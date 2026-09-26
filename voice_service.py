"""Thread-isolated WebRTC voice rooms backed by Supabase Realtime Broadcast.

The service owns its asyncio loop and never touches Tk/CustomTkinter objects.
GUI callbacks are invoked from the worker thread and should be marshalled with
``after`` by the caller.
"""

import asyncio
import math
import queue
import threading
from typing import Any, Callable, Optional

from aiortc import MediaStreamTrack


ROOM_NAMES = tuple(f"voice-{number}" for number in range(1, 6))
MAX_PARTICIPANTS = 5
STUN_SERVER = "stun:stun.l.google.com:19302"


class _MicrophoneTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, on_level=None):
        super().__init__()
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=12)
        self._stream = None
        self._closed = False
        self._pts = 0
        self._on_level = on_level

    async def recv(self):
        from av import AudioFrame

        data = await asyncio.to_thread(self._queue.get)
        if data is None:
            raise asyncio.CancelledError
        frame = AudioFrame.from_ndarray(data.T, format="s16", layout="mono")
        frame.sample_rate = 48000
        frame.pts = self._pts
        self._pts += frame.samples
        return frame

    def start(self):
        import sounddevice as sd

        def callback(indata, frames, time_info, status):
            if self._closed:
                return
            if self._on_level is not None:
                peak = max(abs(int(value)) for value in indata[:, 0]) / 32768.0
                self._on_level(min(1.0, math.sqrt(peak) * 1.7))
            try:
                self._queue.put_nowait(indata.copy())
            except queue.Full:
                pass

        self._stream = sd.InputStream(
            samplerate=48000,
            blocksize=960,
            channels=1,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

    def stop(self):
        self._closed = True
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass


class _Speaker:
    def __init__(self):
        self._stream = None
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=12)

    async def consume(self, track):
        while True:
            frame = await track.recv()
            try:
                self._queue.put_nowait(frame.to_ndarray(format="s16", layout="mono"))
            except queue.Full:
                pass

    def start(self):
        import sounddevice as sd

        def callback(outdata, frames, time_info, status):
            outdata.fill(0)
            try:
                data = self._queue.get_nowait()
            except queue.Empty:
                return
            data = data.reshape(-1)
            length = min(len(data), len(outdata))
            outdata[:length, 0] = data[:length]

        self._stream = sd.OutputStream(
            samplerate=48000,
            blocksize=960,
            channels=1,
            dtype="int16",
            callback=callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class VoiceService:
    """Manage one five-person mesh room without blocking the GUI thread."""

    def __init__(
        self,
        base_url: str,
        anon_key: str,
        username: str,
        on_status: Optional[Callable[[str, Optional[Exception]], None]] = None,
        on_participants: Optional[Callable[[list[str]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_level: Optional[Callable[[float], None]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key
        self.username = username.strip()
        self.client = None
        self.channel = None
        self.room_name = None
        self._thread = None
        self._loop = None
        self._stop_event = threading.Event()
        self._peers: dict[str, Any] = {}
        self._participants: set[str] = set()
        self._microphone = None
        self._speaker = None
        self._on_status = on_status
        self._on_participants = on_participants
        self._on_error = on_error
        self._on_level = on_level

    @property
    def enabled(self):
        return bool(self.base_url and self.anon_key and self.username)

    @property
    def participants(self):
        return sorted(self._participants)

    @property
    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def start(self):
        if not self.enabled or self.running:
            return self.enabled
        self._stop_event.clear()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="voice-service", daemon=True)
        self._thread.start()
        return True

    def join_room(self, room_name: str):
        if room_name not in ROOM_NAMES:
            raise ValueError(f"room_name must be one of {ROOM_NAMES}")
        if not self.start():
            return False
        self._submit(self._join_room(room_name))
        return True

    def leave_room(self):
        if self._loop and self.running:
            self._submit(self._leave_room())

    def stop(self):
        self._stop_event.set()
        if self._loop and self.running:
            self._submit(self._shutdown())

    def start_microphone(self):
        if not self._loop or not self.running:
            return False
        self._submit(self._start_microphone())
        return True

    def stop_microphone(self):
        if self._loop and self.running:
            self._submit(self._stop_microphone())

    def _submit(self, coroutine):
        asyncio.run_coroutine_threadsafe(coroutine, self._loop)

    def _run(self):
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._wait_for_stop())
        except Exception as error:
            self._notify_error(error)
        finally:
            self._loop.close()
            self._loop = None

    async def _wait_for_stop(self):
        await self._connect()
        while not self._stop_event.is_set():
            await asyncio.sleep(0.2)
        await self._shutdown()

    async def _connect(self):
        from supabase import acreate_client

        self.client = await acreate_client(self.base_url, self.anon_key)
        self._notify_status("READY")

    async def _join_room(self, room_name):
        if self.room_name == room_name:
            return
        if self.room_name:
            await self._leave_room()
        self.room_name = room_name
        self._participants = {self.username}
        self.channel = self.client.channel(f"voice-{room_name}")
        self.channel.on_broadcast("signal", self._handle_broadcast)
        self.channel.on_broadcast("presence", self._handle_broadcast)
        await self.channel.subscribe(self._handle_subscribe)
        await self._broadcast("presence", {"action": "join", "user": self.username})
        await self._broadcast("presence", {"action": "sync_request", "user": self.username})
        self._notify_participants()

    async def _leave_room(self):
        if self.channel is not None:
            await self._broadcast("presence", {"action": "leave", "user": self.username})
        for peer in list(self._peers.values()):
            await peer.close()
        self._peers.clear()
        if self.client is not None and self.channel is not None:
            await self.client.remove_channel(self.channel)
        self.channel = None
        self.room_name = None
        self._participants = set()
        self._notify_participants()

    async def _shutdown(self):
        await self._stop_microphone()
        await self._leave_room()
        if self.client is not None:
            await self.client.realtime.close()
            self.client = None
        self._notify_status("STOPPED")

    async def _broadcast(self, event, payload):
        if self.channel is not None:
            await self.channel.send_broadcast(event, payload)

    def _handle_subscribe(self, status, error=None):
        self._notify_status(getattr(status, "value", status), error)

    def _handle_broadcast(self, message):
        payload = message.get("payload", message) if isinstance(message, dict) else {}
        if not isinstance(payload, dict) or payload.get("user") == self.username:
            return
        asyncio.create_task(self._handle_message_safely(message.get("event", ""), payload))

    async def _handle_message_safely(self, event, payload):
        try:
            await self._handle_message(event, payload)
        except Exception as error:
            self._notify_error(error)

    async def _handle_message(self, event, payload):
        user = payload.get("user")
        if not user or len(user) > 80:
            return
        if event == "presence":
            action = payload.get("action")
            if action in {"join", "roster"}:
                if len(self._participants) >= MAX_PARTICIPANTS and user not in self._participants:
                    return
                self._participants.add(user)
                self._notify_participants()
                if action == "join":
                    await self._broadcast("presence", {"action": "roster", "user": self.username})
                if self.username < user:
                    await self._ensure_peer(user, offer=True)
            elif action == "sync_request":
                await self._broadcast("presence", {"action": "roster", "user": self.username})
            elif action == "leave":
                self._participants.discard(user)
                peer = self._peers.pop(user, None)
                if peer:
                    await peer.close()
                self._notify_participants()
            return
        if event != "signal" or payload.get("target") != self.username:
            return
        peer = await self._ensure_peer(user)
        signal_type = payload.get("type")
        if signal_type == "offer":
            from aiortc import RTCSessionDescription

            if self._microphone and not any(
                sender.track is self._microphone
                for sender in peer.getSenders()
            ):
                peer.addTrack(self._microphone)
            await peer.setRemoteDescription(RTCSessionDescription(payload["sdp"], "offer"))
            answer = await peer.createAnswer()
            await peer.setLocalDescription(answer)
            await self._send_signal(user, "answer", peer.localDescription.sdp)
        elif signal_type == "answer":
            from aiortc import RTCSessionDescription

            await peer.setRemoteDescription(RTCSessionDescription(payload["sdp"], "answer"))
        elif signal_type == "ice" and payload.get("candidate"):
            from aiortc import RTCIceCandidate

            await peer.addIceCandidate(RTCIceCandidate(**payload["candidate"]))

    async def _ensure_peer(self, user, offer=False):
        if user in self._peers:
            peer = self._peers[user]
        else:
            from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer

            peer = RTCPeerConnection(RTCConfiguration([RTCIceServer(urls=[STUN_SERVER])]))
            self._peers[user] = peer

            @peer.on("icecandidate")
            async def on_ice(candidate):
                if candidate:
                    await self._send_signal(
                        user,
                        "ice",
                        {
                            "component": candidate.component,
                            "foundation": candidate.foundation,
                            "ip": candidate.ip,
                            "port": candidate.port,
                            "priority": candidate.priority,
                            "protocol": candidate.protocol,
                            "type": candidate.type,
                            "relatedAddress": candidate.relatedAddress,
                            "relatedPort": candidate.relatedPort,
                            "sdpMid": candidate.sdpMid,
                            "sdpMLineIndex": candidate.sdpMLineIndex,
                            "tcpType": candidate.tcpType,
                        },
                    )

            @peer.on("connectionstatechange")
            async def on_connection_state_change():
                self._notify_status(f"PEER_{peer.connectionState.upper()}")

            @peer.on("iceconnectionstatechange")
            async def on_ice_connection_state_change():
                self._notify_status(f"ICE_{peer.iceConnectionState.upper()}")

            @peer.on("track")
            def on_track(track):
                if track.kind == "audio":
                    self._notify_status("AUDIO_RECEIVED")
                    if self._speaker is None:
                        self._speaker = _Speaker()
                        self._speaker.start()
                    asyncio.create_task(self._speaker.consume(track))
        if offer:
            if self._microphone:
                peer.addTrack(self._microphone)
            offer_description = await peer.createOffer()
            await peer.setLocalDescription(offer_description)
            await self._send_signal(user, "offer", peer.localDescription.sdp)
        return peer

    async def _send_signal(self, target, signal_type, value):
        payload = {"user": self.username, "target": target, "type": signal_type}
        if signal_type == "ice":
            payload["candidate"] = value
        else:
            payload["sdp"] = value
        await self._broadcast("signal", payload)

    async def _start_microphone(self):
        if self._microphone is not None:
            return
        try:
            self._microphone = _MicrophoneTrack(self._notify_microphone_level)
            self._microphone.start()
            for user in self._participants:
                if user == self.username:
                    continue
                await self._ensure_peer(user, offer=self.username < user)
            self._notify_status("MICROPHONE_ON")
        except Exception as error:
            self._microphone = None
            self._notify_microphone_level(0.0)
            self._notify_error(error)

    async def _stop_microphone(self):
        if self._microphone is not None:
            self._microphone.stop()
            self._microphone = None
        self._notify_microphone_level(0.0)
        if self._speaker is not None:
            self._speaker.stop()
            self._speaker = None

    def _notify_status(self, status, error=None):
        if self._on_status:
            self._on_status(status, error)

    def _notify_participants(self):
        if self._on_participants:
            self._on_participants(self.participants)

    def _notify_error(self, error):
        if self._on_error:
            self._on_error(error)
        self._notify_status("ERROR", error)

    def _notify_microphone_level(self, level):
        if self._on_level:
            self._on_level(max(0.0, min(1.0, float(level))))