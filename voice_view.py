import tkinter as tk

import customtkinter as ctk

from voice_service import ROOM_NAMES


class VoiceViewMixin:
    def setup_voice_tab(self):
        ctk.CTkLabel(
            self.tab_voice,
            text="POKOJE GŁOSOWE",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(18, 4))
        ctk.CTkLabel(
            self.tab_voice,
            text="Dołącz do jednego pokoju i rozmawiaj z innymi użytkownikami.",
            text_color="#94A3B8"
        ).pack(pady=(0, 12))

        self.voice_status_label = ctk.CTkLabel(self.tab_voice, text="Niezalogowany", text_color="#94A3B8")
        self.voice_status_label.pack(pady=(0, 8))
        self.voice_room_cards = {}
        rooms_frame = ctk.CTkFrame(self.tab_voice, fg_color="transparent")
        rooms_frame.pack(fill="x", padx=20, pady=8)
        for index, room_name in enumerate(ROOM_NAMES, start=1):
            card = ctk.CTkFrame(rooms_frame, fg_color="#172338", border_width=1, border_color="#263449")
            card.grid(row=(index - 1) // 2, column=(index - 1) % 2, sticky="nsew", padx=6, pady=6)
            rooms_frame.grid_columnconfigure((index - 1) % 2, weight=1)
            ctk.CTkLabel(card, text=f"POKÓJ {index}", font=ctk.CTkFont(size=15, weight="bold"), text_color="#38BDF8").pack(anchor="w", padx=14, pady=(12, 3))
            participants = ctk.CTkLabel(card, text="Pusto", anchor="w", text_color="#CBD5E1")
            participants.pack(fill="x", padx=14, pady=(0, 9))
            button = ctk.CTkButton(card, text="Dołącz", width=110, command=lambda room=room_name: self.join_voice_room(room))
            button.pack(anchor="e", padx=14, pady=(0, 12))
            self.voice_room_cards[room_name] = {"participants": participants, "button": button}

        self.voice_controls = ctk.CTkFrame(self.tab_voice, fg_color="#0F172A")
        self.voice_controls.pack(fill="x", padx=20, pady=(14, 10))
        self.voice_current_label = ctk.CTkLabel(self.voice_controls, text="Nie jesteś w pokoju", text_color="#CBD5E1")
        self.voice_current_label.pack(side="left", padx=14, pady=12)
        self.voice_mute_button = ctk.CTkButton(self.voice_controls, text="Włącz mikrofon", width=135, command=self.toggle_voice_microphone, state="disabled")
        self.voice_mute_button.pack(side="right", padx=(6, 14), pady=8)
        self.voice_leave_button = ctk.CTkButton(self.voice_controls, text="Opuść pokój", width=110, fg_color="#DC2626", hover_color="#B91C1C", command=self.leave_voice_room, state="disabled")
        self.voice_leave_button.pack(side="right", padx=6, pady=8)
        ctk.CTkLabel(self.voice_controls, text="Mikrofon", text_color="#94A3B8").pack(side="left", padx=(14, 4), pady=12)
        self.voice_level_bar = ctk.CTkProgressBar(self.voice_controls, width=180, height=14, progress_color="#10B981")
        self.voice_level_bar.set(0)
        self.voice_level_bar.pack(side="left", padx=4, pady=12)

    def start_voice_service(self):
        if not self.current_user:
            return
        from voice_service import VoiceService
        self.voice_service = VoiceService(
            self.cloud_data_service.base_url,
            self.cloud_data_service.anon_key,
            self.current_user,
            on_status=self._on_voice_status,
            on_participants=self._on_voice_participants,
            on_error=self._on_voice_error,
            on_level=self._on_voice_level,
        )

    def stop_voice_service(self):
        service = getattr(self, "voice_service", None)
        if service:
            service.stop()
        self.voice_service = None
        if hasattr(self, "voice_current_label"):
            self.voice_current_label.configure(text="Nie jesteś w pokoju")
            self.voice_leave_button.configure(state="disabled")
            self.voice_mute_button.configure(state="disabled")
            self.voice_level_bar.set(0)

    def join_voice_room(self, room_name):
        service = getattr(self, "voice_service", None)
        if not service:
            self.voice_status_label.configure(text="Zaloguj się, aby używać pokojów głosowych.", text_color="#FBBF24")
            return
        service.join_room(room_name)
        self.voice_current_label.configure(text=f"Łączenie z {room_name.replace('voice-', 'Pokój ')}...")
        self.voice_leave_button.configure(state="normal")
        self.voice_mute_button.configure(state="normal")

    def leave_voice_room(self):
        service = getattr(self, "voice_service", None)
        if service:
            service.leave_room()
        self.voice_current_label.configure(text="Nie jesteś w pokoju")
        self.voice_leave_button.configure(state="disabled")
        self.voice_mute_button.configure(state="disabled")
        self.voice_level_bar.set(0)

    def toggle_voice_microphone(self):
        service = getattr(self, "voice_service", None)
        if not service:
            return
        if getattr(self, "voice_microphone_on", False):
            service.stop_microphone()
            self.voice_microphone_on = False
            self.voice_mute_button.configure(text="Włącz mikrofon")
        else:
            service.start_microphone()
            self.voice_microphone_on = True
            self.voice_mute_button.configure(text="Wycisz mikrofon")

    def _on_voice_status(self, status, error=None):
        try:
            self.after(0, lambda: self._apply_voice_status(status, error))
        except tk.TclError:
            pass

    def _apply_voice_status(self, status, error=None):
        labels = {"READY": "Połączono z usługą głosową", "SUBSCRIBED": "Pokój gotowy", "MICROPHONE_ON": "Mikrofon włączony", "STOPPED": "Usługa głosowa zatrzymana", "ERROR": "Błąd połączenia głosowego"}
        self.voice_status_label.configure(text=labels.get(status, str(status)), text_color="#34D399" if status not in {"ERROR"} else "#FCA5A5")

    def _on_voice_participants(self, participants):
        try:
            self.after(0, lambda: self._apply_voice_participants(participants))
        except tk.TclError:
            pass

    def _apply_voice_participants(self, participants):
        current_room = getattr(getattr(self, "voice_service", None), "room_name", None)
        for room_name, card in self.voice_room_cards.items():
            if room_name == current_room:
                names = ", ".join(participants) if participants else "Pusto"
                card["participants"].configure(text=f"{len(participants)}/5: {names}")
                self.voice_current_label.configure(text=f"{room_name.replace('voice-', 'Pokój ')} · {len(participants)}/5 osób")
            else:
                card["participants"].configure(text="Pokój dostępny")

    def _on_voice_error(self, error):
        self._on_voice_status("ERROR", error)

    def _on_voice_level(self, level):
        try:
            self.after(0, lambda: self.voice_level_bar.set(level))
        except tk.TclError:
            pass
