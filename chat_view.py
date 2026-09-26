import threading
from datetime import datetime
import tkinter as tk

import customtkinter as ctk


class ChatViewMixin:
    def setup_chat_tab(self):
        ctk.CTkLabel(self.tab_chat, text="CHAT TRENINGOWY", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(16, 4))
        ctk.CTkLabel(self.tab_chat, text="Wiadomości użytkowników aplikacji.", text_color="#94A3B8").pack(pady=(0, 10))
        self.chat_messages_frame = ctk.CTkScrollableFrame(self.tab_chat, label_text="WIADOMOŚCI")
        self.chat_messages_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.chat_message_ids = set()
        self.chat_status_label = None
        composer = ctk.CTkFrame(self.tab_chat, fg_color="#0F172A")
        composer.pack(fill="x", padx=20, pady=(0, 15))
        self.chat_entry = ctk.CTkEntry(composer, placeholder_text="Napisz wiadomość...", height=38)
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.chat_entry.bind("<Return>", lambda event: self.send_chat_message())
        self.chat_send_button = ctk.CTkButton(composer, text="Wyślij", width=90, command=self.send_chat_message)
        self.chat_send_button.pack(side="right", padx=10, pady=10)
        self.refresh_chat_messages()

    def start_chat_realtime(self):
        if not self.chat_service.enabled:
            self.refresh_chat_status([])
            return
        self.stop_chat_polling()
        started = self.chat_realtime_service.start(
            self._on_chat_realtime_message,
            self._on_chat_realtime_status,
        )
        if not started:
            self.start_chat_polling()
        self.refresh_chat_messages()

    def stop_chat_realtime(self):
        self.chat_realtime_service.stop()
        self.stop_chat_polling()

    def _on_chat_realtime_message(self, message):
        try:
            self.after(0, lambda: self._append_chat_message(message))
        except tk.TclError:
            pass

    def _on_chat_realtime_status(self, status, error=None):
        try:
            self.after(0, lambda: self._apply_chat_realtime_status(status))
        except tk.TclError:
            pass

    def _apply_chat_realtime_status(self, status):
        if status == "SUBSCRIBED":
            self.stop_chat_polling()
            self.refresh_chat_messages()
        elif status in {"CHANNEL_ERROR", "TIMED_OUT", "ERROR"}:
            self.start_chat_polling()

    def stop_chat_polling(self):
        if getattr(self, "chat_polling_job", None):
            self.after_cancel(self.chat_polling_job)
            self.chat_polling_job = None

    def chat_polling_tick(self):
        self.refresh_chat_messages()
        self.chat_polling_job = self.after(5000, self.chat_polling_tick)

    def refresh_chat_messages(self):
        if not self.chat_service.enabled:
            self.refresh_chat_status([])
            return
        threading.Thread(target=self._chat_load_worker, daemon=True).start()

    def _chat_load_worker(self):
        try:
            messages = self.chat_service.get_messages()
        except Exception:
            messages = None
        self.after(0, lambda: self.refresh_chat_status(messages))

    def refresh_chat_status(self, messages):
        if messages is None:
            if not self.chat_message_ids:
                self._show_chat_status("Brak połączenia z czatem.", "#FCA5A5")
            return
        for item in reversed(messages):
            self._append_chat_message(item)
        if not self.chat_message_ids:
            self._show_chat_status("Brak wiadomości.", "#94A3B8")

    def _show_chat_status(self, text, color):
        if self.chat_status_label is None:
            self.chat_status_label = ctk.CTkLabel(
                self.chat_messages_frame,
                text=text,
                text_color=color,
            )
            self.chat_status_label.pack(anchor="w", padx=10, pady=10)
        else:
            self.chat_status_label.configure(text=text, text_color=color)

    def _clear_chat_status(self):
        if self.chat_status_label is not None:
            self.chat_status_label.destroy()
            self.chat_status_label = None

    def _append_chat_message(self, item):
        if not isinstance(item, dict):
            return
        message_id = item.get("id")
        message_key = message_id if message_id is not None else (
            item.get("username"), item.get("message"), item.get("created_at")
        )
        if message_key in self.chat_message_ids:
            return
        self._clear_chat_status()
        self.chat_message_ids.add(message_key)

        row = ctk.CTkFrame(self.chat_messages_frame, fg_color="#1E293B")
        row.pack(fill="x", padx=5, pady=3)
        created_at = item.get("created_at", "")
        try:
            timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
        except (AttributeError, ValueError):
            timestamp = "--:--"
        ctk.CTkLabel(row, text=item.get("username", "Użytkownik"), width=120, anchor="w", text_color="#38BDF8", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10, pady=8)
        ctk.CTkLabel(row, text=item.get("message", ""), anchor="w", justify="left", wraplength=650).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ctk.CTkLabel(row, text=timestamp, width=55, text_color="#94A3B8").pack(side="right", padx=8)

    def send_chat_message(self):
        message = self.chat_entry.get().strip()
        if not message or not self.current_user or not self.chat_service.enabled:
            return
        if len(message) > 500:
            message = message[:500]
        self.chat_entry.delete(0, "end")
        self.chat_send_button.configure(state="disabled")
        threading.Thread(target=self._chat_send_worker, args=(self.current_user, message), daemon=True).start()

    def _chat_send_worker(self, username, message):
        try:
            result = self.chat_service.send_message(username, message)
            if result:
                self.after(0, lambda: self._append_chat_message(result[0]))
        finally:
            self.after(0, lambda: self.chat_send_button.configure(state="normal"))
