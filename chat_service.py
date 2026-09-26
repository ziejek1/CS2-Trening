import asyncio
import json
import threading
import uuid
import urllib.request


class ChatService:
    def __init__(self, base_url, anon_key):
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key

    @property
    def enabled(self):
        return bool(self.base_url and self.anon_key)

    def _request(self, method, path, payload=None):
        url = f"{self.base_url}/rest/v1/{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("apikey", self.anon_key)
        request.add_header("Authorization", f"Bearer {self.anon_key}")
        request.add_header("Content-Type", "application/json")
        request.add_header("Prefer", "return=representation")
        with urllib.request.urlopen(request, timeout=8) as response:
            content = response.read().decode("utf-8")
            return json.loads(content) if content else []

    def get_messages(self, limit=10):
        limit = max(1, min(int(limit), 100))
        return self._request(
            "GET",
            f"chat_messages?select=id,username,message,created_at&order=created_at.desc,id.desc&limit={limit}"
        )

    def send_message(self, username, message):
        return self._request(
            "POST",
            "chat_messages",
            {"username": username, "message": message}
        )


class ChatRealtimeService:
    def __init__(self, base_url, anon_key):
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key
        self._stop_event = threading.Event()
        self._thread = None
        self._on_message = None
        self._on_status = None

    @property
    def enabled(self):
        return bool(self.base_url and self.anon_key)

    def start(self, on_message, on_status=None):
        if not self.enabled:
            return False
        if self._thread and self._thread.is_alive():
            if not self._stop_event.is_set():
                return True
            self._thread.join(timeout=1)
            if self._thread.is_alive():
                return False

        self._stop_event.clear()
        self._on_message = on_message
        self._on_status = on_status
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._stop_event.set()

    def _run(self):
        try:
            asyncio.run(self._listen())
        except Exception as error:
            if not self._stop_event.is_set():
                self._notify_status("ERROR", error)

    async def _listen(self):
        from supabase import acreate_client

        client = None
        channel = None
        try:
            client = await acreate_client(self.base_url, self.anon_key)
            channel = client.channel(f"chat-{uuid.uuid4().hex}")
            channel.on_postgres_changes(
                "INSERT",
                callback=self._handle_change,
                schema="public",
                table="chat_messages",
            )
            await channel.subscribe(self._handle_subscribe)
            while not self._stop_event.is_set():
                await asyncio.sleep(0.25)
        except Exception as error:
            if not self._stop_event.is_set():
                self._notify_status("ERROR", error)
        finally:
            if client is not None and channel is not None:
                try:
                    await client.remove_channel(channel)
                except Exception:
                    pass

    def _handle_change(self, payload):
        record = payload.get("data", {}).get("record")
        if isinstance(record, dict) and self._on_message:
            self._on_message(record)

    def _handle_subscribe(self, status, error):
        self._notify_status(getattr(status, "value", status), error)

    def _notify_status(self, status, error=None):
        if self._on_status:
            self._on_status(status, error)
