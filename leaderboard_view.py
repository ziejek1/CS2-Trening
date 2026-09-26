import os
import threading
from io import BytesIO
import urllib.request

import customtkinter as ctk
from PIL import Image
from avatar_utils import crop_avatar, get_avatar_focus, get_avatar_zoom


class LeaderboardViewMixin:
    def setup_leaderboard_tab(self):
        ctk.CTkLabel(
            self.tab_leaderboard,
            text="TOP UCZNIOWIE",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(pady=(18, 4))
        ctk.CTkLabel(
            self.tab_leaderboard,
            text="Ranking na podstawie XP, ukończonych ćwiczeń i czasu treningu.",
            text_color="#94A3B8"
        ).pack(pady=(0, 14))

        self.leaderboard_podium = ctk.CTkFrame(self.tab_leaderboard, fg_color="#0F172A")
        self.leaderboard_podium.pack(fill="x", padx=20, pady=(0, 12))
        self.leaderboard_list = ctk.CTkScrollableFrame(self.tab_leaderboard, label_text="KLASYFIKACJA")
        self.leaderboard_list.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self.leaderboard_avatar_images = {}
        self.refresh_leaderboard()

    def _set_leaderboard_avatar(self, label, username, size, image_key):
        user_info = self.get_user_data(username)
        avatar_path = user_info.get("avatar_path", "")
        if avatar_path and os.path.exists(avatar_path):
            try:
                image = crop_avatar(
                    Image.open(avatar_path),
                    get_avatar_zoom(user_info),
                    *get_avatar_focus(user_info)
                )
                image.thumbnail((size, size), Image.Resampling.LANCZOS)
                avatar_image = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
                label.configure(image=avatar_image, text="")
                self.leaderboard_avatar_images[image_key] = avatar_image
                return
            except Exception:
                pass

        avatar_url = user_info.get("avatar_url", "")
        if not avatar_url:
            return

        def load_remote_avatar():
            try:
                request = urllib.request.Request(avatar_url, headers={"User-Agent": "CS2-Trening-Avatar"})
                with urllib.request.urlopen(request, timeout=8) as response:
                    image = crop_avatar(
                        Image.open(BytesIO(response.read())),
                        get_avatar_zoom(user_info),
                        *get_avatar_focus(user_info)
                    )
                image.thumbnail((size, size), Image.Resampling.LANCZOS)
                avatar_image = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
                self.after(0, lambda: self._apply_leaderboard_avatar(label, avatar_image, image_key))
            except Exception:
                pass

        threading.Thread(target=load_remote_avatar, daemon=True).start()

    def _apply_leaderboard_avatar(self, label, avatar_image, image_key):
        try:
            if label.winfo_exists():
                label.configure(image=avatar_image, text="")
                self.leaderboard_avatar_images[image_key] = avatar_image
        except Exception:
            pass

    def get_leaderboard_entries(self):
        entries = []
        training_profiles = self.get_leaderboard_training_data()
        for username, user_data in self.users.items():
            if not isinstance(user_data, dict):
                continue
            training_data = training_profiles.get(username, {})
            if not isinstance(training_data, dict):
                continue
            try:
                xp = int(training_data.get("fatigue_score", 0))
            except (TypeError, ValueError):
                xp = 0
            try:
                completed = int(training_data.get("completed_count", 0))
            except (TypeError, ValueError):
                completed = 0
            total_seconds = self.get_total_seconds(training_data)
            entries.append({
                "username": username,
                "xp": max(0, xp),
                "rank": self.get_rank_for_xp(max(0, xp)),
                "completed": max(0, completed),
                "seconds": max(0, total_seconds),
                "streak": self.get_longest_training_streak(training_data)
            })
        return sorted(
            entries,
            key=lambda entry: (entry["xp"], entry["completed"], entry["seconds"]),
            reverse=True
        )

    def refresh_leaderboard(self):
        if not hasattr(self, "leaderboard_list"):
            return
        for widget in self.leaderboard_podium.winfo_children():
            widget.destroy()
        for widget in self.leaderboard_list.winfo_children():
            widget.destroy()
        self.leaderboard_avatar_images.clear()

        entries = self.get_leaderboard_entries()
        podium_colors = ("#FBBF24", "#CBD5E1", "#CD7F32")
        podium_symbols = ("🥇", "🥈", "🥉")
        for place in range(min(3, len(entries))):
            entry = entries[place]
            card = ctk.CTkFrame(self.leaderboard_podium, fg_color="#172338", border_width=1, border_color=podium_colors[place])
            card.pack(side="left", fill="x", expand=True, padx=7, pady=10)
            avatar_label = ctk.CTkLabel(card, text="👤", width=42, height=42, font=ctk.CTkFont(size=20))
            avatar_label.pack(pady=(8, 0))
            self._set_leaderboard_avatar(avatar_label, entry["username"], 42, f"podium-{place}")
            ctk.CTkLabel(card, text=f"{podium_symbols[place]}  {entry['username']} · {entry['rank']}", text_color=podium_colors[place], font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(10, 4))
            ctk.CTkLabel(card, text=f"{entry['xp']} XP  ·  {entry['completed']} ćw.", font=ctk.CTkFont(weight="bold")).pack(pady=(0, 3))
            ctk.CTkLabel(card, text=f"Seria: {entry['streak']} dni", text_color="#CBD5E1").pack(pady=(0, 10))

        if not entries:
            ctk.CTkLabel(self.leaderboard_list, text="Brak danych do rankingu.", text_color="#94A3B8").pack(anchor="w", padx=10, pady=10)
            return

        for place, entry in enumerate(entries, start=1):
            hours, remainder = divmod(entry["seconds"], 3600)
            minutes = remainder // 60
            row = ctk.CTkFrame(self.leaderboard_list, fg_color="#1E293B")
            row.pack(fill="x", padx=5, pady=4)
            rank_color = "#FBBF24" if place == 1 else "#CBD5E1" if place == 2 else "#CD7F32" if place == 3 else "#94A3B8"
            ctk.CTkLabel(row, text=f"#{place}", width=55, text_color=rank_color, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=10, pady=9)
            avatar_label = ctk.CTkLabel(row, text="👤", width=30, height=30, font=ctk.CTkFont(size=14))
            avatar_label.pack(side="left", padx=(0, 4), pady=5)
            self._set_leaderboard_avatar(avatar_label, entry["username"], 30, f"list-{place}")
            ctk.CTkLabel(row, text=f"{entry['username']} · {entry['rank']}", anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", fill="x", expand=True, padx=8, pady=9)
            ctk.CTkLabel(row, text=f"{entry['xp']} XP", width=90, text_color="#FBBF24").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"{entry['completed']} ćw.", width=90, text_color="#34D399").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"{hours}h {minutes:02d}m", width=85, text_color="#93C5FD").pack(side="left", padx=4)
            ctk.CTkLabel(row, text=f"Seria {entry['streak']} dni", width=105, text_color="#F472B6").pack(side="left", padx=8)
