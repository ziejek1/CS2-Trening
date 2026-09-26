import customtkinter as ctk
import csv
import json
import os
import secrets
import sys
import tkinter as tk
from io import BytesIO
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from tkinter import filedialog, messagebox
import threading
import urllib.request
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import Image
from avatar_utils import crop_avatar, get_avatar_focus, get_avatar_zoom
from auth_utils import hash_password, hash_remember_token, verify_password
from data_store import (
    clear_remembered_login,
    load_remembered_login,
    load_training_data,
    load_users,
    save_remembered_login,
    save_training_data,
    save_users,
)
from training_utils import (
    get_current_training_streak,
    get_longest_training_streak,
    get_rank_for_xp,
    get_rank_progress,
    get_task_category,
    get_total_seconds,
    get_training_badges,
    get_training_chart_data,
    get_training_dates,
    get_weekly_training_totals,
    infer_skill_category,
    parse_completion_date,
)
from leaderboard_view import LeaderboardViewMixin
from planner_view import PlannerViewMixin
from stats_view import StatsViewMixin
from app_constants import (
    DATA_FILE,
    USERS_FILE,
    REMEMBERED_LOGIN_FILE,
    PASSWORD_SCHEME,
    APP_VERSION,
    SUPABASE_ANON_KEY,
    SUPABASE_URL,
    PRESET_PROTOCOLS,
    CS2_RANKS,
    SKILL_CATEGORIES,
    SKILL_CATEGORY_COLORS,
    DEFAULT_MODULE_CATALOG,
)
from update_utils import download_installer, fetch_latest_release, launch_installer
from presence_service import PresenceService
from chat_service import ChatRealtimeService, ChatService
from chat_view import ChatViewMixin
from voice_view import VoiceViewMixin
from cloud_data_service import CloudDataService, merge_training_data

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class CS2ProTrainingApp(ChatViewMixin, VoiceViewMixin, StatsViewMixin, PlannerViewMixin, LeaderboardViewMixin, ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CS2 TRENING E-SPORT")
        self.geometry("1150x880")
        try:
            self.iconbitmap(self.get_resource_path("app_icon.ico"))
        except tk.TclError:
            pass
        self.protocol("WM_DELETE_WINDOW", self.close_app)

        self.users = self.load_users()
        self.training_data = self.load_data()
        self.data = self.empty_training_data()
        self.remembered_login = self.load_remembered_login()
        self.current_user = None
        self.presence_service = PresenceService(SUPABASE_URL, SUPABASE_ANON_KEY)
        self.presence_job = None
        self.realtime_presence_cache = {}
        self.chat_service = ChatService(SUPABASE_URL, SUPABASE_ANON_KEY)
        self.chat_realtime_service = ChatRealtimeService(SUPABASE_URL, SUPABASE_ANON_KEY)
        self.chat_polling_job = None
        self.voice_service = None
        self.voice_microphone_on = False
        self.cloud_data_service = CloudDataService(SUPABASE_URL, SUPABASE_ANON_KEY)
        self.cloud_leaderboard_cache = None
        self.cloud_leaderboard_cache_time = None
        self.shared_config_job = None
        self.sync_users()
        self.sync_shared_config()

        # Stan stoperów
        self.active_timer_index = None
        self.session_timer_seconds = 0
        self.timer_job = None
        self.rest_timer_seconds = 0
        self.rest_timer_job = None
        self.reminder_job = None
        self.reminder_window = None
        self.rank_progress_animation_job = None

        # Górny pasek nagłówka z awatarem i przyciskiem wylogowania
        self.top_bar = ctk.CTkFrame(self, fg_color="#0F172A", height=50)
        self.top_bar.pack(fill="x", side="top")

        self.lbl_user_avatar_top = ctk.CTkLabel(self.top_bar, text="👤", width=35, height=35)
        self.lbl_user_avatar_top.pack(side="left", padx=(15, 5), pady=8)

        self.lbl_user_info = ctk.CTkLabel(
            self.top_bar, 
            text="Zalogowany jako: --", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.lbl_user_info.pack(side="left", padx=5, pady=8)

        self.lbl_online_users = ctk.CTkLabel(
            self.top_bar,
            text="Online: --",
            text_color="#A7F3D0",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_online_users.pack(side="left", padx=18, pady=8)

        self.btn_logout = ctk.CTkButton(
            self.top_bar, 
            text="🚪 Wyloguj się", 
            fg_color="#EF4444", 
            hover_color="#DC2626", 
            width=110,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.logout
        )
        self.btn_logout.pack(side="right", padx=15, pady=8)

        # Tabview (System Zakładek)
        self.tabview = ctk.CTkTabview(
            self,
            corner_radius=12,
            border_width=1,
            border_color="#334155",
            fg_color="#111827",
            segmented_button_fg_color="#1E293B",
            segmented_button_selected_color="#2563EB",
            segmented_button_selected_hover_color="#1D4ED8",
            segmented_button_unselected_color="#1E293B",
            segmented_button_unselected_hover_color="#334155"
        )
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        self.tabview._segmented_button.configure(
            height=42,
            corner_radius=9,
            font=ctk.CTkFont(size=13, weight="bold")
        )

        self.tab_dashboard = self.tabview.add("⚡ Centrum Dowodzenia")
        self.tab_presets = self.tabview.add("🏆 Gotowe Rutyny Pro")
        self.tab_stats = self.tabview.add("📊 Statystyki")
        self.tab_profile = self.tabview.add("👤 Mój Profil")
        self.tab_planner = self.tabview.add("📅 Plan treningowy")
        self.tab_leaderboard = self.tabview.add("🏆 Top uczniowie")
        self.tab_chat = self.tabview.add("💬 Chat")
        self.tab_voice = self.tabview.add("🎙️ Pokoje głosowe")

        self.setup_dashboard()
        self.setup_presets()
        self.setup_stats()
        self.setup_profile_tab()
        self.setup_planner_tab()
        self.setup_leaderboard_tab()
        self.setup_chat_tab()
        self.setup_voice_tab()

        # Zegarek systemowy
        self.update_realtime_clock()
        self.check_training_reminders()
        self.refresh_ui()

        # Otwarcie okna logowania
        self.start_chat_realtime()
        self.show_login_dialog()

    @staticmethod
    def get_resource_path(filename):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, filename)

    # --- ZARZĄDZANIE UŻYTKOWNIKAMI I PROFILAMI ---
    def load_users(self):
        return load_users(USERS_FILE, hash_password)

    def save_users(self):
        save_users(USERS_FILE, self.users)
        if not self.cloud_data_service.enabled:
            return
        for username, user_data in self.users.items():
            try:
                self.cloud_data_service.save_user_account(username, user_data)
            except Exception:
                pass

    def sync_users(self):
        if not self.cloud_data_service.enabled:
            return
        try:
            cloud_users = self.cloud_data_service.get_all_users()
        except Exception:
            return

        if cloud_users:
            local_only_users = {
                username: user_data
                for username, user_data in self.users.items()
                if username not in cloud_users
            }
            self.users.update(cloud_users)
            save_users(USERS_FILE, self.users)
            for username, user_data in local_only_users.items():
                try:
                    self.cloud_data_service.save_user_account(username, user_data)
                except Exception:
                    pass
            return

        for username, user_data in self.users.items():
            try:
                self.cloud_data_service.save_user_account(username, user_data)
            except Exception:
                pass

    def load_remembered_login(self):
        return load_remembered_login(REMEMBERED_LOGIN_FILE)

    def save_remembered_login(self, username, token):
        self.remembered_login = save_remembered_login(REMEMBERED_LOGIN_FILE, username, token)

    def clear_remembered_login(self):
        username = self.remembered_login.get("username")
        if username in self.users:
            self.get_user_data(username).pop("remember_token_hash", None)
            self.save_users()
        self.remembered_login = {}
        clear_remembered_login(REMEMBERED_LOGIN_FILE)

    def get_user_data(self, username):
        user_info = self.users.get(username, {})
        if isinstance(user_info, str):
            user_info = {
                "password": user_info,
                "first_name": "",
                "last_name": "",
                "birth_date": "",
                "avatar_path": ""
            }
            self.users[username] = user_info
        elif not isinstance(user_info, dict):
            user_info = {}
            self.users[username] = user_info
        return user_info

    def get_module_catalog(self):
        catalog = self.training_data.get("module_catalog", [])
        if not isinstance(catalog, list):
            catalog = []
        normalized = []
        for item in catalog:
            if isinstance(item, dict) and item.get("name"):
                category = item.get("category")
                if category not in SKILL_CATEGORIES:
                    category = self.infer_skill_category(item["name"])
                normalized.append({"name": item["name"], "category": category})
            elif isinstance(item, str) and item.strip():
                normalized.append({"name": item.strip(), "category": self.infer_skill_category(item)})
        return normalized or [
            {"name": name, "category": category}
            for name, category in DEFAULT_MODULE_CATALOG
        ]

    def refresh_module_catalog(self):
        if not hasattr(self, "entry_custom_type"):
            return
        catalog = self.get_module_catalog()
        values = [item["name"] for item in catalog]
        self.entry_custom_type.configure(values=values)
        if self.entry_custom_type.get() not in values:
            self.entry_custom_type.set(values[0])
        if self.entry_custom_type.get() in values:
            selected = next(item for item in catalog if item["name"] == self.entry_custom_type.get())
            self.entry_custom_category.set(selected["category"])

    def can_manage_modules(self):
        return self.current_user == "admin"

    def show_module_permission_error(self):
        messagebox.showwarning(
            "Brak uprawnień",
            "Tylko administrator może zmieniać wspólny katalog modułów.",
            parent=self
        )

    @staticmethod
    def infer_skill_category(task_name):
        task_name = str(task_name or "").lower()
        category_keywords = (
            ("AWP", ("awp", "sniper", "flick")),
            ("Utility", ("smoke", "flash", "molotov", "lineup", "utility", "granat")),
            ("Movement", ("movement", "kz", "surf", "strafe", "ruch")),
            ("Recoil", ("recoil", "spray", "odrzut")),
            ("Game sense", ("tactical", "retake", "execute", "prefire", "angle", "pozyc")),
            ("Aim", ("aim", "botz", "headshot", "deathmatch", "gridshot", "cel"))
        )
        for category, keywords in category_keywords:
            if any(keyword in task_name for keyword in keywords):
                return category
        return "Aim"

    @classmethod
    def get_task_category(cls, task):
        category = task.get("category") if isinstance(task, dict) else None
        return category if category in SKILL_CATEGORIES else cls.infer_skill_category(
            task.get("type", "") if isinstance(task, dict) else task
        )

    @staticmethod
    def get_rank_for_xp(xp):
        current_rank = CS2_RANKS[0][1]
        for required_xp, rank_name in CS2_RANKS:
            if xp >= required_xp:
                current_rank = rank_name
            else:
                break
        return current_rank

    @staticmethod
    def get_rank_progress(xp):
        current_index = 0
        for index, (required_xp, _) in enumerate(CS2_RANKS):
            if xp >= required_xp:
                current_index = index
            else:
                break

        current_threshold, current_rank = CS2_RANKS[current_index]
        if current_index == len(CS2_RANKS) - 1:
            return current_rank, "MAX", 1.0

        next_threshold, next_rank = CS2_RANKS[current_index + 1]
        remaining_xp = next_threshold - xp
        progress = (xp - current_threshold) / (next_threshold - current_threshold)
        return current_rank, f"Pozostało {remaining_xp} XP do {next_rank}", max(0.0, min(progress, 1.0))

    # --- EKRAN LOGOWANIA ---
    def show_login_dialog(self):
        self.withdraw()

        login_win = ctk.CTkToplevel(self)
        login_win.title("CS2 TRENING E-SPORT - ZALOGUJ SIĘ !")
        login_win.geometry("400x420")
        login_win.resizable(False, False)
        login_win.attributes("-topmost", True)
        login_win.protocol("WM_DELETE_WINDOW", self.destroy)

        login_win.update_idletasks()
        x = (login_win.winfo_screenwidth() // 2) - (400 // 2)
        y = (login_win.winfo_screenheight() // 2) - (420 // 2)
        login_win.geometry(f"+{x}+{y}")

        title_label = ctk.CTkLabel(
            login_win, 
            text="🔐 PANEL LOGOWANIA", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(25, 15))

        entry_username = ctk.CTkEntry(login_win, placeholder_text="Login", width=280)
        entry_username.pack(pady=10)

        entry_password = ctk.CTkEntry(login_win, placeholder_text="Hasło", show="*", width=280)
        entry_password.pack(pady=10)

        chk_remember_login = ctk.CTkCheckBox(
            login_win,
            text="Zapamiętaj mnie na tym komputerze",
            font=ctk.CTkFont(size=12)
        )
        chk_remember_login.pack(pady=(2, 5))

        remembered_username = self.remembered_login.get("username", "")
        remembered_token = self.remembered_login.get("token", "")
        if remembered_username in self.users:
            entry_username.insert(0, remembered_username)
            chk_remember_login.select()

        def toggle_password_visibility():
            if chk_show_password.get() == 1:
                entry_password.configure(show="")
            else:
                entry_password.configure(show="*")

        chk_show_password = ctk.CTkCheckBox(
            login_win, 
            text="Pokaż hasło", 
            command=toggle_password_visibility,
            font=ctk.CTkFont(size=12)
        )
        chk_show_password.pack(pady=(2, 10))

        lbl_error = ctk.CTkLabel(login_win, text="", text_color="#EF4444", font=ctk.CTkFont(size=12, weight="bold"))
        lbl_error.pack(pady=5)

        def finish_login(user, user_info):
            self.current_user = user
            self.load_user_training_data()
            self.refresh_custom_routines()
            self.refresh_ui()
            self.session_timer_seconds = 0
            self.refresh_timer_displays()
            self.lbl_user_info.configure(text=f"{self.current_user}")
            login_win.destroy()
            self.load_user_profile_data()

            if self.current_user == "admin" and not hasattr(self, "tab_admin"):
                self.tab_admin = self.tabview.add("🛡️ Panel Administratora")
                self.setup_admin_tab()

            self.deiconify()
            self.start_presence_updates()
            self.start_chat_realtime()
            self.start_voice_service()
            self.start_shared_config_polling()
            self.after(1500, self.check_for_updates)

        def check_login():
            if btn_login.cget("state") == "disabled":
                return
            user = entry_username.get().strip()
            pwd = entry_password.get().strip()

            if user in self.users:
                user_info = self.get_user_data(user)
                password_matches, is_legacy_password = verify_password(pwd, user_info.get("password", ""))
                if password_matches:
                    if is_legacy_password:
                        user_info["password"] = hash_password(pwd)
                    if chk_remember_login.get() == 1:
                        token = secrets.token_urlsafe(32)
                        user_info["remember_token_hash"] = hash_remember_token(token)
                        self.save_remembered_login(user, token)
                    else:
                        self.clear_remembered_login()
                    self.save_users()
                    finish_login(user, user_info)
                    return

            lbl_error.configure(text="❌ Nieprawidłowy login lub hasło!")

        btn_login = ctk.CTkButton(
            login_win, 
            text="ZALOGUJ SIĘ", 
            font=ctk.CTkFont(weight="bold"), 
            width=280,
            command=check_login
        )
        btn_login.pack(pady=15)
        btn_login.configure(state="disabled")
        ctk.CTkLabel(
            login_win,
            text=f"Wersja {APP_VERSION}",
            text_color="#94A3B8",
            font=ctk.CTkFont(size=11)
        ).pack(pady=(8, 12))

        login_win.bind("<Return>", lambda event: check_login())

        def auto_login():
            if remembered_username and remembered_token and remembered_username in self.users:
                user_info = self.get_user_data(remembered_username)
                token_hash = user_info.get("remember_token_hash", "")
                if token_hash == hash_remember_token(remembered_token):
                    finish_login(remembered_username, user_info)
                else:
                    self.clear_remembered_login()

        def enable_login():
            if login_win.winfo_exists():
                btn_login.configure(state="normal")
                login_win.after(150, auto_login)

        self.check_for_updates(silent=True, force=True, on_ready=enable_login, parent=login_win)

    # --- SYSTEM WYLOGOWANIA ---
    def close_app(self):
        self.stop_timer()
        self.stop_rest_timer()
        self.stop_presence_updates()
        self.stop_chat_realtime()
        self.stop_voice_service()
        self.stop_shared_config_polling()
        if self.reminder_job:
            self.after_cancel(self.reminder_job)
            self.reminder_job = None
        for order in self.data.get("active", []):
            order.pop("tracked_seconds", None)
        self.save_data()
        self.destroy()

    def logout(self):
        self.stop_timer()
        self.stop_rest_timer()
        self.stop_presence_updates()
        self.stop_chat_realtime()
        self.stop_voice_service()
        self.stop_shared_config_polling()
        if self.current_user:
            self.save_data()
        self.clear_remembered_login()
        self.current_user = None
        self.data = self.empty_training_data()
        self.session_timer_seconds = 0
        
        if hasattr(self, "tab_admin"):
            try:
                self.tabview.delete("🛡️ Panel Administratora")
            except Exception:
                pass
            delattr(self, "tab_admin")
            for widget_name in (
                "lbl_clock",
                "lbl_admin_session_time",
                "lbl_admin_msg",
                "users_scroll",
                "new_user_entry",
                "new_pass_entry"
            ):
                if hasattr(self, widget_name):
                    delattr(self, widget_name)

        self.show_login_dialog()

    def start_presence_updates(self):
        if not self.presence_service.enabled:
            self.refresh_online_users([])
            return
        self.stop_presence_updates()
        self.presence_tick()

    def stop_presence_updates(self):
        if self.presence_job:
            self.after_cancel(self.presence_job)
            self.presence_job = None
        username = self.current_user
        if username and self.presence_service.enabled:
            threading.Thread(target=self._remove_presence_worker, args=(username,), daemon=True).start()
        self.refresh_online_users([])

    def presence_tick(self):
        if not self.current_user or not self.presence_service.enabled:
            return
        threading.Thread(target=self._presence_worker, args=(self.current_user,), daemon=True).start()
        self.presence_job = self.after(30000, self.presence_tick)

    def _presence_worker(self, username):
        try:
            self.presence_service.heartbeat(username)
            online_presence = self.presence_service.online_presence()
        except Exception:
            online_presence = None
        self.after(0, lambda: self.update_online_presence_cache(online_presence))

    def update_online_presence_cache(self, online_presence):
        if online_presence is None:
            self.refresh_online_users(None)
            return
        self.realtime_presence_cache = online_presence
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.presence_service.ttl_seconds)
        online_users = []
        for username, last_seen in online_presence.items():
            try:
                timestamp = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                continue
            if timestamp > cutoff:
                online_users.append(username)
        self.refresh_online_users(sorted(online_users))

    def _on_cloud_realtime_change(self, payload):
        try:
            self.after(0, lambda: self.apply_cloud_realtime_change(payload))
        except tk.TclError:
            pass

    def apply_cloud_realtime_change(self, payload):
        change = payload.get("data", {})
        table = change.get("table")
        event = change.get("type")
        record = change.get("record") or {}
        old_record = change.get("old_record") or {}

        if table == "user_presence":
            presence_record = old_record if event == "DELETE" else record
            username = presence_record.get("username")
            if not username:
                return
            if event == "DELETE":
                self.realtime_presence_cache.pop(username, None)
            elif record.get("last_seen"):
                self.realtime_presence_cache[username] = record["last_seen"]
            self.update_online_presence_cache(self.realtime_presence_cache)
            return

        if table == "app_shared_config":
            shared_config = record.get("data")
            if isinstance(shared_config, dict):
                self.apply_shared_config(shared_config)
            return

        if table == "app_users":
            username = (old_record if event == "DELETE" else record).get("username")
            if not username:
                return
            if event == "DELETE":
                self.users.pop(username, None)
            else:
                user_data = record.get("data")
                if isinstance(user_data, dict):
                    self.users[username] = user_data
            save_users(USERS_FILE, self.users)
            if self.current_user == "admin" and hasattr(self, "users_scroll"):
                self.refresh_users_list()
            return

        if table != "user_training_data":
            return

        training_record = old_record if event == "DELETE" else record
        username = training_record.get("username")
        if not username:
            return
        if self.cloud_leaderboard_cache is None:
            self.cloud_leaderboard_cache = {}
        if event == "DELETE":
            self.cloud_leaderboard_cache.pop(username, None)
        else:
            cloud_data = record.get("data")
            if not isinstance(cloud_data, dict):
                return
            self.cloud_leaderboard_cache[username] = cloud_data
            if username == self.current_user:
                merged_data = merge_training_data(self.data, cloud_data)
                merged_fields = {
                    "completion_history",
                    "custom_routines",
                    "scheduled_plans",
                    "total_seconds_spent",
                    "total_minutes_spent",
                    "fatigue_score",
                    "completed_count",
                }
                for key, value in cloud_data.items():
                    if key not in merged_fields:
                        merged_data[key] = value
                if merged_data != self.data:
                    self.data = merged_data
                    self.training_data.setdefault("users", {})[username] = merged_data
                    save_training_data(DATA_FILE, self.training_data)
                    self.refresh_ui()
        self.cloud_leaderboard_cache_time = datetime.now()
        if username != self.current_user and hasattr(self, "leaderboard_list"):
            self.refresh_leaderboard()

    def _remove_presence_worker(self, username):
        try:
            self.presence_service.remove(username)
        except Exception:
            pass

    def refresh_online_users(self, online_users):
        if online_users is None:
            text = "Online: offline"
            detail = "UŻYTKOWNICY ONLINE: brak połączenia z usługą obecności"
        elif not self.presence_service.enabled:
            text = "Online: konfiguracja"
            detail = "UŻYTKOWNICY ONLINE: uzupełnij SUPABASE_URL i SUPABASE_ANON_KEY"
        else:
            visible_names = ", ".join(online_users[:3])
            if len(online_users) > 3:
                visible_names += f" +{len(online_users) - 3}"
            text = f"Online: {len(online_users)} ({visible_names or 'nikt'})"
            names = ", ".join(online_users) if online_users else "nikt"
            detail = f"UŻYTKOWNICY ONLINE ({len(online_users)}): {names}"
        self.lbl_online_users.configure(text=text)
        self.lbl_online_users_detail.configure(text=detail)

    @staticmethod
    def empty_training_data():
        return {
            "active": [],
            "custom_routines": [],
            "weekly_goals": {"workouts": 5, "minutes": 180},
            "completed_count": 0,
            "total_minutes_spent": 0,
            "total_seconds_spent": 0,
            "fatigue_score": 0,
            "completion_history": [],
            "scheduled_plans": [],
            "category_goals": {category: 5 for category in SKILL_CATEGORIES}
        }

    @staticmethod
    def get_total_seconds(training_data):
        if "total_seconds_spent" in training_data:
            return int(training_data.get("total_seconds_spent", 0))
        return int(training_data.get("total_minutes_spent", 0)) * 60

    @staticmethod
    def get_weekly_training_totals(training_data, today=None):
        today = today or datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        next_week = week_start + timedelta(days=7)
        completed_count = 0
        total_seconds = 0

        for item in training_data.get("completion_history", []):
            try:
                completed_date = datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
            except (TypeError, ValueError):
                continue
            if not week_start <= completed_date < next_week:
                continue

            completed_count += 1
            try:
                duration_seconds = int(
                    item.get("duration_seconds", int(item.get("duration", 0)) * 60)
                )
            except (TypeError, ValueError):
                duration_seconds = 0
            total_seconds += max(0, duration_seconds)

        return completed_count, total_seconds

    @staticmethod
    def parse_completion_date(item):
        try:
            return datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
        except (AttributeError, TypeError, ValueError):
            return None

    @classmethod
    def get_training_chart_data(cls, training_data, period="week", today=None):
        today = today or datetime.now().date()
        if period == "month":
            start_date = today - timedelta(days=29)
            dates = [start_date + timedelta(days=index) for index in range(30)]
            labels = [date.strftime("%d.%m") for date in dates]
        else:
            start_date = today - timedelta(days=6)
            dates = [start_date + timedelta(days=index) for index in range(7)]
            labels = [date.strftime("%a\n%d.%m") for date in dates]

        daily_seconds = defaultdict(int)
        daily_completed = defaultdict(int)
        for item in training_data.get("completion_history", []):
            completed_date = cls.parse_completion_date(item)
            if completed_date is None or not start_date <= completed_date <= today:
                continue
            daily_completed[completed_date] += 1
            try:
                duration_seconds = int(
                    item.get("duration_seconds", int(item.get("duration", 0)) * 60)
                )
            except (AttributeError, TypeError, ValueError):
                duration_seconds = 0
            daily_seconds[completed_date] += max(0, duration_seconds)

        return (
            labels,
            [daily_seconds[date] / 60 for date in dates],
            [daily_completed[date] for date in dates],
        )

    @classmethod
    def get_longest_training_streak(cls, training_data):
        completed_dates = {
            completed_date
            for item in training_data.get("completion_history", [])
            if (completed_date := cls.parse_completion_date(item)) is not None
        }
        if not completed_dates:
            return 0

        longest_streak = 0
        current_streak = 0
        previous_date = None
        for completed_date in sorted(completed_dates):
            if previous_date and completed_date == previous_date + timedelta(days=1):
                current_streak += 1
            else:
                current_streak = 1
            longest_streak = max(longest_streak, current_streak)
            previous_date = completed_date
        return longest_streak

    def get_weekly_goals(self):
        goals = self.data.get("weekly_goals", {})
        if not isinstance(goals, dict):
            goals = {}
        try:
            workout_goal = int(goals.get("workouts", 5))
        except (TypeError, ValueError):
            workout_goal = 5
        try:
            minutes_goal = int(goals.get("minutes", 180))
        except (TypeError, ValueError):
            minutes_goal = 180
        return {
            "workouts": max(1, workout_goal),
            "minutes": max(1, minutes_goal)
        }

    def load_data(self):
        return load_training_data(DATA_FILE)

    def load_user_training_data(self):
        user_data = self.training_data.setdefault("users", {}).get(self.current_user)
        if not isinstance(user_data, dict):
            user_data = self.empty_training_data()
            self.training_data["users"][self.current_user] = user_data
        self.data = user_data
        self.sync_current_user_training_data()
        self.data.setdefault("custom_routines", [])
        self.data.setdefault("scheduled_plans", [])
        self.data.setdefault("category_goals", {category: 5 for category in SKILL_CATEGORIES})
        self.data["weekly_goals"] = self.get_weekly_goals()
        for order in self.data.get("active", []):
            order.pop("tracked_seconds", None)
        self.save_data()

    def sync_current_user_training_data(self):
        if not self.cloud_data_service.enabled or not self.current_user:
            return
        try:
            cloud_data = self.cloud_data_service.get_user_data(self.current_user)
            if isinstance(cloud_data, dict):
                self.data = merge_training_data(self.data, cloud_data)
            self.training_data.setdefault("users", {})[self.current_user] = self.data
            self.cloud_data_service.save_user_data(self.current_user, self.data)
        except Exception:
            pass

    def sync_shared_config(self):
        if not self.cloud_data_service.enabled:
            return
        try:
            shared_config = self.cloud_data_service.get_shared_config()
            if isinstance(shared_config, dict):
                self.training_data["module_catalog"] = shared_config.get(
                    "module_catalog", self.training_data.get("module_catalog", [])
                )
                self.training_data["preset_protocols"] = shared_config.get(
                    "preset_protocols", self.training_data.get("preset_protocols", {})
                )
        except Exception:
            pass

    def save_shared_training_config(self):
        if not self.cloud_data_service.enabled:
            return
        try:
            self.cloud_data_service.save_shared_config({
                "module_catalog": self.training_data.get("module_catalog", []),
                "preset_protocols": self.training_data.get("preset_protocols", {})
            })
        except Exception:
            pass

    def start_shared_config_polling(self):
        if not self.cloud_data_service.enabled:
            return
        self.stop_shared_config_polling()
        self.shared_config_tick()

    def stop_shared_config_polling(self):
        if self.shared_config_job:
            self.after_cancel(self.shared_config_job)
            self.shared_config_job = None

    def shared_config_tick(self):
        if not self.current_user or not self.cloud_data_service.enabled:
            return
        threading.Thread(target=self._shared_config_worker, daemon=True).start()
        self.shared_config_job = self.after(30000, self.shared_config_tick)

    def _shared_config_worker(self):
        try:
            shared_config = self.cloud_data_service.get_shared_config()
        except Exception:
            shared_config = None
        if shared_config:
            self.after(0, lambda: self.apply_shared_config(shared_config))

    def apply_shared_config(self, shared_config):
        if not isinstance(shared_config, dict):
            return
        self.training_data["module_catalog"] = shared_config.get("module_catalog", self.training_data.get("module_catalog", []))
        self.training_data["preset_protocols"] = shared_config.get("preset_protocols", self.training_data.get("preset_protocols", {}))
        self.refresh_module_catalog()
        self.refresh_preset_protocols()
        self.refresh_planner_views()

    def get_leaderboard_training_data(self):
        if self.cloud_data_service.enabled:
            cache_is_fresh = (
                self.cloud_leaderboard_cache is not None
                and self.cloud_leaderboard_cache_time is not None
                and (datetime.now() - self.cloud_leaderboard_cache_time).total_seconds() < 30
            )
            if not cache_is_fresh:
                try:
                    self.cloud_leaderboard_cache = self.cloud_data_service.get_all_data()
                    self.cloud_leaderboard_cache_time = datetime.now()
                except Exception:
                    pass
        return self.cloud_leaderboard_cache or self.training_data.get("users", {})

    def save_data(self):
        if not self.current_user:
            return
        self.training_data.setdefault("users", {})[self.current_user] = self.data
        self.save_data_for_user(self.current_user)

    def save_data_for_user(self, username):
        self.training_data.setdefault("users", {})[username] = self.training_data["users"].get(
            username,
            self.empty_training_data()
        )
        save_training_data(DATA_FILE, self.training_data)
        if self.cloud_data_service.enabled:
            try:
                self.cloud_data_service.save_user_data(username, self.training_data["users"][username])
            except Exception:
                pass

    # --- ZAKŁADKA 1: Centrum Dowodzenia ---
    def setup_dashboard(self):
        header = ctk.CTkLabel(
            self.tab_dashboard, 
            text="CS2 TRENING E-SPORT", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        header.pack(pady=(10, 5))

        self.online_users_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="#0F172A", border_width=1, border_color="#24433F")
        self.online_users_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.lbl_online_users_detail = ctk.CTkLabel(
            self.online_users_frame,
            text="UŻYTKOWNICY ONLINE: konfiguracja obecności wymagana",
            anchor="w",
            text_color="#A7F3D0",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_online_users_detail.pack(fill="x", padx=14, pady=8)

        self.stats_summary_frame = ctk.CTkFrame(
            self.tab_dashboard,
            fg_color="#111827",
            corner_radius=12,
            border_width=1,
            border_color="#263449"
        )
        self.stats_summary_frame.pack(fill="x", padx=10, pady=5)

        summary_tiles = (
            ("lbl_plan_time", "Aktywne zlecenia: 0", "#60A5FA", "#1E3A5F"),
            ("lbl_completed", "Ukończone: 0", "#34D399", "#164A43"),
            ("lbl_fatigue", "Wskaźnik Potu: 0 XP", "#FBBF24", "#59421D"),
            ("lbl_rank", "Ranga: Silver I", "#F472B6", "#542D4A")
        )
        for attribute, text, accent, border in summary_tiles:
            tile = ctk.CTkFrame(
                self.stats_summary_frame,
                fg_color="#172338",
                corner_radius=9,
                border_width=1,
                border_color=border
            )
            tile.pack(side="left", padx=(8, 2), pady=7)
            label = ctk.CTkLabel(
                tile,
                text=text,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=accent
            )
            label.pack(padx=11, pady=9)
            setattr(self, attribute, label)

        rank_progress_frame = ctk.CTkFrame(
            self.tab_dashboard,
            fg_color="#111827",
            corner_radius=12,
            border_width=1,
            border_color="#3D3155"
        )
        rank_progress_frame.pack(fill="x", padx=10, pady=(3, 8))
        rank_progress_header = ctk.CTkFrame(rank_progress_frame, fg_color="transparent")
        rank_progress_header.pack(fill="x", padx=14, pady=(8, 4))
        self.lbl_rank_progress = ctk.CTkLabel(
            rank_progress_header,
            text="Silver I  •  Pozostało 120 XP do Silver II",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#F472B6"
        )
        self.lbl_rank_progress.pack(side="left", anchor="w")
        self.lbl_rank_percentage = ctk.CTkLabel(
            rank_progress_header,
            text="0%",
            width=52,
            height=24,
            fg_color="#2A2038",
            text_color="#F9A8D4",
            corner_radius=7,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_rank_percentage.pack(side="right")
        self.rank_progress_bar = ctk.CTkProgressBar(
            rank_progress_frame,
            height=16,
            corner_radius=8,
            progress_color="#F472B6",
            fg_color="#27354B"
        )
        self.rank_progress_bar.pack(fill="x", padx=14, pady=(0, 10))
        self.rank_progress_bar.set(0)

        self.weekly_goals_frame = ctk.CTkFrame(
            self.tab_dashboard,
            fg_color="#111827",
            corner_radius=10,
            border_width=1,
            border_color="#24433F"
        )
        self.weekly_goals_frame.pack(fill="x", padx=10, pady=(0, 8))
        weekly_header = ctk.CTkFrame(self.weekly_goals_frame, fg_color="transparent")
        weekly_header.pack(fill="x", padx=14, pady=(7, 2))
        self.lbl_weekly_goal_period = ctk.CTkLabel(
            weekly_header,
            text="CEL TYGODNIA",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#34D399"
        )
        self.lbl_weekly_goal_period.pack(side="left")
        ctk.CTkButton(
            weekly_header,
            text="Ustaw cele",
            width=92,
            height=28,
            fg_color="#24433F",
            hover_color="#315A50",
            command=self.open_weekly_goals_editor
        ).pack(side="right")

        weekly_metrics = ctk.CTkFrame(self.weekly_goals_frame, fg_color="transparent")
        weekly_metrics.pack(fill="x", padx=8, pady=(0, 8))
        workouts_frame = ctk.CTkFrame(weekly_metrics, fg_color="transparent")
        workouts_frame.pack(side="left", fill="x", expand=True, padx=6)
        minutes_frame = ctk.CTkFrame(weekly_metrics, fg_color="transparent")
        minutes_frame.pack(side="left", fill="x", expand=True, padx=6)

        self.lbl_weekly_workouts = ctk.CTkLabel(
            workouts_frame,
            text="Ukończone ćwiczenia: 0 / 5",
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#A7F3D0"
        )
        self.lbl_weekly_workouts.pack(fill="x", pady=(2, 3))
        self.weekly_workouts_bar = ctk.CTkProgressBar(
            workouts_frame,
            height=10,
            corner_radius=5,
            progress_color="#34D399",
            fg_color="#263B3A"
        )
        self.weekly_workouts_bar.pack(fill="x")

        self.lbl_weekly_minutes = ctk.CTkLabel(
            minutes_frame,
            text="Czas treningu: 0 / 180 min",
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#93C5FD"
        )
        self.lbl_weekly_minutes.pack(fill="x", pady=(2, 3))
        self.weekly_minutes_bar = ctk.CTkProgressBar(
            minutes_frame,
            height=10,
            corner_radius=5,
            progress_color="#60A5FA",
            fg_color="#26364A"
        )
        self.weekly_minutes_bar.pack(fill="x")
        self.refresh_weekly_goals()

        self.streak_frame = ctk.CTkFrame(
            self.tab_dashboard,
            fg_color="#111827",
            corner_radius=10,
            border_width=1,
            border_color="#5B3A1D"
        )
        self.streak_frame.pack(fill="x", padx=10, pady=(0, 8))
        streak_header = ctk.CTkFrame(self.streak_frame, fg_color="transparent")
        streak_header.pack(fill="x", padx=14, pady=(8, 2))
        ctk.CTkLabel(
            streak_header,
            text="SERIA TRENINGOWA",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#FBBF24"
        ).pack(side="left")
        self.lbl_streak_count = ctk.CTkLabel(
            streak_header,
            text="0 dni z rzędu",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#FDE68A"
        )
        self.lbl_streak_count.pack(side="right")
        self.lbl_streak_status = ctk.CTkLabel(
            self.streak_frame,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color="#CBD5E1"
        )
        self.lbl_streak_status.pack(fill="x", padx=14, pady=(0, 4))
        self.lbl_badges = ctk.CTkLabel(
            self.streak_frame,
            text="Odznaki: brak",
            anchor="w",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FBBF24"
        )
        self.lbl_badges.pack(fill="x", padx=14, pady=(0, 8))
        self.refresh_streaks()

        self.lbl_session_timer = ctk.CTkLabel(
            self.stats_summary_frame, 
            text="⏱️ AKTYWNY TRENING  00:00", 
            font=ctk.CTkFont(size=20, weight="bold"), 
            text_color="#FF4D5A",
            fg_color="#111827",
            corner_radius=10,
            width=310,
            height=54
        )
        self.lbl_session_timer.pack(side="right", padx=15, pady=8)

        rest_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", border_width=1, border_color="#24433F")
        rest_frame.pack(fill="x", padx=10, pady=(0, 8))
        ctk.CTkLabel(rest_frame, text="PRZERWA REGENERACYJNA", text_color="#34D399", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=14, pady=8)
        self.rest_duration_menu = ctk.CTkOptionMenu(rest_frame, values=["5 minut", "10 minut", "15 minut"], width=105)
        self.rest_duration_menu.set("10 minut")
        self.rest_duration_menu.pack(side="left", padx=5, pady=6)
        self.lbl_rest_timer = ctk.CTkLabel(rest_frame, text="00:00", width=70, text_color="#A7F3D0", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_rest_timer.pack(side="left", padx=8)
        self.btn_rest_timer = ctk.CTkButton(rest_frame, text="Start przerwy", width=115, fg_color="#059669", hover_color="#047857", command=self.start_rest_timer)
        self.btn_rest_timer.pack(side="left", padx=5, pady=6)
        ctk.CTkButton(rest_frame, text="Reset", width=65, fg_color="#334155", hover_color="#475569", command=self.reset_rest_timer).pack(side="left", padx=5, pady=6)

        form_frame = ctk.CTkFrame(self.tab_dashboard)
        form_frame.pack(fill="x", padx=10, pady=10)
        self.module_form_frame = form_frame

        ctk.CTkLabel(form_frame, text="Moduł:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10)
        self.entry_custom_type = ctk.CTkOptionMenu(
            form_frame, 
            values=[item["name"] for item in self.get_module_catalog()],
            width=260
        )
        self.entry_custom_type.grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(form_frame, text="Kategoria:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=10, pady=10)
        self.entry_custom_category = ctk.CTkOptionMenu(
            form_frame,
            values=list(SKILL_CATEGORIES),
            width=150
        )
        self.entry_custom_category.grid(row=0, column=3, padx=10, pady=10)

        btn_add = ctk.CTkButton(form_frame, text="+ Dodaj Moduł", command=self.add_custom_order, font=ctk.CTkFont(weight="bold"))
        btn_add.grid(row=0, column=4, padx=15, pady=10)
        self.btn_add_module = btn_add
        self.entry_custom_type.configure(command=self.sync_selected_module_category)
        self.refresh_module_catalog()

        self.orders_scroll = ctk.CTkScrollableFrame(self.tab_dashboard, label_text="Aktualny Plan Treningowy (Kliknij START przy module)")
        self.orders_scroll.pack(fill="both", expand=True, padx=10, pady=10)

    def sync_selected_module_category(self, selected_name=None):
        selected_name = selected_name or self.entry_custom_type.get()
        for item in self.get_module_catalog():
            if item["name"] == selected_name:
                self.entry_custom_category.set(item["category"])
                return

    def refresh_weekly_goals(self):
        if not hasattr(self, "weekly_workouts_bar"):
            return

        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        goals = self.get_weekly_goals()
        completed_count, total_seconds = self.get_weekly_training_totals(self.data, today)
        completed_minutes = total_seconds // 60

        self.lbl_weekly_goal_period.configure(
            text=f"CEL TYGODNIA · {week_start:%d.%m}–{week_end:%d.%m}"
        )
        self.lbl_weekly_workouts.configure(
            text=f"Ukończone ćwiczenia: {completed_count} / {goals['workouts']}"
        )
        self.weekly_workouts_bar.set(min(1.0, completed_count / goals["workouts"]))
        self.lbl_weekly_minutes.configure(
            text=f"Czas treningu: {completed_minutes} / {goals['minutes']} min"
        )
        self.weekly_minutes_bar.set(
            min(1.0, total_seconds / (goals["minutes"] * 60))
        )

    @classmethod
    def get_training_dates(cls, training_data):
        return {
            completed_date
            for item in training_data.get("completion_history", [])
            if (completed_date := cls.parse_completion_date(item)) is not None
        }

    @classmethod
    def get_current_training_streak(cls, training_data, today=None):
        today = today or datetime.now().date()
        training_dates = cls.get_training_dates(training_data)
        if not training_dates:
            return 0

        streak_end = today if today in training_dates else today - timedelta(days=1)
        if streak_end not in training_dates:
            return 0

        streak = 0
        while streak_end - timedelta(days=streak) in training_dates:
            streak += 1
        return streak

    @classmethod
    def get_training_badges(cls, training_data):
        longest_streak = cls.get_longest_training_streak(training_data)
        badges = []
        for required_days, badge_name in (
            (3, "🔥 3 dni regularności"),
            (7, "🏅 7 dni regularności"),
            (14, "💪 14 dni regularności"),
            (30, "👑 30 dni regularności")
        ):
            if longest_streak >= required_days:
                badges.append(badge_name)
        return badges

    def refresh_streaks(self):
        if not hasattr(self, "lbl_streak_count"):
            return

        today = datetime.now().date()
        training_dates = self.get_training_dates(self.data)
        current_streak = self.get_current_training_streak(self.data, today)
        longest_streak = self.get_longest_training_streak(self.data)
        badges = self.get_training_badges(self.data)

        self.lbl_streak_count.configure(text=f"{current_streak} dni z rzędu")
        if training_dates and max(training_dates) < today - timedelta(days=1):
            last_training = max(training_dates).strftime("%d.%m.%Y")
            self.lbl_streak_status.configure(
                text=f"⚠️ Seria przerwana. Ostatni trening: {last_training}. Zacznij dziś, aby zbudować nową serię.",
                text_color="#FCA5A5"
            )
        elif current_streak:
            self.lbl_streak_status.configure(
                text=f"Najdłuższa seria: {longest_streak} dni. Utrzymaj regularność także jutro!",
                text_color="#A7F3D0"
            )
        else:
            self.lbl_streak_status.configure(
                text="Nie masz jeszcze aktywnej serii. Ukończ trening dzisiaj, aby zacząć.",
                text_color="#CBD5E1"
            )

        self.lbl_badges.configure(
            text="Odznaki: " + ("  •  ".join(badges) if badges else "brak — pierwsza odznaka po 3 dniach")
        )

    def open_weekly_goals_editor(self):
        goals = self.get_weekly_goals()
        editor = ctk.CTkToplevel(self)
        editor.title("Cele tygodniowe")
        editor.geometry("420x330")
        editor.resizable(False, False)
        editor.transient(self)
        editor.grab_set()

        ctk.CTkLabel(
            editor,
            text="USTAW CELE TYGODNIOWE",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#34D399"
        ).pack(anchor="w", padx=24, pady=(22, 14))
        ctk.CTkLabel(
            editor,
            text="Liczba ukończonych ćwiczeń",
            anchor="w"
        ).pack(fill="x", padx=24)
        workouts_entry = ctk.CTkEntry(editor)
        workouts_entry.pack(fill="x", padx=24, pady=(4, 12))
        workouts_entry.insert(0, str(goals["workouts"]))

        ctk.CTkLabel(
            editor,
            text="Łączny czas treningu (minuty)",
            anchor="w"
        ).pack(fill="x", padx=24)
        minutes_entry = ctk.CTkEntry(editor)
        minutes_entry.pack(fill="x", padx=24, pady=(4, 14))
        minutes_entry.insert(0, str(goals["minutes"]))

        def save_weekly_goals():
            try:
                workouts_goal = int(workouts_entry.get().strip())
                minutes_goal = int(minutes_entry.get().strip())
            except ValueError:
                messagebox.showerror(
                    "Nieprawidłowe cele",
                    "Wpisz całkowitą liczbę ćwiczeń i minut.",
                    parent=editor
                )
                return

            if not 1 <= workouts_goal <= 100 or not 1 <= minutes_goal <= 10080:
                messagebox.showerror(
                    "Nieprawidłowe cele",
                    "Cel ćwiczeń musi wynosić 1–100, a czas 1–10080 minut.",
                    parent=editor
                )
                return

            self.data["weekly_goals"] = {
                "workouts": workouts_goal,
                "minutes": minutes_goal
            }
            self.save_data()
            self.refresh_weekly_goals()
            editor.destroy()

        footer = ctk.CTkFrame(editor, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(4, 18))
        ctk.CTkButton(
            footer,
            text="Anuluj",
            fg_color="#334155",
            hover_color="#475569",
            command=editor.destroy
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            footer,
            text="Zapisz cele",
            font=ctk.CTkFont(weight="bold"),
            command=save_weekly_goals
        ).pack(side="right")

    # --- ZAKŁADKA 2: Gotowe Rutyny Pro ---
    def setup_presets(self):
        header = ctk.CTkLabel(self.tab_presets, text="GOTOWE PROTOKOŁY E-SPORTOWE", font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(pady=15)

        self.custom_routines_section = ctk.CTkFrame(
            self.tab_presets,
            fg_color="#111827",
            corner_radius=10,
            border_width=1,
            border_color="#263449"
        )
        self.custom_routines_section.pack(fill="x", padx=15, pady=(0, 10))
        custom_routines_header = ctk.CTkFrame(self.custom_routines_section, fg_color="transparent")
        custom_routines_header.pack(fill="x", padx=14, pady=(10, 4))
        ctk.CTkLabel(
            custom_routines_header,
            text="MOJE RUTYNY",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#34D399"
        ).pack(side="left")
        ctk.CTkButton(
            custom_routines_header,
            text="+ Utwórz rutynę",
            width=145,
            font=ctk.CTkFont(weight="bold"),
            command=self.open_routine_editor
        ).pack(side="right")
        self.btn_create_routine = custom_routines_header.winfo_children()[-1]
        self.custom_routines_list = ctk.CTkScrollableFrame(
            self.custom_routines_section,
            height=180,
            fg_color="transparent"
        )
        self.custom_routines_list.pack(fill="x", padx=10, pady=(2, 10))
        self.refresh_custom_routines()

        self.preset_load_buttons = []
        self.preset_protocols_section = ctk.CTkFrame(self.tab_presets, fg_color="transparent")
        self.preset_protocols_section.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        self.refresh_preset_protocols()

    def get_preset_protocols(self):
        protocols = self.training_data.get("preset_protocols", {})
        if not isinstance(protocols, dict) or not protocols:
            protocols = {
                name: [dict(task) for task in tasks]
                for name, tasks in PRESET_PROTOCOLS.items()
            }
        return protocols

    def refresh_preset_protocols(self):
        for widget in self.preset_protocols_section.winfo_children():
            widget.destroy()
        self.preset_load_buttons.clear()
        protocols = self.get_preset_protocols()
        header = ctk.CTkFrame(self.preset_protocols_section, fg_color="#111827")
        header.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(header, text="STANDARDOWE RUTYNY PRO", text_color="#A78BFA", font=ctk.CTkFont(size=15, weight="bold")).pack(side="left", padx=12, pady=8)
        if self.can_manage_modules():
            ctk.CTkButton(header, text="+ Dodaj rutynę", width=120, command=self.open_preset_editor).pack(side="right", padx=8, pady=5)
        for preset_name, tasks in protocols.items():
            card = ctk.CTkFrame(self.preset_protocols_section)
            card.pack(fill="x", pady=5)
            ctk.CTkLabel(card, text=preset_name, font=ctk.CTkFont(size=16, weight="bold"), text_color="#3B82F6").pack(anchor="w", padx=15, pady=(10, 5))
            desc_text = " • " + "\n • ".join([f"{t['type']} ({t['duration']} min)" for t in tasks])
            ctk.CTkLabel(card, text=desc_text, justify="left", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=15, pady=5)
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(anchor="e", padx=15, pady=10)
            ctk.CTkButton(actions, text="Załaduj", fg_color="#8B5CF6", hover_color="#7C3AED", command=lambda p=tasks: self.load_preset_protocol(p)).pack(side="left", padx=3)
            if self.can_manage_modules():
                ctk.CTkButton(actions, text="Edytuj", width=70, fg_color="#334155", command=lambda n=preset_name: self.open_preset_editor(n)).pack(side="left", padx=3)
                ctk.CTkButton(actions, text="Usuń", width=62, fg_color="#991B1B", hover_color="#B91C1C", command=lambda n=preset_name: self.delete_preset_protocol(n)).pack(side="left", padx=3)
            self.preset_load_buttons.append(actions.winfo_children()[0])

    def open_preset_editor(self, preset_name=None):
        if not self.can_manage_modules():
            self.show_module_permission_error()
            return
        protocols = self.get_preset_protocols()
        existing = protocols.get(preset_name, [])
        editor = ctk.CTkToplevel(self)
        editor.title("Edytuj rutynę Pro" if preset_name else "Nowa rutyna Pro")
        editor.geometry("650x520")
        editor.transient(self)
        editor.grab_set()
        ctk.CTkLabel(editor, text="RUTYNA PRO", font=ctk.CTkFont(size=20, weight="bold"), text_color="#A78BFA").pack(anchor="w", padx=22, pady=(18, 8))
        ctk.CTkLabel(editor, text="Nazwa rutyny", anchor="w").pack(fill="x", padx=22)
        name_entry = ctk.CTkEntry(editor)
        name_entry.pack(fill="x", padx=22, pady=(4, 12))
        name_entry.insert(0, preset_name or "")
        ctk.CTkLabel(editor, text="Ćwiczenia: jedno na linię w formacie nazwa | minuty", anchor="w").pack(fill="x", padx=22)
        tasks_box = ctk.CTkTextbox(editor, height=250)
        tasks_box.pack(fill="both", expand=True, padx=22, pady=(4, 12))
        tasks_box.insert("1.0", "\n".join(f"{task.get('type', '')} | {task.get('duration', 10)}" for task in existing))

        def save_preset():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Brak nazwy", "Podaj nazwę rutyny.", parent=editor)
                return
            tasks = []
            for line_number, line in enumerate(tasks_box.get("1.0", "end").splitlines(), start=1):
                if not line.strip():
                    continue
                parts = line.rsplit("|", 1)
                if len(parts) != 2 or not parts[0].strip():
                    messagebox.showerror("Nieprawidłowe ćwiczenie", f"Linia {line_number} musi mieć format: nazwa | minuty.", parent=editor)
                    return
                try:
                    duration = int(parts[1].strip())
                except ValueError:
                    messagebox.showerror("Nieprawidłowy czas", f"Czas w linii {line_number} musi być liczbą minut.", parent=editor)
                    return
                if not 1 <= duration <= 600:
                    messagebox.showerror("Nieprawidłowy czas", "Czas ćwiczenia musi wynosić 1–600 minut.", parent=editor)
                    return
                tasks.append({"type": parts[0].strip(), "duration": duration})
            if not tasks:
                messagebox.showerror("Brak ćwiczeń", "Dodaj co najmniej jedno ćwiczenie.", parent=editor)
                return
            if name != preset_name and name in protocols:
                messagebox.showerror("Duplikat", "Rutyna o tej nazwie już istnieje.", parent=editor)
                return
            if preset_name and preset_name != name:
                protocols.pop(preset_name, None)
            protocols[name] = tasks
            self.training_data["preset_protocols"] = protocols
            self.save_shared_training_config()
            self.save_data_for_user(self.current_user)
            self.refresh_preset_protocols()
            editor.destroy()

        footer = ctk.CTkFrame(editor, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=(0, 16))
        ctk.CTkButton(footer, text="Anuluj", fg_color="#334155", command=editor.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Zapisz rutynę", fg_color="#7C3AED", hover_color="#6D28D9", command=save_preset).pack(side="right")

    def delete_preset_protocol(self, preset_name):
        if not self.can_manage_modules():
            self.show_module_permission_error()
            return
        if not messagebox.askyesno("Usuń rutynę", f"Usunąć rutynę '{preset_name}' dla wszystkich graczy?", parent=self):
            return
        protocols = self.get_preset_protocols()
        protocols.pop(preset_name, None)
        self.training_data["preset_protocols"] = protocols
        self.save_shared_training_config()
        self.save_data_for_user(self.current_user)
        self.refresh_preset_protocols()

    def refresh_custom_routines(self):
        if hasattr(self, "btn_create_routine"):
            self.btn_create_routine.configure(state="normal")
        for widget in self.custom_routines_list.winfo_children():
            widget.destroy()

        routines = self.data.get("custom_routines", [])
        if not routines:
            ctk.CTkLabel(
                self.custom_routines_list,
                text="Nie masz jeszcze własnych rutyn.",
                text_color="#94A3B8",
                font=ctk.CTkFont(size=12)
            ).pack(anchor="w", padx=6, pady=7)
            return

        for index, routine in enumerate(routines):
            tasks = routine.get("tasks", [])
            total_minutes = sum(int(task.get("duration", 0)) for task in tasks)
            card = ctk.CTkFrame(
                self.custom_routines_list,
                fg_color="#172338",
                corner_radius=8,
                border_width=1,
                border_color="#34445D"
            )
            card.pack(fill="x", padx=3, pady=3)

            ctk.CTkLabel(
                card,
                text=routine.get("name", "Własna rutyna"),
                font=ctk.CTkFont(size=14, weight="bold"),
                anchor="w"
            ).pack(side="left", fill="x", expand=True, padx=12, pady=10)

            ctk.CTkButton(
                card,
                text="Załaduj",
                width=82,
                fg_color="#059669",
                hover_color="#047857",
                command=lambda routine_index=index: self.load_custom_routine(routine_index)
            ).pack(side="right", padx=(4, 8), pady=7)
            ctk.CTkButton(
                card,
                text="Edytuj",
                width=70,
                fg_color="#334155",
                hover_color="#475569",
                command=lambda routine_index=index: self.open_routine_editor(routine_index)
            ).pack(side="right", padx=4, pady=7)
            ctk.CTkButton(
                card,
                text="Usuń",
                width=62,
                fg_color="#991B1B",
                hover_color="#B91C1C",
                command=lambda routine_index=index: self.delete_custom_routine(routine_index)
            ).pack(side="right", padx=4, pady=7)
            ctk.CTkLabel(
                card,
                text=f"{len(tasks)} ćw. · {total_minutes} min",
                width=110,
                text_color="#94A3B8",
                font=ctk.CTkFont(size=12)
            ).pack(side="right", padx=8, pady=7)

    def open_routine_editor(self, routine_index=None):
        routines = self.data.setdefault("custom_routines", [])
        if routine_index is not None and not 0 <= routine_index < len(routines):
            return

        routine = routines[routine_index] if routine_index is not None else {
            "name": "",
            "tasks": [{"type": "", "duration": 10}]
        }
        editor = ctk.CTkToplevel(self)
        editor.title("Edytuj rutynę" if routine_index is not None else "Nowa rutyna")
        editor.geometry("720x640")
        editor.minsize(620, 500)
        editor.transient(self)
        editor.grab_set()

        ctk.CTkLabel(
            editor,
            text="WŁASNA RUTYNA",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#34D399"
        ).pack(anchor="w", padx=22, pady=(18, 8))
        ctk.CTkLabel(editor, text="Nazwa rutyny", anchor="w").pack(fill="x", padx=22)
        name_entry = ctk.CTkEntry(editor, placeholder_text="Np. Rozgrzewka przed meczem")
        name_entry.pack(fill="x", padx=22, pady=(4, 12))
        name_entry.insert(0, routine.get("name", ""))

        ctk.CTkLabel(
            editor,
            text="Ćwiczenia w kolejności wykonywania",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        ).pack(fill="x", padx=22, pady=(0, 5))
        tasks_frame = ctk.CTkScrollableFrame(editor, height=360, fg_color="#111827")
        tasks_frame.pack(fill="both", expand=True, padx=22, pady=(0, 8))

        task_rows = []

        def read_task_rows():
            return [
                {"type": row["name"].get().strip(), "duration": row["duration"].get().strip()}
                for row in task_rows
            ]

        def render_task_rows(tasks):
            for widget in tasks_frame.winfo_children():
                widget.destroy()
            task_rows.clear()

            for index, task in enumerate(tasks):
                row_frame = ctk.CTkFrame(tasks_frame, fg_color="#172338", corner_radius=7)
                row_frame.pack(fill="x", padx=3, pady=3)
                name_entry_row = ctk.CTkEntry(row_frame, placeholder_text="Nazwa ćwiczenia")
                name_entry_row.pack(side="left", fill="x", expand=True, padx=(8, 6), pady=7)
                name_entry_row.insert(0, task.get("type", ""))
                duration_entry = ctk.CTkEntry(row_frame, width=64, justify="center")
                duration_entry.pack(side="left", padx=4, pady=7)
                duration_entry.insert(0, str(task.get("duration", 10)))
                ctk.CTkLabel(row_frame, text="min", text_color="#94A3B8").pack(side="left", padx=(0, 6))
                ctk.CTkButton(
                    row_frame,
                    text="↑",
                    width=32,
                    command=lambda row_index=index: move_task_row(row_index, -1)
                ).pack(side="left", padx=2, pady=7)
                ctk.CTkButton(
                    row_frame,
                    text="↓",
                    width=32,
                    command=lambda row_index=index: move_task_row(row_index, 1)
                ).pack(side="left", padx=2, pady=7)
                ctk.CTkButton(
                    row_frame,
                    text="×",
                    width=32,
                    fg_color="#991B1B",
                    hover_color="#B91C1C",
                    command=lambda row_index=index: remove_task_row(row_index)
                ).pack(side="left", padx=(2, 7), pady=7)
                task_rows.append({"name": name_entry_row, "duration": duration_entry})

        def move_task_row(index, offset):
            tasks = read_task_rows()
            destination = index + offset
            if 0 <= destination < len(tasks):
                tasks[index], tasks[destination] = tasks[destination], tasks[index]
                render_task_rows(tasks)

        def remove_task_row(index):
            tasks = read_task_rows()
            del tasks[index]
            render_task_rows(tasks)

        def add_task_row():
            tasks = read_task_rows()
            tasks.append({"type": "", "duration": "10"})
            render_task_rows(tasks)
            task_rows[-1]["name"].focus_set()

        def save_routine():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Brak nazwy", "Podaj nazwę rutyny.", parent=editor)
                return

            tasks = []
            for index, task in enumerate(read_task_rows(), start=1):
                if not task["type"]:
                    messagebox.showerror("Brak ćwiczenia", f"Uzupełnij nazwę ćwiczenia {index}.", parent=editor)
                    return
                try:
                    duration = int(task["duration"])
                except ValueError:
                    messagebox.showerror("Nieprawidłowy czas", f"Czas ćwiczenia {index} musi być liczbą minut.", parent=editor)
                    return
                if duration < 1 or duration > 600:
                    messagebox.showerror("Nieprawidłowy czas", "Czas ćwiczenia musi wynosić od 1 do 600 minut.", parent=editor)
                    return
                tasks.append({"type": task["type"], "duration": duration})

            if not tasks:
                messagebox.showerror("Brak ćwiczeń", "Dodaj co najmniej jedno ćwiczenie.", parent=editor)
                return

            saved_routine = {"name": name, "tasks": tasks}
            if routine_index is None:
                routines.append(saved_routine)
            else:
                routines[routine_index] = saved_routine
            self.save_data()
            self.refresh_custom_routines()
            if hasattr(self, "planner_routine_menu"):
                self.refresh_planner_routine_options()
            editor.destroy()

        render_task_rows(routine.get("tasks", []))
        ctk.CTkButton(
            editor,
            text="+ Dodaj ćwiczenie",
            fg_color="#334155",
            hover_color="#475569",
            command=add_task_row
        ).pack(anchor="w", padx=22, pady=(0, 8))
        footer = ctk.CTkFrame(editor, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=(0, 16))
        ctk.CTkButton(footer, text="Anuluj", fg_color="#334155", hover_color="#475569", command=editor.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Zapisz rutynę", font=ctk.CTkFont(weight="bold"), command=save_routine).pack(side="right")

    def load_custom_routine(self, routine_index):
        routines = self.data.get("custom_routines", [])
        if 0 <= routine_index < len(routines):
            self.load_preset_protocol(routines[routine_index].get("tasks", []))

    def delete_custom_routine(self, routine_index):
        routines = self.data.get("custom_routines", [])
        if not 0 <= routine_index < len(routines):
            return
        routine_name = routines[routine_index].get("name", "Własna rutyna")
        if not messagebox.askyesno(
            "Usuń rutynę",
            f"Czy usunąć rutynę '{routine_name}'?",
            parent=self
        ):
            return
        del routines[routine_index]
        self.save_data()
        self.refresh_custom_routines()
        if hasattr(self, "planner_routine_menu"):
            self.refresh_planner_routine_options()

    # --- PLAN TRENINGOWY ---
    def setup_planner_tab(self):
        ctk.CTkLabel(
            self.tab_planner,
            text="PLAN TRENINGOWY",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(pady=(15, 5))
        ctk.CTkLabel(
            self.tab_planner,
            text="Przypisz rutynę do konkretnego dnia i kontroluj jej realizację.",
            text_color="#94A3B8"
        ).pack(pady=(0, 12))

        planner_form = ctk.CTkFrame(self.tab_planner, fg_color="#0F172A")
        planner_form.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(planner_form, text="Data (RRRR-MM-DD)", anchor="w").grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")
        self.planner_date_entry = ctk.CTkEntry(planner_form, width=145)
        self.planner_date_entry.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="w")
        self.planner_date_entry.insert(0, datetime.now().date().isoformat())
        ctk.CTkLabel(planner_form, text="Rutyna", anchor="w").grid(row=0, column=1, padx=12, pady=(12, 4), sticky="w")
        self.planner_routine_menu = ctk.CTkOptionMenu(planner_form, values=["Brak rutyn"], width=340)
        self.planner_routine_menu.grid(row=1, column=1, padx=12, pady=(0, 12), sticky="w")
        ctk.CTkLabel(planner_form, text="Godzina (HH:MM)", anchor="w").grid(row=0, column=2, padx=12, pady=(12, 4), sticky="w")
        self.planner_time_entry = ctk.CTkEntry(planner_form, width=95, placeholder_text="18:00")
        self.planner_time_entry.grid(row=1, column=2, padx=12, pady=(0, 12), sticky="w")
        self.planner_time_entry.insert(0, "18:00")
        self.planner_reminder_enabled = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(planner_form, text="Przypomnij", variable=self.planner_reminder_enabled).grid(row=1, column=3, padx=8, pady=(0, 12), sticky="w")
        ctk.CTkButton(
            planner_form,
            text="+ Zaplanuj rutynę",
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(weight="bold"),
            command=self.schedule_routine
        ).grid(row=1, column=4, padx=12, pady=(0, 12), sticky="w")
        self.refresh_planner_routine_options()

        self.planner_month = datetime.now().date().replace(day=1)
        calendar_card = ctk.CTkFrame(self.tab_planner, fg_color="#0F172A")
        calendar_card.pack(fill="x", padx=20, pady=(0, 12))
        calendar_header = ctk.CTkFrame(calendar_card, fg_color="transparent")
        calendar_header.pack(fill="x", padx=12, pady=(10, 5))
        ctk.CTkButton(calendar_header, text="‹", width=36, command=lambda: self.change_planner_month(-1)).pack(side="left")
        self.lbl_planner_month = ctk.CTkLabel(calendar_header, text="", font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_planner_month.pack(side="left", expand=True)
        ctk.CTkButton(calendar_header, text="›", width=36, command=lambda: self.change_planner_month(1)).pack(side="right")
        self.planner_calendar_body = ctk.CTkFrame(calendar_card, fg_color="transparent")
        self.planner_calendar_body.pack(fill="x", padx=12, pady=(0, 12))

        self.planner_list = ctk.CTkScrollableFrame(self.tab_planner, label_text="ZAPLANOWANE SESJE")
        self.planner_list.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self.refresh_planner_views()

    def refresh_planner_routine_options(self):
        routine_map = {}
        for routine_name, tasks in self.get_preset_protocols().items():
            routine_map[routine_name] = tasks
        for routine in self.data.get("custom_routines", []):
            routine_name = routine.get("name", "Własna rutyna")
            routine_map[routine_name] = routine.get("tasks", [])
        self.planner_routine_map = routine_map
        values = list(routine_map) or ["Brak rutyn"]
        self.planner_routine_menu.configure(values=values)
        self.planner_routine_menu.set(values[0])

    def refresh_planner_views(self):
        if not hasattr(self, "planner_calendar_body"):
            return
        self.refresh_planner_routine_options()
        self.refresh_planner_calendar()
        self.refresh_planner_list()

    def select_planner_date(self, selected_date):
        self.planner_date_entry.delete(0, "end")
        self.planner_date_entry.insert(0, selected_date.isoformat())
        self.refresh_planner_calendar()

    def change_planner_month(self, offset):
        month = self.planner_month.month - 1 + offset
        year = self.planner_month.year + month // 12
        month = month % 12 + 1
        self.planner_month = self.planner_month.replace(year=year, month=month, day=1)
        self.refresh_planner_calendar()

    def refresh_planner_calendar(self):
        for widget in self.planner_calendar_body.winfo_children():
            widget.destroy()

        month_names = ("Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień")
        self.lbl_planner_month.configure(text=f"{month_names[self.planner_month.month - 1]} {self.planner_month.year}")
        weekdays = ("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd")
        for column, weekday in enumerate(weekdays):
            ctk.CTkLabel(self.planner_calendar_body, text=weekday, text_color="#94A3B8", font=ctk.CTkFont(weight="bold")).grid(row=0, column=column, padx=4, pady=4)

        plans_by_date = defaultdict(list)
        for plan in self.data.get("scheduled_plans", []):
            plans_by_date[plan.get("date", "")].append(plan)
        first_weekday = self.planner_month.weekday()
        next_month = (self.planner_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        days_in_month = (next_month - self.planner_month).days
        try:
            selected_date = datetime.strptime(self.planner_date_entry.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            selected_date = None
        for day in range(1, days_in_month + 1):
            selected = self.planner_month.replace(day=day)
            plans = plans_by_date.get(selected.isoformat(), [])
            if any(plan.get("status") == "completed" for plan in plans):
                color = "#047857"
            elif any(plan.get("status") == "started" for plan in plans):
                color = "#B45309"
            elif plans:
                color = "#1D4ED8"
            else:
                color = "#1E293B"
            button = ctk.CTkButton(
                self.planner_calendar_body,
                text=f"{day}\n{len(plans)} planów" if plans else str(day),
                width=92,
                height=45,
                fg_color=color,
                hover_color="#334155",
                border_width=2 if selected_date == selected else 0,
                border_color="#FBBF24",
                command=lambda selected_day=selected: self.select_planner_date(selected_day)
            )
            position = first_weekday + day - 1
            button.grid(row=position // 7 + 1, column=position % 7, padx=3, pady=3, sticky="ew")

    def schedule_routine(self):
        try:
            selected_date = datetime.strptime(self.planner_date_entry.get().strip(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Nieprawidłowa data", "Wpisz datę w formacie RRRR-MM-DD.", parent=self)
            return
        selected_time = self.planner_time_entry.get().strip()
        try:
            datetime.strptime(selected_time, "%H:%M")
        except ValueError:
            messagebox.showerror("Nieprawidłowa godzina", "Wpisz godzinę w formacie HH:MM, np. 18:00.", parent=self)
            return
        routine_name = self.planner_routine_menu.get()
        tasks = self.planner_routine_map.get(routine_name)
        if not tasks:
            messagebox.showerror("Brak rutyny", "Najpierw utwórz lub wybierz rutynę.", parent=self)
            return
        self.data.setdefault("scheduled_plans", []).append({
            "date": selected_date.isoformat(),
            "routine_name": routine_name,
            "tasks": [dict(task) for task in tasks],
            "status": "planned",
            "plan_id": secrets.token_hex(8),
            "time": selected_time,
            "reminder_enabled": bool(self.planner_reminder_enabled.get()),
            "reminder_notified": False
        })
        self.save_data()
        self.refresh_planner_views()

    def update_scheduled_plan_status(self, plan_index, status):
        plans = self.data.get("scheduled_plans", [])
        if not 0 <= plan_index < len(plans):
            return
        plans[plan_index]["status"] = status
        self.save_data()
        self.refresh_planner_views()

    def start_scheduled_plan(self, plan_index):
        plans = self.data.get("scheduled_plans", [])
        if not 0 <= plan_index < len(plans):
            return
        plan = plans[plan_index]
        if plan.get("status") == "completed":
            return
        plan_id = plan.setdefault("plan_id", secrets.token_hex(8))
        if not any(task.get("scheduled_plan_id") == plan_id for task in self.data.get("active", [])):
            for task in plan.get("tasks", []):
                active_task = dict(task)
                active_task["scheduled_plan_id"] = plan_id
                self.data["active"].append(active_task)
        plan["status"] = "started"
        self.save_data()
        self.refresh_ui()
        self.tabview.set("⚡ Centrum Dowodzenia")

    def open_scheduled_plan_training(self, plan_index):
        plans = self.data.get("scheduled_plans", [])
        if 0 <= plan_index < len(plans):
            self.tabview.set("⚡ Centrum Dowodzenia")

    def check_training_reminders(self):
        if not self.current_user:
            self.reminder_job = self.after(30000, self.check_training_reminders)
            return
        now = datetime.now()
        for plan in self.data.get("scheduled_plans", []):
            if plan.get("status") != "planned" or not plan.get("reminder_enabled", False) or plan.get("reminder_notified"):
                continue
            if plan.get("date") != now.date().isoformat() or plan.get("time") != now.strftime("%H:%M"):
                continue
            plan["reminder_notified"] = True
            self.save_data()
            self.show_training_reminder(plan.get("routine_name", "Trening"))
        self.reminder_job = self.after(30000, self.check_training_reminders)

    def show_training_reminder(self, routine_name):
        if self.reminder_window is not None and self.reminder_window.winfo_exists():
            self.reminder_window.destroy()

        reminder = ctk.CTkToplevel(self)
        self.reminder_window = reminder
        reminder.title("Przypomnienie o treningu")
        reminder.geometry("380x165")
        reminder.resizable(False, False)
        reminder.attributes("-topmost", True)
        reminder.protocol("WM_DELETE_WINDOW", reminder.destroy)
        reminder.update_idletasks()
        x = reminder.winfo_screenwidth() - reminder.winfo_width() - 24
        y = 55
        reminder.geometry(f"+{x}+{y}")

        ctk.CTkLabel(
            reminder,
            text="CZAS NA TRENING",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#34D399"
        ).pack(pady=(16, 4))
        ctk.CTkLabel(
            reminder,
            text=routine_name,
            font=ctk.CTkFont(size=13, weight="bold"),
            wraplength=330
        ).pack(padx=15, pady=3)
        ctk.CTkButton(
            reminder,
            text="Otwórz plan treningowy",
            width=190,
            command=lambda: self.open_planner_from_reminder(reminder)
        ).pack(pady=(8, 14))

    def open_planner_from_reminder(self, reminder):
        if reminder.winfo_exists():
            reminder.destroy()
        self.tabview.set("📅 Plan treningowy")

    def delete_scheduled_plan(self, plan_index):
        plans = self.data.get("scheduled_plans", [])
        if not 0 <= plan_index < len(plans):
            return
        del plans[plan_index]
        self.save_data()
        self.refresh_planner_views()

    def refresh_planner_list(self):
        for widget in self.planner_list.winfo_children():
            widget.destroy()
        plans = self.data.get("scheduled_plans", [])
        if not plans:
            ctk.CTkLabel(self.planner_list, text="Brak zaplanowanych sesji.", text_color="#94A3B8").pack(anchor="w", padx=10, pady=10)
            return
        status_names = {"planned": "ZAPLANOWANE", "started": "ROZPOCZĘTE", "completed": "UKOŃCZONE"}
        status_colors = {"planned": "#60A5FA", "started": "#FBBF24", "completed": "#34D399"}
        for index, plan in sorted(enumerate(plans), key=lambda item: item[1].get("date", "")):
            status = plan.get("status", "planned")
            row = ctk.CTkFrame(self.planner_list, fg_color="#1E293B")
            row.pack(fill="x", padx=5, pady=4)
            ctk.CTkLabel(row, text=plan.get("date", "Brak daty"), width=105, anchor="w", text_color="#CBD5E1").pack(side="left", padx=10, pady=10)
            plan_time = plan.get("time", "")
            time_text = f" · {plan_time}" if plan_time else ""
            ctk.CTkLabel(row, text=plan.get("routine_name", "Rutyna") + time_text, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", fill="x", expand=True, padx=8, pady=10)
            ctk.CTkLabel(row, text=status_names.get(status, status.upper()), width=125, text_color=status_colors.get(status, "#CBD5E1"), font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5, pady=10)
            if status == "planned":
                ctk.CTkButton(row, text="Rozpocznij rutynę", width=125, command=lambda plan_index=index: self.start_scheduled_plan(plan_index)).pack(side="right", padx=3, pady=6)
            elif status == "started":
                ctk.CTkButton(row, text="Otwórz trening", width=105, fg_color="#059669", hover_color="#047857", command=lambda plan_index=index: self.open_scheduled_plan_training(plan_index)).pack(side="right", padx=3, pady=6)
            ctk.CTkButton(row, text="Usuń", width=62, fg_color="#991B1B", hover_color="#B91C1C", command=lambda plan_index=index: self.delete_scheduled_plan(plan_index)).pack(side="right", padx=3, pady=6)

    # --- ZAKŁADKA 3: Statystyki ---
    def setup_stats(self):
        self.setup_stats_filters()

        self.stats_card = ctk.CTkFrame(self.tab_stats)
        self.stats_card.pack(fill="x", padx=20, pady=10)

        self.lbl_stat_time = ctk.CTkLabel(self.stats_card, text="Łączny czas spędzony w treningu: 0 minut", font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_stat_time.pack(anchor="w", padx=20, pady=10)

        self.lbl_stat_xp = ctk.CTkLabel(self.stats_card, text="Zdobyte Punkty Potu (Intensity XP): 0 XP", font=ctk.CTkFont(size=15, weight="bold"), text_color="#F59E0B")
        self.lbl_stat_xp.pack(anchor="w", padx=20, pady=10)

        self.lbl_stat_rank = ctk.CTkLabel(
            self.stats_card,
            text="Aktualna ranga: Silver I",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#F472B6"
        )
        self.lbl_stat_rank.pack(anchor="w", padx=20, pady=10)

        self.lbl_stat_rank_progress = ctk.CTkLabel(
            self.stats_card,
            text="Pozostało 120 XP do Silver II",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#F472B6"
        )
        self.lbl_stat_rank_progress.pack(anchor="w", padx=20, pady=(0, 5))
        self.stat_rank_progress_bar = ctk.CTkProgressBar(
            self.stats_card,
            height=14,
            corner_radius=7,
            progress_color="#EC4899",
            fg_color="#334155"
        )
        self.stat_rank_progress_bar.pack(fill="x", padx=20, pady=(0, 12))
        self.stat_rank_progress_bar.set(0)

        charts_card = ctk.CTkFrame(self.tab_stats, fg_color="#0F172A")
        charts_card.pack(fill="x", padx=20, pady=(0, 15))
        charts_header = ctk.CTkFrame(charts_card, fg_color="transparent")
        charts_header.pack(fill="x", padx=15, pady=(12, 5))
        ctk.CTkLabel(
            charts_header,
            text="WYKRESY POSTĘPÓW",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#38BDF8"
        ).pack(side="left")
        self.lbl_stat_streak = ctk.CTkLabel(
            charts_header,
            text="Najdłuższa seria: 0 dni",
            text_color="#FBBF24",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_stat_streak.pack(side="left", padx=20)
        self.chart_period = ctk.StringVar(value="Tydzień")
        ctk.CTkSegmentedButton(
            charts_header,
            values=["Tydzień", "Miesiąc"],
            variable=self.chart_period,
            command=self.refresh_progress_charts,
            width=180
        ).pack(side="right")

        self.progress_figure = Figure(figsize=(10, 5.5), dpi=100, facecolor="#0F172A")
        self.progress_axes = self.progress_figure.subplots(2, 2)
        self.progress_canvas = FigureCanvasTkAgg(self.progress_figure, master=charts_card)
        self.progress_canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self.skill_stats_card = ctk.CTkFrame(self.tab_stats, fg_color="#0F172A")
        self.skill_stats_card.pack(fill="x", padx=20, pady=(0, 15))
        skill_header = ctk.CTkFrame(self.skill_stats_card, fg_color="transparent")
        skill_header.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(
            skill_header,
            text="ROZWÓJ WEDŁUG KATEGORII",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#A78BFA"
        ).pack(side="left")
        ctk.CTkButton(
            skill_header,
            text="Ustaw cele",
            width=95,
            height=28,
            fg_color="#4C1D95",
            hover_color="#5B21B6",
            command=self.open_category_goals_editor
        ).pack(side="right")
        self.skill_stat_rows = {}
        for category in SKILL_CATEGORIES:
            row = ctk.CTkFrame(self.skill_stats_card, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            label = ctk.CTkLabel(row, text=category, width=105, anchor="w", text_color=SKILL_CATEGORY_COLORS[category])
            label.pack(side="left")
            progress = ctk.CTkProgressBar(
                row,
                height=10,
                progress_color=SKILL_CATEGORY_COLORS[category],
                fg_color="#263449"
            )
            progress.pack(side="left", fill="x", expand=True, padx=10)
            summary = ctk.CTkLabel(row, text="0 XP · 0 ćw.", width=105, anchor="e", text_color="#CBD5E1")
            summary.pack(side="right")
            self.skill_stat_rows[category] = (progress, summary)
        self.refresh_skill_category_stats()

        history_card = ctk.CTkFrame(self.tab_stats, fg_color="#0F172A")
        history_card.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        ctk.CTkLabel(
            history_card,
            text="HISTORIA UKOŃCZONYCH TRENINGÓW",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#38BDF8"
        ).pack(anchor="w", padx=15, pady=(12, 8))

        self.history_scroll = ctk.CTkScrollableFrame(history_card, fg_color="#111827")
        self.history_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 12))

        advice_card = ctk.CTkFrame(self.tab_stats, fg_color="#0F172A")
        advice_card.pack(fill="both", expand=True, padx=20, pady=15)

        ctk.CTkLabel(advice_card, text="💡 ZASADY REGENERACJI PRO:", font=ctk.CTkFont(size=16, weight="bold"), text_color="#10B981").pack(anchor="w", padx=15, pady=10)
        advice_txt = (
            "1. Po każdych 45 minutach intensywnego treningu aimu zrób 10 minut przerwy dla mięśni dłoni.\n"
            "2. Dbaj o nawodnienie – brak płynów obniża czas reakcji o ponad 12%.\n"
            "3. Skupiaj się na precyzji (placement celownika), a nie tylko na szybkości."
        )
        ctk.CTkLabel(advice_card, text=advice_txt, justify="left", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=15, pady=5)
        self.refresh_progress_charts()

    def get_filtered_completion_history(self):
        selected_category = self.stats_category_filter.get()
        history = self.data.get("completion_history", [])
        date_mode = self.stats_date_filter.get()
        today = datetime.now().date()
        start_date = None
        end_date = today
        if date_mode == "Dzisiaj":
            start_date = today
        elif date_mode == "Ten tydzień":
            start_date = today - timedelta(days=today.weekday())
        elif date_mode == "Ten miesiąc":
            start_date = today.replace(day=1)
        elif date_mode == "Własny zakres":
            try:
                start_date = datetime.strptime(self.stats_date_start.get().strip(), "%d-%m-%Y").date()
                end_date = datetime.strptime(self.stats_date_end.get().strip(), "%d-%m-%Y").date()
            except ValueError:
                return []
            if start_date > end_date:
                return []

        filtered_history = []
        for item in history:
            if selected_category != "Wszystkie" and self.get_task_category(item) != selected_category:
                continue
            if start_date is not None:
                completed_date = self.parse_completion_date(item)
                if completed_date is None or not start_date <= completed_date <= end_date:
                    continue
            filtered_history.append(item)
        return filtered_history

    def refresh_stats_date_filter(self, selected_mode=None):
        custom_enabled = self.stats_date_filter.get() == "Własny zakres"
        state = "normal" if custom_enabled else "disabled"
        self.stats_date_start.configure(state=state)
        self.stats_date_end.configure(state=state)
        self.refresh_filtered_stats()

    def refresh_filtered_stats(self, selected_category=None):
        self.refresh_training_history()
        self.refresh_progress_charts()

    def get_category_goals(self):
        stored_goals = self.data.get("category_goals", {})
        if not isinstance(stored_goals, dict):
            stored_goals = {}
        return {
            category: max(1, int(stored_goals.get(category, 5)))
            if str(stored_goals.get(category, 5)).isdigit()
            else 5
            for category in SKILL_CATEGORIES
        }

    def open_category_goals_editor(self):
        goals = self.get_category_goals()
        editor = ctk.CTkToplevel(self)
        editor.title("Cele kategorii")
        editor.geometry("430x390")
        editor.resizable(False, False)
        editor.transient(self)
        editor.grab_set()
        ctk.CTkLabel(
            editor,
            text="CELE DLA KATEGORII",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#A78BFA"
        ).pack(anchor="w", padx=24, pady=(20, 5))
        ctk.CTkLabel(
            editor,
            text="Ustaw liczbę ćwiczeń, które chcesz ukończyć.",
            text_color="#94A3B8"
        ).pack(anchor="w", padx=24, pady=(0, 12))
        entries = {}
        for category in SKILL_CATEGORIES:
            row = ctk.CTkFrame(editor, fg_color="transparent")
            row.pack(fill="x", padx=24, pady=3)
            ctk.CTkLabel(row, text=category, width=130, anchor="w", text_color=SKILL_CATEGORY_COLORS[category]).pack(side="left")
            entry = ctk.CTkEntry(row, width=90, justify="center")
            entry.insert(0, str(goals[category]))
            entry.pack(side="left")
            ctk.CTkLabel(row, text="ćwiczeń").pack(side="left", padx=8)
            entries[category] = entry

        def save_category_goals():
            new_goals = {}
            for category, entry in entries.items():
                try:
                    value = int(entry.get().strip())
                except ValueError:
                    messagebox.showerror("Nieprawidłowy cel", f"Cel dla kategorii {category} musi być liczbą.", parent=editor)
                    return
                if not 1 <= value <= 1000:
                    messagebox.showerror("Nieprawidłowy cel", "Cel musi wynosić od 1 do 1000 ćwiczeń.", parent=editor)
                    return
                new_goals[category] = value
            self.data["category_goals"] = new_goals
            self.save_data()
            self.refresh_skill_category_stats()
            editor.destroy()

        footer = ctk.CTkFrame(editor, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(16, 18))
        ctk.CTkButton(footer, text="Anuluj", fg_color="#334155", hover_color="#475569", command=editor.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Zapisz cele", fg_color="#7C3AED", hover_color="#6D28D9", command=save_category_goals).pack(side="right")

    def refresh_skill_category_stats(self):
        if not hasattr(self, "skill_stat_rows"):
            return

        category_xp = defaultdict(int)
        category_completed = defaultdict(int)
        for item in self.data.get("completion_history", []):
            category = self.get_task_category(item)
            try:
                duration_minutes = int(
                    item.get("duration", int(item.get("duration_seconds", 0)) / 60)
                )
            except (AttributeError, TypeError, ValueError):
                duration_minutes = 0
            category_xp[category] += max(0, duration_minutes) * 12
            category_completed[category] += 1

        category_goals = self.get_category_goals()
        for category, (progress, summary) in self.skill_stat_rows.items():
            xp = category_xp[category]
            completed = category_completed[category]
            progress.set(min(1.0, completed / category_goals[category]))
            summary.configure(text=f"{completed}/{category_goals[category]} ćw. · {xp} XP")

    def refresh_progress_charts(self, selected_period=None):
        if not hasattr(self, "progress_canvas"):
            return

        period = "month" if self.chart_period.get() == "Miesiąc" else "week"
        chart_training_data = dict(self.data)
        chart_training_data["completion_history"] = self.get_filtered_completion_history()
        labels, minutes, completed = self.get_training_chart_data(chart_training_data, period)
        dates = []
        today = datetime.now().date()
        start_date = today - timedelta(days=29 if period == "month" else 6)
        for offset in range(30 if period == "month" else 7):
            dates.append(start_date + timedelta(days=offset))

        xp_by_day = defaultdict(int)
        for item in self.get_filtered_completion_history():
            completed_date = self.parse_completion_date(item)
            if completed_date is None or completed_date not in dates:
                continue
            try:
                duration_minutes = int(
                    item.get("duration", int(item.get("duration_seconds", 0)) / 60)
                )
            except (AttributeError, TypeError, ValueError):
                duration_minutes = 0
            xp_by_day[completed_date] += max(0, duration_minutes) * 12

        xp_values = [xp_by_day[date] for date in dates]
        cumulative_xp = []
        running_xp = 0
        for value in xp_values:
            running_xp += value
            cumulative_xp.append(running_xp)

        chart_data = (
            ("Czas treningu (min)", minutes, "#38BDF8", "bar"),
            ("Ukończone ćwiczenia", completed, "#34D399", "bar"),
            ("XP zdobyte dziennie", xp_values, "#FBBF24", "bar"),
            ("Narastające XP", cumulative_xp, "#F472B6", "line")
        )
        x_values = list(range(len(labels)))
        for axis, (title, values, color, chart_type) in zip(self.progress_axes.flat, chart_data):
            axis.clear()
            axis.set_facecolor("#111827")
            if chart_type == "bar":
                axis.bar(x_values, values, color=color, width=0.72)
            else:
                axis.plot(x_values, values, color=color, linewidth=2.5, marker="o", markersize=4)
            axis.set_title(title, color="#E2E8F0", fontsize=10, pad=8)
            axis.tick_params(axis="both", colors="#94A3B8", labelsize=8)
            axis.grid(axis="y", color="#334155", alpha=0.45, linewidth=0.7)
            for spine in axis.spines.values():
                spine.set_color("#334155")
            axis.set_xticks(x_values)
            if period == "month":
                axis.set_xticks(x_values[::5])
                axis.set_xticklabels([labels[index] for index in x_values[::5]])
            else:
                axis.set_xticklabels(labels)
            axis.margins(x=0.02)

        self.progress_figure.tight_layout(pad=2.0)
        self.progress_canvas.draw_idle()
        longest_streak = self.get_longest_training_streak(self.data)
        self.lbl_stat_streak.configure(text=f"Najdłuższa seria: {longest_streak} dni")

    def refresh_training_history(self):
        for widget in self.history_scroll.winfo_children():
            widget.destroy()

        history = list(reversed(self.get_filtered_completion_history()))
        if not history:
            ctk.CTkLabel(
                self.history_scroll,
                text="Brak ukończonych treningów.",
                text_color="#94A3B8"
            ).pack(anchor="w", padx=12, pady=12)
            return

        for item in history:
            total_seconds = int(item.get("duration_seconds", int(item.get("duration", 0)) * 60))
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_text = f"{hours} godz. {minutes:02d} min {seconds:02d} sek"
            row = ctk.CTkFrame(self.history_scroll, fg_color="#1E293B")
            row.pack(fill="x", padx=5, pady=4)
            ctk.CTkLabel(
                row,
                text=item.get("date", "Brak daty"),
                width=110,
                anchor="w",
                text_color="#94A3B8"
            ).pack(side="left", padx=10, pady=8)
            ctk.CTkLabel(
                row,
                text=(
                    f"{item.get('type', 'Trening')}\n"
                    f"Trudność: {item.get('difficulty', 'brak oceny')}  •  "
                    f"Samopoczucie: {item.get('mood', 'brak oceny')}\n"
                    f"Pracować nad: {item.get('focus', 'nie podano')}"
                    + (f"\nNotatka: {item['note']}" if item.get("note") else "")
                ),
                anchor="w",
                font=ctk.CTkFont(weight="bold")
            ).pack(side="left", fill="x", expand=True, padx=8, pady=8)
            ctk.CTkLabel(
                row,
                text=duration_text,
                width=150,
                anchor="e",
                text_color="#10B981"
            ).pack(side="right", padx=10, pady=8)

    # --- ZAKŁADKA 4: Profil Użytkownika ---
    def setup_profile_tab(self):
        header = ctk.CTkLabel(self.tab_profile, text="⚙️ USTAWIENIA PROFILU UŻYTKOWNIKA", font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(pady=15)

        main_profile_frame = ctk.CTkFrame(self.tab_profile, fg_color="#1E293B")
        main_profile_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Lewa kolumna: Avatar & Podstawowe Dane
        left_col = ctk.CTkFrame(main_profile_frame, fg_color="#0F172A", width=300)
        left_col.pack(side="left", fill="y", padx=15, pady=15)

        ctk.CTkLabel(left_col, text="🖼️ ZDJĘCIE PROFILOWE", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 10))

        self.lbl_avatar_display = ctk.CTkLabel(left_col, text="[Brak zdjęcia]", width=140, height=140, fg_color="#1E293B", corner_radius=10)
        self.lbl_avatar_display.pack(pady=10)
        self.lbl_avatar_display.configure(cursor="hand2")
        self.lbl_avatar_display.bind("<ButtonPress-1>", self.start_avatar_drag)
        self.lbl_avatar_display.bind("<B1-Motion>", self.drag_avatar)

        btn_choose_avatar = ctk.CTkButton(
            left_col, 
            text="📷 Wybierz Avatar", 
            command=self.choose_avatar_file,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            font=ctk.CTkFont(weight="bold")
        )
        btn_choose_avatar.pack(pady=10)

        ctk.CTkLabel(left_col, text="Powiększenie zdjęcia", text_color="#CBD5E1").pack(pady=(12, 2))
        self.avatar_zoom_value = ctk.CTkLabel(left_col, text="100%", text_color="#38BDF8")
        self.avatar_zoom_value.pack(pady=(0, 2))
        self.avatar_zoom_slider = ctk.CTkSlider(
            left_col,
            from_=1.0,
            to=3.0,
            number_of_steps=20,
            command=self.preview_avatar_zoom
        )
        self.avatar_zoom_slider.set(1.0)
        self.avatar_zoom_slider.pack(fill="x", padx=20, pady=(0, 6))
        ctk.CTkButton(
            left_col,
            text="Zapisz powiększenie",
            width=170,
            fg_color="#10B981",
            hover_color="#059669",
            command=self.save_avatar_zoom
        ).pack(pady=(0, 10))

        # Prawa kolumna: Dane osobowe oraz Zmiana Hasła
        right_col = ctk.CTkFrame(main_profile_frame, fg_color="transparent")
        right_col.pack(side="right", fill="both", expand=True, padx=15, pady=15)

        # Sekcja 1: Dane Osobowe
        info_frame = ctk.CTkFrame(right_col, fg_color="#0F172A")
        info_frame.pack(fill="x", pady=(0, 15))

        ctk.CTkLabel(info_frame, text="📝 DANE OSOBOWE", font=ctk.CTkFont(size=15, weight="bold"), text_color="#38BDF8").pack(anchor="w", padx=15, pady=10)

        f_form = ctk.CTkFrame(info_frame, fg_color="transparent")
        f_form.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(f_form, text="Imię:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", pady=5)
        self.entry_first_name = ctk.CTkEntry(f_form, width=220)
        self.entry_first_name.grid(row=0, column=1, padx=10, pady=5)

        ctk.CTkLabel(f_form, text="Nazwisko:", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, sticky="w", pady=5)
        self.entry_last_name = ctk.CTkEntry(f_form, width=220)
        self.entry_last_name.grid(row=1, column=1, padx=10, pady=5)

        ctk.CTkLabel(f_form, text="Data urodzenia (DD-MM-RRRR):", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, sticky="w", pady=5)
        self.entry_birth_date = ctk.CTkEntry(f_form, width=220, placeholder_text="01-01-2000")
        self.entry_birth_date.grid(row=2, column=1, padx=10, pady=5)

        btn_save_info = ctk.CTkButton(
            info_frame, 
            text="💾 Zapisz Dane Osobowe", 
            fg_color="#10B981", 
            hover_color="#059669", 
            font=ctk.CTkFont(weight="bold"),
            command=self.save_profile_info
        )
        btn_save_info.pack(anchor="e", padx=15, pady=10)

        # Sekcja 2: Zmiana Hasła
        pass_frame = ctk.CTkFrame(right_col, fg_color="#0F172A")
        pass_frame.pack(fill="x")

        ctk.CTkLabel(pass_frame, text="🔑 ZMIANA HASŁA", font=ctk.CTkFont(size=15, weight="bold"), text_color="#F59E0B").pack(anchor="w", padx=15, pady=10)

        p_form = ctk.CTkFrame(pass_frame, fg_color="transparent")
        p_form.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(p_form, text="Obecne hasło:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, sticky="w", pady=5)
        self.entry_old_pass = ctk.CTkEntry(p_form, show="*", width=220)
        self.entry_old_pass.grid(row=0, column=1, padx=10, pady=5)

        ctk.CTkLabel(p_form, text="Nowe hasło:", font=ctk.CTkFont(weight="bold")).grid(row=1, column=0, sticky="w", pady=5)
        self.entry_new_pass = ctk.CTkEntry(p_form, show="*", width=220)
        self.entry_new_pass.grid(row=1, column=1, padx=10, pady=5)

        btn_change_pass = ctk.CTkButton(
            pass_frame, 
            text="🔒 Zmień Hasło", 
            fg_color="#F59E0B", 
            hover_color="#D97706", 
            font=ctk.CTkFont(weight="bold"),
            command=self.change_user_password
        )
        btn_change_pass.pack(anchor="e", padx=15, pady=10)

        self.lbl_profile_status = ctk.CTkLabel(right_col, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_profile_status.pack(pady=10)

        self.profile_calendar_frame = ctk.CTkFrame(self.tab_profile, fg_color="#0F172A")
        self.profile_calendar_frame.pack(fill="x", padx=20, pady=(0, 12))

        data_tools_frame = ctk.CTkFrame(self.tab_profile, fg_color="#0F172A")
        data_tools_frame.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(
            data_tools_frame,
            text="EKSPORT I KOPIA DANYCH",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#A78BFA"
        ).pack(anchor="w", padx=15, pady=(10, 4))
        ctk.CTkLabel(
            data_tools_frame,
            text="Przenieś postępy na inny komputer albo zachowaj historię treningów.",
            text_color="#94A3B8"
        ).pack(anchor="w", padx=15, pady=(0, 8))
        data_tools_buttons = ctk.CTkFrame(data_tools_frame, fg_color="transparent")
        data_tools_buttons.pack(fill="x", padx=15, pady=(0, 12))
        ctk.CTkButton(
            data_tools_buttons,
            text="Eksportuj statystyki CSV",
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.export_stats_csv
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            data_tools_buttons,
            text="Utwórz kopię danych",
            fg_color="#059669",
            hover_color="#047857",
            command=self.create_data_backup
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            data_tools_buttons,
            text="Importuj kopię danych",
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            command=self.import_data_backup
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            data_tools_buttons,
            text="Sprawdź aktualizacje",
            fg_color="#0F766E",
            hover_color="#115E59",
            command=lambda: self.check_for_updates(silent=False)
        ).pack(side="left", padx=8)

    def check_for_updates(self, silent=True, force=False, on_ready=None, parent=None):
        if not self.current_user and not force:
            if on_ready:
                on_ready()
            return
        threading.Thread(
            target=self._check_for_updates_worker,
            args=(silent, force, on_ready, parent),
            daemon=True
        ).start()

    def _check_for_updates_worker(self, silent, force, on_ready, parent):
        try:
            release = fetch_latest_release(APP_VERSION)
        except Exception as error:
            if not silent:
                self.after(0, lambda: messagebox.showerror(
                    "Błąd aktualizacji",
                    f"Nie udało się sprawdzić aktualizacji:\n{error}",
                    parent=parent or self
                ))
            if on_ready:
                self.after(0, on_ready)
            return
        self.after(0, lambda: self.handle_update_result(release, silent, force, on_ready, parent))

    def handle_update_result(self, release, silent=True, force=False, on_ready=None, parent=None):
        if not release:
            if not silent:
                messagebox.showinfo("Aktualizacje", f"Masz najnowszą wersję ({APP_VERSION}).", parent=parent or self)
            if on_ready:
                on_ready()
            return
        if not release.get("installer_ready", bool(release.get("url"))):
            messagebox.showinfo(
                "Aktualizacja dostępna",
                f"Wersja {release['version']} jest już opublikowana, ale instalator jest jeszcze przygotowywany. Spróbuj ponownie za chwilę.",
                parent=parent or self
            )
            if on_ready:
                on_ready()
            return
        if not messagebox.askyesno(
            "Dostępna aktualizacja",
            f"Dostępna jest wersja {release['version']}. Pobrać i zainstalować teraz?\n\nAplikacja pozostanie zablokowana do czasu aktualizacji.",
            parent=parent or self
        ):
            if force:
                messagebox.showwarning("Wymagana aktualizacja", "Aby korzystać z aplikacji, zainstaluj najnowszą wersję.", parent=parent or self)
            elif on_ready:
                on_ready()
            return
        threading.Thread(target=self._download_update_worker, args=(release, parent), daemon=True).start()

    def _download_update_worker(self, release, parent=None):
        try:
            installer_path = download_installer(release["url"])
        except Exception as error:
            self.after(0, lambda: messagebox.showerror(
                "Błąd aktualizacji",
                f"Nie udało się pobrać instalatora:\n{error}",
                parent=parent or self
            ))
            return
        self.after(0, lambda: self.install_downloaded_update(installer_path))

    def install_downloaded_update(self, installer_path):
        try:
            launch_installer(installer_path)
            self.close_app()
        except OSError as error:
            messagebox.showerror("Błąd aktualizacji", f"Nie udało się uruchomić instalatora:\n{error}", parent=self)

    def export_stats_csv(self):
        if not self.current_user:
            return
        file_path = filedialog.asksaveasfilename(
            title="Eksportuj statystyki treningowe",
            initialfile=f"cs2_statystyki_{self.current_user}.csv",
            defaultextension=".csv",
            filetypes=[("Plik CSV", "*.csv")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=(
                        "date", "type", "category", "duration_seconds",
                        "difficulty", "mood", "focus", "note"
                    )
                )
                writer.writeheader()
                for item in self.data.get("completion_history", []):
                    writer.writerow({
                        field: item.get(field, "")
                        for field in writer.fieldnames
                    })
            messagebox.showinfo("Eksport zakończony", "Statystyki zostały zapisane do pliku CSV.", parent=self)
        except (OSError, csv.Error) as error:
            messagebox.showerror("Błąd eksportu", f"Nie udało się zapisać pliku:\n{error}", parent=self)

    def create_data_backup(self):
        if not self.current_user:
            return
        file_path = filedialog.asksaveasfilename(
            title="Utwórz kopię danych aplikacji",
            initialfile="cs2_trening_backup.json",
            defaultextension=".json",
            filetypes=[("Kopia danych JSON", "*.json")]
        )
        if not file_path:
            return

        backup = {
            "format": "cs2_training_backup_v1",
            "users": self.users,
            "training_data": self.training_data
        }
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(backup, file, ensure_ascii=False, indent=4)
            messagebox.showinfo("Kopia utworzona", "Pełna kopia danych została zapisana.", parent=self)
        except (OSError, TypeError) as error:
            messagebox.showerror("Błąd kopii", f"Nie udało się zapisać kopii:\n{error}", parent=self)

    def import_data_backup(self):
        if not self.current_user:
            return
        file_path = filedialog.askopenfilename(
            title="Importuj kopię danych aplikacji",
            filetypes=[("Kopia danych JSON", "*.json")]
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                backup = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            messagebox.showerror("Błąd importu", f"Nie udało się odczytać pliku:\n{error}", parent=self)
            return

        imported_users = backup.get("users") if isinstance(backup, dict) else None
        imported_training = backup.get("training_data") if isinstance(backup, dict) else None
        if not isinstance(imported_users, dict) or not isinstance(imported_training, dict):
            messagebox.showerror("Nieprawidłowa kopia", "Wybrany plik nie jest kopią danych CS2 Trening.", parent=self)
            return
        if self.current_user not in imported_users:
            messagebox.showerror(
                "Nieprawidłowa kopia",
                "Kopia nie zawiera aktualnie zalogowanego użytkownika.",
                parent=self
            )
            return
        if not messagebox.askyesno(
            "Potwierdź import",
            "Import zastąpi obecne konta i dane treningowe. Czy kontynuować?",
            parent=self
        ):
            return

        imported_training.setdefault("users", {})
        if not isinstance(imported_training["users"], dict):
            messagebox.showerror("Nieprawidłowa kopia", "Sekcja danych treningowych ma nieprawidłowy format.", parent=self)
            return
        self.users = imported_users
        self.training_data = imported_training
        self.load_user_training_data()
        self.save_users()
        self.save_data()
        self.refresh_custom_routines()
        self.refresh_ui()
        self.load_user_profile_data()
        messagebox.showinfo("Import zakończony", "Dane zostały pomyślnie przywrócone.", parent=self)

    def choose_avatar_file(self):
        file_path = filedialog.askopenfilename(
            title="Wybierz zdjęcie profilowe",
            filetypes=[("Pliki graficzne", "*.png *.jpg *.jpeg *.bmp")]
        )
        if file_path and self.current_user:
            user_info = self.get_user_data(self.current_user)
            user_info["avatar_path"] = file_path
            if self.cloud_data_service.enabled:
                try:
                    user_info["avatar_url"] = self.cloud_data_service.upload_avatar(
                        self.current_user,
                        file_path
                    )
                except Exception:
                    user_info.pop("avatar_url", None)
            self.save_users()
            self.load_user_profile_data()
            if hasattr(self, "refresh_users_list"):
                self.refresh_users_list()
            self.lbl_profile_status.configure(text="✓ Zaktualizowano avatar profilowy!", text_color="#10B981")

    def preview_avatar_zoom(self, value):
        zoom = float(value)
        self.avatar_zoom_value.configure(text=f"{round(zoom * 100)}%")
        user_info = self.get_user_data(self.current_user) if self.current_user else {}
        avatar_path = user_info.get("avatar_path", "")
        if avatar_path and os.path.exists(avatar_path):
            try:
                image = crop_avatar(
                    Image.open(avatar_path),
                    zoom,
                    self.avatar_focus_x,
                    self.avatar_focus_y
                )
                large_image = ctk.CTkImage(light_image=image, dark_image=image, size=(130, 130))
                self.lbl_avatar_display.configure(image=large_image, text="")
                self._profile_avatar_preview = large_image
            except Exception:
                pass

    def start_avatar_drag(self, event):
        self._avatar_drag_origin = (
            event.x,
            event.y,
            self.avatar_focus_x,
            self.avatar_focus_y
        )

    def drag_avatar(self, event):
        if not getattr(self, "_avatar_drag_origin", None):
            return
        start_x, start_y, focus_x, focus_y = self._avatar_drag_origin
        zoom = max(1.0, float(self.avatar_zoom_slider.get()))
        self.avatar_focus_x = max(0.0, min(1.0, focus_x - (event.x - start_x) / (130 * zoom)))
        self.avatar_focus_y = max(0.0, min(1.0, focus_y - (event.y - start_y) / (130 * zoom)))
        self.preview_avatar_zoom(self.avatar_zoom_slider.get())

    def save_avatar_zoom(self):
        if not self.current_user:
            return
        user_info = self.get_user_data(self.current_user)
        user_info["avatar_zoom"] = round(float(self.avatar_zoom_slider.get()), 2)
        user_info["avatar_focus_x"] = round(self.avatar_focus_x, 4)
        user_info["avatar_focus_y"] = round(self.avatar_focus_y, 4)
        self.save_users()
        self.load_user_profile_data()
        if hasattr(self, "refresh_users_list"):
            self.refresh_users_list()
        self.lbl_profile_status.configure(text="✓ Zapisano powiększenie avatara!", text_color="#10B981")

    def load_user_profile_data(self):
        if not self.current_user:
            return

        user_info = self.get_user_data(self.current_user)

        self.entry_first_name.delete(0, "end")
        self.entry_first_name.insert(0, user_info.get("first_name", ""))

        self.entry_last_name.delete(0, "end")
        self.entry_last_name.insert(0, user_info.get("last_name", ""))

        self.entry_birth_date.delete(0, "end")
        birth_date = user_info.get("birth_date", "")
        try:
            birth_date = datetime.strptime(birth_date, "%Y-%m-%d").strftime("%d-%m-%Y")
        except ValueError:
            pass
        self.entry_birth_date.insert(0, birth_date)

        self.entry_old_pass.delete(0, "end")
        self.entry_new_pass.delete(0, "end")

        avatar_path = user_info.get("avatar_path", "")
        avatar_zoom = get_avatar_zoom(user_info)
        self.avatar_focus_x, self.avatar_focus_y = get_avatar_focus(user_info)
        if hasattr(self, "avatar_zoom_slider"):
            self.avatar_zoom_slider.set(avatar_zoom)
            self.avatar_zoom_value.configure(text=f"{round(avatar_zoom * 100)}%")
        if avatar_path and os.path.exists(avatar_path):
            try:
                img = crop_avatar(
                    Image.open(avatar_path),
                    avatar_zoom,
                    self.avatar_focus_x,
                    self.avatar_focus_y
                )
                
                # Duży avatar w zakładce profilu
                avatar_img_large = ctk.CTkImage(light_image=img, dark_image=img, size=(130, 130))
                self.lbl_avatar_display.configure(image=avatar_img_large, text="")

                # Mały avatar obok nazwy w górnym pasku
                avatar_img_small = ctk.CTkImage(light_image=img, dark_image=img, size=(30, 30))
                self.lbl_user_avatar_top.configure(image=avatar_img_small, text="")
            except Exception:
                self.lbl_avatar_display.configure(image=None, text="[Błąd pliku]")
                self.lbl_user_avatar_top.configure(image=None, text="👤")
        else:
            self.lbl_avatar_display.configure(image=None, text="[Brak zdjęcia]")
            self.lbl_user_avatar_top.configure(image=None, text="👤")

        self.refresh_profile_calendar()

    def refresh_profile_calendar(self):
        if not self.current_user or not hasattr(self, "profile_calendar_frame"):
            return
        for widget in self.profile_calendar_frame.winfo_children():
            widget.destroy()
        self.add_activity_calendar(self.profile_calendar_frame, self.data)

    def save_profile_info(self):
        if not self.current_user:
            return

        user_info = self.get_user_data(self.current_user)
        user_info["first_name"] = self.entry_first_name.get().strip()
        user_info["last_name"] = self.entry_last_name.get().strip()
        birth_date = self.entry_birth_date.get().strip()
        if birth_date:
            try:
                datetime.strptime(birth_date, "%d-%m-%Y")
            except ValueError:
                self.lbl_profile_status.configure(
                    text="❌ Data musi mieć format DD-MM-RRRR, np. 01-01-2000.",
                    text_color="#EF4444"
                )
                return
        else:
            birth_date = ""
        user_info["birth_date"] = birth_date

        self.save_users()
        self.lbl_profile_status.configure(text="✓ Dane osobowe pomyślnie zapisane!", text_color="#10B981")

    def change_user_password(self):
        if not self.current_user:
            return

        old_p = self.entry_old_pass.get().strip()
        new_p = self.entry_new_pass.get().strip()

        user_info = self.get_user_data(self.current_user)

        if not old_p or not new_p:
            self.lbl_profile_status.configure(text="❌ Pola haseł nie mogą być puste!", text_color="#EF4444")
            return

        password_matches, _ = verify_password(old_p, user_info.get("password", ""))
        if not password_matches:
            self.lbl_profile_status.configure(text="❌ Podane obecne hasło jest nieprawidłowe!", text_color="#EF4444")
            return

        user_info["password"] = hash_password(new_p)
        self.save_users()

        self.entry_old_pass.delete(0, "end")
        self.entry_new_pass.delete(0, "end")
        self.lbl_profile_status.configure(text="✓ Hasło zostało pomyślnie zmienione!", text_color="#10B981")

    # --- ZAKŁADKA 5: Panel Administratora (AWATAR OBOK NAZWY UŻYTKOWNIKA) ---
    def setup_admin_tab(self):
        header = ctk.CTkLabel(self.tab_admin, text="🛡️ PANEL ADMINISTRATORA — ZARZĄDZANIE SYSTEMEM", font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(pady=10)

        module_catalog_frame = ctk.CTkFrame(self.tab_admin, fg_color="#1E293B")
        module_catalog_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(
            module_catalog_frame,
            text="🧩 KATALOG MODUŁÓW TRENINGOWYCH",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#A78BFA"
        ).pack(side="left", padx=15, pady=10)
        ctk.CTkButton(
            module_catalog_frame,
            text="Edytuj moduły",
            width=130,
            fg_color="#7C3AED",
            hover_color="#6D28D9",
            command=self.open_module_catalog_editor
        ).pack(side="right", padx=15, pady=7)

        # Sekcja Tworzenia Nowego Użytkownika
        create_user_frame = ctk.CTkFrame(self.tab_admin, fg_color="#1E293B")
        create_user_frame.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(create_user_frame, text="👤 TWORZENIE NOWEGO UŻYTKOWNIKA", font=ctk.CTkFont(size=15, weight="bold"), text_color="#38BDF8").pack(anchor="w", padx=15, pady=8)

        form_subframe = ctk.CTkFrame(create_user_frame, fg_color="transparent")
        form_subframe.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(form_subframe, text="Login:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5)
        self.new_user_entry = ctk.CTkEntry(form_subframe, placeholder_text="Nowy login", width=160)
        self.new_user_entry.grid(row=0, column=1, padx=10, pady=5)

        ctk.CTkLabel(form_subframe, text="Hasło:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=10, pady=5)
        self.new_pass_entry = ctk.CTkEntry(form_subframe, placeholder_text="Hasło", width=160)
        self.new_pass_entry.grid(row=0, column=3, padx=10, pady=5)

        btn_create = ctk.CTkButton(
            form_subframe, 
            text="+ Utwórz Konto", 
            fg_color="#10B981", 
            hover_color="#059669", 
            font=ctk.CTkFont(weight="bold"),
            command=self.create_new_user
        )
        btn_create.grid(row=0, column=4, padx=15, pady=5)

        self.lbl_admin_msg = ctk.CTkLabel(create_user_frame, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self.lbl_admin_msg.pack(anchor="w", padx=15, pady=(0, 5))

        # Sekcja Zarządzania Użytkownikami
        users_list_frame = ctk.CTkFrame(self.tab_admin, fg_color="#1E293B")
        users_list_frame.pack(fill="both", expand=True, padx=20, pady=5)

        ctk.CTkLabel(users_list_frame, text="📋 ZARZĄDZANIE KONTAMI UŻYTKOWNIKÓW", font=ctk.CTkFont(size=15, weight="bold"), text_color="#F59E0B").pack(anchor="w", padx=15, pady=8)

        self.users_scroll = ctk.CTkScrollableFrame(users_list_frame)
        self.users_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))

        self.refresh_users_list()

        # Panel Monitoringu
        admin_card = ctk.CTkFrame(self.tab_admin, fg_color="#0F172A")
        admin_card.pack(fill="x", padx=20, pady=5)

        self.lbl_clock = ctk.CTkLabel(
            admin_card, 
            text="📅 Data i czas: --", 
            font=ctk.CTkFont(size=14, weight="bold"), 
            text_color="#38BDF8"
        )
        self.lbl_clock.pack(anchor="w", padx=20, pady=8)

        self.lbl_admin_session_time = ctk.CTkLabel(
            admin_card, 
            text="⏳ Czas obecnej sesji użytkownika: 00:00:00", 
            font=ctk.CTkFont(size=14, weight="bold"), 
            text_color="#F59E0B"
        )
        self.lbl_admin_session_time.pack(anchor="w", padx=20, pady=8)

    def open_module_catalog_editor(self):
        if not self.can_manage_modules():
            self.show_module_permission_error()
            return

        editor = ctk.CTkToplevel(self)
        editor.title("Katalog modułów")
        editor.geometry("720x600")
        editor.minsize(620, 480)
        editor.transient(self)
        editor.grab_set()
        ctk.CTkLabel(
            editor,
            text="ZARZĄDZANIE MODUŁAMI",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#A78BFA"
        ).pack(anchor="w", padx=22, pady=(18, 4))
        ctk.CTkLabel(
            editor,
            text="Zmiany będą widoczne dla wszystkich użytkowników.",
            text_color="#94A3B8"
        ).pack(anchor="w", padx=22, pady=(0, 10))
        rows_frame = ctk.CTkScrollableFrame(editor, fg_color="#111827")
        rows_frame.pack(fill="both", expand=True, padx=22, pady=(0, 8))
        rows = []

        def read_rows():
            return [
                {"name": row["name"].get().strip(), "category": row["category"].get()}
                for row in rows
            ]

        def render_rows(items):
            for widget in rows_frame.winfo_children():
                widget.destroy()
            rows.clear()
            for index, item in enumerate(items):
                row_frame = ctk.CTkFrame(rows_frame, fg_color="#172338")
                row_frame.pack(fill="x", padx=3, pady=3)
                name_entry = ctk.CTkEntry(row_frame, placeholder_text="Nazwa modułu")
                name_entry.insert(0, item.get("name", ""))
                name_entry.pack(side="left", fill="x", expand=True, padx=(8, 6), pady=7)
                category_menu = ctk.CTkOptionMenu(row_frame, values=list(SKILL_CATEGORIES), width=125)
                category_menu.set(item.get("category", "Aim"))
                category_menu.pack(side="left", padx=4, pady=7)
                ctk.CTkButton(
                    row_frame,
                    text="Usuń",
                    width=62,
                    fg_color="#991B1B",
                    hover_color="#B91C1C",
                    command=lambda row_index=index: remove_row(row_index)
                ).pack(side="left", padx=(4, 7), pady=7)
                rows.append({"name": name_entry, "category": category_menu})

        def remove_row(index):
            items = read_rows()
            del items[index]
            render_rows(items)

        def add_row():
            items = read_rows()
            items.append({"name": "", "category": "Aim"})
            render_rows(items)
            rows[-1]["name"].focus_set()

        def save_catalog():
            catalog = []
            names = set()
            for index, item in enumerate(read_rows(), start=1):
                if not item["name"]:
                    messagebox.showerror("Brak nazwy", f"Uzupełnij nazwę modułu {index}.", parent=editor)
                    return
                if item["name"].lower() in names:
                    messagebox.showerror("Duplikat", f"Moduł '{item['name']}' występuje więcej niż raz.", parent=editor)
                    return
                names.add(item["name"].lower())
                catalog.append(item)
            if not catalog:
                messagebox.showerror("Brak modułów", "Katalog musi zawierać co najmniej jeden moduł.", parent=editor)
                return
            self.training_data["module_catalog"] = catalog
            self.save_shared_training_config()
            self.save_data_for_user(self.current_user)
            self.refresh_module_catalog()
            editor.destroy()

        render_rows(self.get_module_catalog())
        ctk.CTkButton(editor, text="+ Dodaj moduł", fg_color="#334155", hover_color="#475569", command=add_row).pack(anchor="w", padx=22, pady=(0, 8))
        footer = ctk.CTkFrame(editor, fg_color="transparent")
        footer.pack(fill="x", padx=22, pady=(0, 16))
        ctk.CTkButton(footer, text="Anuluj", fg_color="#334155", hover_color="#475569", command=editor.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Zapisz katalog", fg_color="#7C3AED", hover_color="#6D28D9", command=save_catalog).pack(side="right")

    def refresh_users_list(self):
        for widget in self.users_scroll.winfo_children():
            widget.destroy()
        self.admin_avatar_images = {}

        for username in list(self.users.keys()):
            user_info = self.get_user_data(username)
            password = user_info.get("password", "")

            user_row = ctk.CTkFrame(self.users_scroll, fg_color="#0F172A")
            user_row.pack(fill="x", padx=5, pady=4)

            # Kontener na mini-awatar i nazwę użytkownika po lewej stronie
            left_info_frame = ctk.CTkFrame(user_row, fg_color="transparent")
            left_info_frame.pack(side="left", padx=5, pady=5)

            avatar_path = user_info.get("avatar_path", "")
            lbl_avatar = ctk.CTkLabel(left_info_frame, text="", width=28, height=28)
            lbl_avatar.pack(side="left", padx=(2, 6))

            if avatar_path and os.path.exists(avatar_path):
                try:
                    img = crop_avatar(
                        Image.open(avatar_path),
                        get_avatar_zoom(user_info),
                        *get_avatar_focus(user_info)
                    )
                    avatar_img_list = ctk.CTkImage(light_image=img, dark_image=img, size=(28, 28))
                    lbl_avatar.configure(image=avatar_img_list)
                    self.admin_avatar_images[username] = avatar_img_list
                except Exception:
                    lbl_avatar.configure(text="👤")
            else:
                lbl_avatar.configure(text="👤")
                avatar_url = user_info.get("avatar_url", "")
                if avatar_url:
                    threading.Thread(
                        target=self._load_admin_list_avatar,
                        args=(lbl_avatar, avatar_url, username),
                        daemon=True
                    ).start()

            role_text = " [ADMIN]" if username == "admin" else ""
            color = "#EF4444" if username == "admin" else "#38BDF8"

            lbl_name = ctk.CTkLabel(
                left_info_frame, 
                text=f"{username}{role_text}", 
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=color,
                width=110,
                anchor="w"
            )
            lbl_name.pack(side="left", padx=2)

            entry_user = ctk.CTkEntry(user_row, width=130)
            entry_user.insert(0, username)
            entry_user.pack(side="left", padx=5, pady=5)

            entry_pass = ctk.CTkEntry(user_row, width=130)
            entry_pass.configure(placeholder_text="Nowe hasło (opcjonalne)")
            entry_pass.pack(side="left", padx=5, pady=5)

            btn_profile = ctk.CTkButton(
                user_row,
                text="👁 Profil",
                fg_color="#8B5CF6",
                hover_color="#7C3AED",
                width=85,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda u=username: self.show_user_profile_admin(u)
            )
            btn_profile.pack(side="left", padx=5, pady=5)

            if username != "admin":
                btn_save = ctk.CTkButton(
                    user_row, 
                    text="💾 Zapisz", 
                    fg_color="#3B82F6", 
                    hover_color="#2563EB", 
                    width=75,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda old_u=username, u_e=entry_user, p_e=entry_pass: self.edit_user(old_u, u_e.get().strip(), p_e.get().strip())
                )
                btn_save.pack(side="left", padx=5, pady=5)

                btn_delete = ctk.CTkButton(
                    user_row, 
                    text="🗑️ Usuń", 
                    fg_color="#EF4444", 
                    hover_color="#DC2626", 
                    width=70,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda u=username: self.delete_user(u)
                )
                btn_delete.pack(side="left", padx=5, pady=5)
            else:
                btn_save = ctk.CTkButton(
                    user_row, 
                    text="💾 Zapisz Hasło", 
                    fg_color="#3B82F6", 
                    hover_color="#2563EB", 
                    width=110,
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda old_u=username, u_e=entry_user, p_e=entry_pass: self.edit_user(old_u, "admin", p_e.get().strip())
                )
                btn_save.pack(side="left", padx=5, pady=5)

    def _load_admin_list_avatar(self, label, avatar_url, username):
        try:
            request = urllib.request.Request(avatar_url, headers={"User-Agent": "CS2-Trening-Avatar"})
            with urllib.request.urlopen(request, timeout=8) as response:
                user_info = self.get_user_data(username)
                image = crop_avatar(
                    Image.open(BytesIO(response.read())),
                    get_avatar_zoom(user_info),
                    *get_avatar_focus(user_info)
                )
            avatar_image = ctk.CTkImage(light_image=image, dark_image=image, size=(28, 28))
            self.after(0, lambda: self._apply_admin_list_avatar(label, avatar_image, username))
        except Exception:
            pass

    def _apply_admin_list_avatar(self, label, avatar_image, username):
        try:
            if label.winfo_exists():
                label.configure(image=avatar_image, text="")
                self.admin_avatar_images[username] = avatar_image
        except tk.TclError:
            pass

    def show_user_profile_admin(self, username):
        if self.current_user != "admin" or username not in self.users:
            return

        user_info = self.get_user_data(username)
        training_info = self.training_data.get("users", {}).get(username, self.empty_training_data())
        total_seconds = self.get_total_seconds(training_info)
        completed_count = int(training_info.get("completed_count", 0))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        full_name = " ".join(
            part for part in (user_info.get("first_name", ""), user_info.get("last_name", "")) if part
        ) or "Nie podano"

        profile_win = ctk.CTkToplevel(self)
        profile_win.title(f"Profil użytkownika: {username}")
        profile_win.geometry("760x850")
        profile_win.minsize(620, 650)
        profile_win.resizable(True, True)
        profile_win.transient(self)
        profile_win.grab_set()

        ctk.CTkLabel(
            profile_win,
            text=f"👤 PROFIL: {username}",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=(22, 18))

        profile_scroll = ctk.CTkScrollableFrame(profile_win, fg_color="transparent")
        profile_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        profile_canvas = profile_scroll._parent_canvas
        profile_canvas.configure(yscrollincrement=1)
        profile_canvas.unbind("<MouseWheel>")
        profile_canvas.bind(
            "<MouseWheel>",
            lambda event: profile_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        )

        avatar_card = ctk.CTkFrame(profile_scroll, fg_color="#0F172A", border_width=1, border_color="#334155")
        avatar_card.pack(fill="x", padx=17, pady=(0, 8))
        avatar_label = ctk.CTkLabel(avatar_card, text="👤", width=110, height=110, font=ctk.CTkFont(size=42))
        avatar_label.pack(side="left", padx=16, pady=12)
        avatar_details = ctk.CTkFrame(avatar_card, fg_color="transparent")
        avatar_details.pack(side="left", fill="both", expand=True, padx=(0, 12))
        ctk.CTkLabel(
            avatar_details,
            text=username,
            anchor="w",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#38BDF8"
        ).pack(anchor="w", pady=(20, 4))
        ctk.CTkLabel(
            avatar_details,
            text=f"Ranga: {self.get_rank_for_xp(int(training_info.get('fatigue_score', 0) or 0))}",
            anchor="w",
            text_color="#FBBF24",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w")
        avatar_image_holder = {"image": None}
        avatar_zoom = get_avatar_zoom(user_info)
        avatar_focus_x, avatar_focus_y = get_avatar_focus(user_info)

        def apply_avatar(image):
            image = crop_avatar(image, avatar_zoom, avatar_focus_x, avatar_focus_y)
            image.thumbnail((100, 100), Image.Resampling.LANCZOS)
            avatar_image = ctk.CTkImage(light_image=image, dark_image=image, size=(100, 100))
            avatar_image_holder["image"] = avatar_image
            avatar_label.configure(image=avatar_image, text="")

        avatar_path = user_info.get("avatar_path", "")
        if avatar_path and os.path.exists(avatar_path):
            try:
                apply_avatar(Image.open(avatar_path))
            except Exception:
                pass
        else:
            avatar_url = user_info.get("avatar_url", "")
            if avatar_url:
                def load_admin_avatar():
                    try:
                        request = urllib.request.Request(avatar_url, headers={"User-Agent": "CS2-Trening-Avatar"})
                        with urllib.request.urlopen(request, timeout=8) as response:
                            image = Image.open(BytesIO(response.read())).copy()
                        profile_win.after(0, lambda: apply_avatar(image))
                    except Exception:
                        pass

                threading.Thread(target=load_admin_avatar, daemon=True).start()

        info_frame = ctk.CTkFrame(profile_scroll, fg_color="#1E293B")
        info_frame.pack(fill="x", padx=17, pady=5)

        profile_rows = (
            ("Imię i nazwisko", full_name),
            ("Data urodzenia", user_info.get("birth_date", "") or "Nie podano"),
            ("Łączny czas treningu", f"{hours} godz. {minutes:02d} min {seconds:02d} sek"),
            ("Ukończone treningi", str(completed_count)),
        )
        for label_text, value_text in profile_rows:
            row = ctk.CTkFrame(info_frame, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=7)
            ctk.CTkLabel(
                row,
                text=f"{label_text}:",
                width=180,
                anchor="w",
                font=ctk.CTkFont(weight="bold")
            ).pack(side="left")
            ctk.CTkLabel(row, text=value_text, anchor="w").pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            profile_scroll,
            text="Dane są tylko do podglądu administratora.",
            text_color="#94A3B8",
            font=ctk.CTkFont(size=12)
        ).pack(pady=(16, 8))

        self.add_activity_calendar(profile_scroll, training_info)
        self.add_admin_stats_charts(profile_scroll, training_info)

        ctk.CTkButton(
            profile_scroll,
            text="♻️ Resetuj statystyki treningu",
            width=240,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            font=ctk.CTkFont(weight="bold"),
            command=lambda: self.reset_user_training_stats(username, profile_win)
        ).pack(pady=(4, 8))

        ctk.CTkButton(
            profile_scroll,
            text="Zamknij",
            width=120,
            command=profile_win.destroy
        ).pack(pady=8)

    def add_admin_stats_charts(self, parent, training_info):
        stats_frame = ctk.CTkFrame(parent, fg_color="#0F172A")
        stats_frame.pack(fill="x", padx=17, pady=(4, 10))
        ctk.CTkLabel(
            stats_frame,
            text="STATYSTYKI TRENINGOWE — OSTATNIE 7 DNI",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38BDF8"
        ).pack(anchor="w", padx=12, pady=(10, 4))

        labels, minutes, completed = self.get_training_chart_data(training_info, "week")
        today = datetime.now().date()
        dates = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        xp_by_day = defaultdict(int)
        for item in training_info.get("completion_history", []):
            completed_date = self.parse_completion_date(item)
            if completed_date not in dates:
                continue
            try:
                duration_minutes = int(
                    item.get("duration", int(item.get("duration_seconds", 0)) / 60)
                )
            except (AttributeError, TypeError, ValueError):
                duration_minutes = 0
            xp_by_day[completed_date] += max(0, duration_minutes) * 12

        xp_values = [xp_by_day[date] for date in dates]
        cumulative_xp = []
        running_xp = 0
        for value in xp_values:
            running_xp += value
            cumulative_xp.append(running_xp)

        figure = Figure(figsize=(8.2, 6.2), dpi=90, facecolor="#0F172A")
        axes = figure.subplots(2, 2)
        chart_data = (
            ("Czas treningu (min)", minutes, "#38BDF8", "bar"),
            ("Ukończone ćwiczenia", completed, "#34D399", "bar"),
            ("XP zdobyte dziennie", xp_values, "#FBBF24", "bar"),
            ("Narastające XP", cumulative_xp, "#F472B6", "line")
        )
        x_values = list(range(len(labels)))
        for axis, (title, values, color, chart_type) in zip(axes.flat, chart_data):
            axis.set_facecolor("#111827")
            if chart_type == "bar":
                axis.bar(x_values, values, color=color, width=0.72)
            else:
                axis.plot(x_values, values, color=color, linewidth=2.2, marker="o", markersize=3)
            axis.set_title(title, color="#E2E8F0", fontsize=11, pad=7)
            axis.tick_params(axis="both", colors="#94A3B8", labelsize=8)
            axis.set_xticks(x_values)
            axis.set_xticklabels(labels, rotation=35, ha="right", fontsize=8)
            axis.grid(axis="y", color="#334155", alpha=0.45, linewidth=0.6)
            for spine in axis.spines.values():
                spine.set_color("#334155")

        figure.tight_layout(pad=1.5)
        canvas = FigureCanvasTkAgg(figure, master=stats_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="x", padx=8, pady=(0, 10))

    def reset_user_training_stats(self, username, profile_win):
        if self.current_user != "admin" or username not in self.users:
            return

        confirmed = messagebox.askyesno(
            "Potwierdź reset",
            f"Czy na pewno wyzerować czas i ukończone treningi użytkownika '{username}'?\n\n"
            "Zostanie również wyczyszczony kalendarz aktywności i XP.",
            parent=profile_win
        )
        if not confirmed:
            return

        training_info = self.training_data.setdefault("users", {}).setdefault(
            username,
            self.empty_training_data()
        )
        training_info["completed_count"] = 0
        training_info["total_minutes_spent"] = 0
        training_info["total_seconds_spent"] = 0
        training_info["fatigue_score"] = 0
        training_info["completion_history"] = []
        self.save_data_for_user(username)
        if self.cloud_leaderboard_cache is not None:
            self.cloud_leaderboard_cache.pop(username, None)
        self.cloud_leaderboard_cache_time = None
        if hasattr(self, "leaderboard_list"):
            self.refresh_leaderboard()

        if username == self.current_user:
            self.data = training_info
            self.refresh_ui()

        profile_win.grab_release()
        profile_win.destroy()
        self.show_user_profile_admin(username)

    def add_activity_calendar(self, parent, training_info):
        history = training_info.get("completion_history", [])
        activity_by_date = defaultdict(list)
        for item in history:
            completed_date = item.get("date")
            if completed_date:
                activity_by_date[completed_date].append(item)

        today = datetime.now().date()
        first_day = today - timedelta(days=89)
        calendar_start = first_day - timedelta(days=first_day.weekday())
        calendar_end = today + timedelta(days=6 - today.weekday())
        total_days = (calendar_end - calendar_start).days + 1
        week_count = total_days // 7
        active_days = sum(
            1 for date_key, entries in activity_by_date.items()
            if entries and first_day.isoformat() <= date_key <= today.isoformat()
        )

        calendar_frame = ctk.CTkFrame(
            parent,
            fg_color="#0F172A",
            border_width=1,
            border_color="#1E3A5F"
        )
        calendar_frame.pack(fill="x", padx=17, pady=(4, 10))

        header = ctk.CTkFrame(calendar_frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(12, 4))
        ctk.CTkLabel(
            header,
            text="AKTYWNOŚĆ TRENINGOWA",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#E2E8F0"
        ).pack(side="left")
        ctk.CTkLabel(
            header,
            text=f"{active_days} aktywnych dni · {len(history)} ukończonych sesji",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#38BDF8"
        ).pack(side="right")
        ctk.CTkLabel(
            calendar_frame,
            text="Ostatnie 90 dni",
            text_color="#94A3B8",
            font=ctk.CTkFont(size=11)
        ).pack(anchor="w", padx=15, pady=(0, 8))

        grid_frame = ctk.CTkFrame(calendar_frame, fg_color="#111827", corner_radius=8)
        grid_frame.pack(anchor="center", padx=15, pady=(0, 10))
        calendar_cells = []

        ctk.CTkLabel(grid_frame, text="", width=38).grid(row=0, column=0, padx=4, pady=3)
        for week in range(week_count):
            week_date = calendar_start + timedelta(days=week * 7)
            month_changed = week == 0 or week_date.month != (week_date - timedelta(days=7)).month
            ctk.CTkLabel(
                grid_frame,
                text=week_date.strftime("%b") if month_changed else "",
                text_color="#CBD5E1",
                font=ctk.CTkFont(size=9, weight="bold"),
                width=15
            ).grid(row=0, column=week + 1, padx=2, pady=(3, 2))

        weekdays = ("pon.", "wt.", "śr.", "czw.", "pt.", "sob.", "niedz.")
        for row, weekday in enumerate(weekdays, start=1):
            ctk.CTkLabel(
                grid_frame,
                text=weekday,
                width=38,
                anchor="e",
                text_color="#94A3B8",
                font=ctk.CTkFont(size=9)
            ).grid(row=row, column=0, padx=(4, 6), pady=2, sticky="e")

        calendar_hint = ctk.CTkLabel(
            calendar_frame,
            text="Najedź na dzień, aby zobaczyć szczegóły treningu.",
            height=30,
            text_color="#CBD5E1",
            fg_color="#111827",
            corner_radius=6,
            anchor="center",
            font=ctk.CTkFont(size=11)
        )

        for week in range(week_count):
            week_date = calendar_start + timedelta(days=week * 7)
            for weekday in range(7):
                cell_date = week_date + timedelta(days=weekday)
                date_key = cell_date.isoformat()
                entries = activity_by_date.get(date_key, [])
                count = len(entries) if first_day <= cell_date <= today else 0
                if count == 0:
                    color = "#1E293B"
                elif count == 1:
                    color = "#155E75"
                elif count == 2:
                    color = "#0E7490"
                else:
                    color = "#14B8A6"

                cell = ctk.CTkLabel(
                    grid_frame,
                    text="",
                    width=15,
                    height=15,
                    corner_radius=4,
                    fg_color=color
                )
                cell.grid(row=weekday + 1, column=week + 1, padx=2, pady=2)
                calendar_cells.append(cell)
                cell._calendar_date = cell_date
                cell._calendar_entries = entries
                cell._calendar_hint = calendar_hint
                cell.bind(
                    "<Enter>",
                    lambda event, d=cell_date, e=entries: self.show_calendar_details(event, d, e)
                )
                cell.bind(
                    "<Motion>",
                    lambda event, d=cell_date, e=entries: self.show_calendar_details(event, d, e)
                )
        legend = ctk.CTkFrame(calendar_frame, fg_color="transparent")
        legend.pack(anchor="center", pady=(0, 5))
        ctk.CTkLabel(legend, text="Mniej", text_color="#94A3B8", font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 5))
        for color in ("#1E293B", "#155E75", "#0E7490", "#14B8A6"):
            ctk.CTkLabel(legend, text="", width=15, height=15, corner_radius=4, fg_color=color).pack(side="left", padx=2)
        ctk.CTkLabel(legend, text="Więcej", text_color="#94A3B8", font=ctk.CTkFont(size=10)).pack(side="left", padx=(5, 0))
        calendar_hint.pack(fill="x", padx=15, pady=(3, 12))
        self.admin_calendar_hint = calendar_hint
        for cell in calendar_cells:
            cell.bind("<Leave>", self.hide_calendar_details)

    def show_calendar_details(self, event, completed_date, entries):
        text = f"{completed_date.strftime('%d.%m.%Y')}  ·  {len(entries)} ukończonych treningów"
        calendar_hint = getattr(event.widget, "_calendar_hint", None)
        if calendar_hint is not None and calendar_hint.winfo_exists():
            calendar_hint.configure(text=text)

    def hide_calendar_details(self, event):
        calendar_hint = getattr(event.widget, "_calendar_hint", None)
        if calendar_hint is not None and calendar_hint.winfo_exists():
            calendar_hint.configure(text="Najedź na dzień, aby zobaczyć szczegóły treningu.")

    def edit_user(self, old_username, new_username, new_password):
        if not new_username:
            self.lbl_admin_msg.configure(text="❌ Login nie może być pusty!", text_color="#EF4444")
            return

        if old_username == "admin" and new_username != "admin":
            self.lbl_admin_msg.configure(text="❌ Nie można zmienić loginu konta Administratora!", text_color="#EF4444")
            self.refresh_users_list()
            return

        if new_username != old_username and new_username in self.users:
            self.lbl_admin_msg.configure(text=f"❌ Użytkownik '{new_username}' już istnieje!", text_color="#EF4444")
            return

        user_data = self.get_user_data(old_username)
        if new_password:
            user_data["password"] = hash_password(new_password)

        if new_username != old_username:
            del self.users[old_username]
            self.users[new_username] = user_data
            try:
                self.cloud_data_service.delete_user_account(old_username)
            except Exception:
                pass
            if self.current_user == old_username:
                self.current_user = new_username

        self.save_users()
        self.save_user_account_to_cloud(new_username)
        self.lbl_admin_msg.configure(text=f"✓ Pomyślnie zaktualizowano konto: {new_username}", text_color="#10B981")
        self.refresh_users_list()

    def delete_user(self, username):
        if username == "admin":
            self.lbl_admin_msg.configure(text="❌ Nie można usunąć konta administratora!", text_color="#EF4444")
            return

        if username in self.users:
            del self.users[username]
            self.save_users()
            try:
                self.cloud_data_service.delete_user_account(username)
            except Exception:
                pass
            self.lbl_admin_msg.configure(text=f"✓ Usunięto użytkownika: {username}", text_color="#10B981")
            self.refresh_users_list()

    def create_new_user(self):
        new_username = self.new_user_entry.get().strip()
        new_password = self.new_pass_entry.get().strip()

        if not new_username or not new_password:
            self.lbl_admin_msg.configure(text="❌ Wypełnij oba pola (Login i Hasło)!", text_color="#EF4444")
            return

        if new_username in self.users:
            self.lbl_admin_msg.configure(text=f"❌ Użytkownik '{new_username}' już istnieje!", text_color="#EF4444")
            return

        self.users[new_username] = {
            "password": hash_password(new_password),
            "first_name": "",
            "last_name": "",
            "birth_date": "",
            "avatar_path": ""
        }
        self.save_users()
        self.save_user_account_to_cloud(new_username)

        self.new_user_entry.delete(0, "end")
        self.new_pass_entry.delete(0, "end")
        self.lbl_admin_msg.configure(text=f"✓ Pomyślnie utworzono konto dla: {new_username}", text_color="#10B981")
        
        self.refresh_users_list()

    def save_user_account_to_cloud(self, username):
        if not self.cloud_data_service.enabled or username not in self.users:
            return
        try:
            self.cloud_data_service.save_user_account(username, self.users[username])
        except Exception:
            pass

    # --- Zegar Systemowy ---
    def update_realtime_clock(self):
        now = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
        try:
            if self.current_user == "admin" and hasattr(self, "lbl_clock") and self.lbl_clock.winfo_exists():
                self.lbl_clock.configure(text=f"📅 Aktualny czas systemowy: {now}")
            self.after(1000, self.update_realtime_clock)
        except tk.TclError:
            pass

    # --- OBSŁUGA STOPERA DLA MODUŁÓW I SESJI ---
    def toggle_task_timer(self, index):
        if self.active_timer_index == index:
            self.stop_timer()
        else:
            self.stop_timer()
            self.active_timer_index = index
            self.data["active"][index].setdefault("tracked_seconds", 0)
            self.run_timer()
        self.save_data()
        self.refresh_ui()

    def stop_timer(self):
        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        self.active_timer_index = None
        self.refresh_timer_displays()

    def start_rest_timer(self):
        if self.rest_timer_job:
            self.stop_rest_timer()
            return
        if self.rest_timer_seconds <= 0:
            duration_text = self.rest_duration_menu.get().split()[0]
            self.rest_timer_seconds = int(duration_text) * 60
        self.btn_rest_timer.configure(text="Pauza")
        self.run_rest_timer()

    def run_rest_timer(self):
        minutes, seconds = divmod(self.rest_timer_seconds, 60)
        self.lbl_rest_timer.configure(text=f"{minutes:02d}:{seconds:02d}")
        if self.rest_timer_seconds <= 0:
            self.rest_timer_job = None
            self.btn_rest_timer.configure(text="Start przerwy")
            messagebox.showinfo("Przerwa zakończona", "Przerwa regeneracyjna dobiegła końca.", parent=self)
            return
        self.rest_timer_seconds -= 1
        self.rest_timer_job = self.after(1000, self.run_rest_timer)

    def stop_rest_timer(self):
        if self.rest_timer_job:
            self.after_cancel(self.rest_timer_job)
            self.rest_timer_job = None
        if hasattr(self, "btn_rest_timer") and self.btn_rest_timer.winfo_exists():
            self.btn_rest_timer.configure(text="Start przerwy")

    def reset_rest_timer(self):
        self.stop_rest_timer()
        self.rest_timer_seconds = 0
        if hasattr(self, "lbl_rest_timer") and self.lbl_rest_timer.winfo_exists():
            self.lbl_rest_timer.configure(text="00:00")

    def run_timer(self):
        if self.active_timer_index is not None:
            order = self.data["active"][self.active_timer_index]
            order["tracked_seconds"] = int(order.get("tracked_seconds", 0)) + 1
            self.session_timer_seconds += 1
            self.refresh_timer_displays()
            self.timer_job = self.after(1000, self.run_timer)

    def refresh_timer_displays(self):
        hrs = self.session_timer_seconds // 3600
        s_mins = (self.session_timer_seconds % 3600) // 60
        s_secs = self.session_timer_seconds % 60
        timer_is_running = self.active_timer_index is not None
        timer_text = "▶ TRENING W TOKU" if timer_is_running else "⏸ TRENING WSTRZYMANY"
        timer_color = "#34D399" if timer_is_running else "#FF4D5A"
        timer_background = "#123C34" if timer_is_running else "#111827"
        
        try:
            if hasattr(self, "lbl_admin_session_time") and self.lbl_admin_session_time.winfo_exists():
                self.lbl_admin_session_time.configure(text=f"⏳ Czas obecnej sesji użytkownika: {hrs:02d}:{s_mins:02d}:{s_secs:02d}")

            if self.lbl_session_timer.winfo_exists():
                self.lbl_session_timer.configure(
                    text=f"{timer_text}  {s_mins:02d}:{s_secs:02d}",
                    text_color=timer_color,
                    fg_color=timer_background
                )

            if self.active_timer_index is not None and hasattr(self, "current_timer_label"):
                tracked_seconds = int(
                    self.data["active"][self.active_timer_index].get("tracked_seconds", 0)
                )
                t_mins = tracked_seconds // 60
                t_secs = tracked_seconds % 60
                if self.current_timer_label.winfo_exists():
                    self.current_timer_label.configure(
                        text=f"⏱️ {t_mins:02d}:{t_secs:02d}",
                        text_color="#34D399" if timer_is_running else "#FF4D5A"
                    )
        except tk.TclError:
            pass

    # --- LOGIKA ZDAREŃ ---
    def load_preset_protocol(self, tasks):
        for t in tasks:
            self.data["active"].append({
                "type": t["type"],
                "duration": t["duration"],
                "category": self.get_task_category(t)
            })
        self.save_data()
        self.refresh_ui()
        self.tabview.set("⚡ Centrum Dowodzenia")

    def add_custom_order(self):
        t_type = self.entry_custom_type.get()
        category = self.entry_custom_category.get()
        dur = 0

        self.data["active"].append({"type": t_type, "duration": dur, "category": category})
        self.save_data()
        self.refresh_ui()

    def complete_order(self, index):
        if not 0 <= index < len(self.data["active"]):
            return

        completed_task = self.data["active"][index]
        tracked_seconds = int(completed_task.get("tracked_seconds", 0))
        if tracked_seconds <= 0:
            messagebox.showwarning(
                "Najpierw uruchom trening",
                "Nie możesz zaliczyć modułu bez uruchomienia timera. Kliknij START i wykonaj ćwiczenie.",
                parent=self
            )
            return

        notes_window = ctk.CTkToplevel(self)
        notes_window.title("Podsumowanie ćwiczenia")
        notes_window.geometry("520x570")
        notes_window.resizable(False, False)
        notes_window.transient(self)
        notes_window.grab_set()

        ctk.CTkLabel(
            notes_window,
            text="PODSUMOWANIE ĆWICZENIA",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#34D399"
        ).pack(anchor="w", padx=24, pady=(20, 5))
        ctk.CTkLabel(
            notes_window,
            text=completed_task.get("type", "Trening"),
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(fill="x", padx=24, pady=(0, 14))

        ctk.CTkLabel(notes_window, text="Komentarz po ćwiczeniu", anchor="w").pack(fill="x", padx=24)
        note_textbox = ctk.CTkTextbox(notes_window, height=105)
        note_textbox.pack(fill="x", padx=24, pady=(4, 12))

        ratings_frame = ctk.CTkFrame(notes_window, fg_color="transparent")
        ratings_frame.pack(fill="x", padx=24)
        ctk.CTkLabel(ratings_frame, text="Trudność", anchor="w").grid(row=0, column=0, sticky="w", pady=5)
        difficulty = ctk.StringVar(value="3 / 5")
        ctk.CTkOptionMenu(
            ratings_frame,
            variable=difficulty,
            values=["1 / 5", "2 / 5", "3 / 5", "4 / 5", "5 / 5"],
            width=120
        ).grid(row=0, column=1, padx=12, pady=5, sticky="w")

        ctk.CTkLabel(ratings_frame, text="Samopoczucie", anchor="w").grid(row=1, column=0, sticky="w", pady=5)
        mood = ctk.StringVar(value="Dobrze")
        ctk.CTkOptionMenu(
            ratings_frame,
            variable=mood,
            values=["Słabo", "Średnio", "Dobrze", "Bardzo dobrze"],
            width=120
        ).grid(row=1, column=1, padx=12, pady=5, sticky="w")

        ctk.CTkLabel(notes_window, text="Nad czym trzeba pracować?", anchor="w").pack(fill="x", padx=24, pady=(12, 0))
        focus_entry = ctk.CTkEntry(notes_window, placeholder_text="Np. celowanie w głowę, recoil, movement")
        focus_entry.pack(fill="x", padx=24, pady=(4, 14))

        def save_training_summary():
            self.finish_completed_order(
                index,
                note_textbox.get("1.0", "end").strip(),
                difficulty.get(),
                mood.get(),
                focus_entry.get().strip()
            )
            notes_window.destroy()

        footer = ctk.CTkFrame(notes_window, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(4, 18))
        ctk.CTkButton(
            footer,
            text="Anuluj",
            fg_color="#334155",
            hover_color="#475569",
            command=notes_window.destroy
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            footer,
            text="Zapisz i zalicz",
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(weight="bold"),
            command=save_training_summary
        ).pack(side="right")

    def finish_completed_order(self, index, note, difficulty, mood, focus):
        if 0 <= index < len(self.data["active"]):
            completed_task = self.data["active"][index]
            scheduled_plan_id = completed_task.get("scheduled_plan_id")
            tracked_seconds = int(completed_task.get("tracked_seconds", 0))

            if self.active_timer_index == index:
                self.stop_timer()
            elif self.active_timer_index is not None and self.active_timer_index > index:
                self.active_timer_index -= 1

            self.data["active"].pop(index)
            self.data["completed_count"] += 1
            tracked_minutes = (tracked_seconds + 59) // 60
            self.data["total_seconds_spent"] = self.get_total_seconds(self.data) + tracked_seconds
            self.data["total_minutes_spent"] = self.data["total_seconds_spent"] // 60
            self.data["fatigue_score"] += tracked_minutes * 12
            if scheduled_plan_id and not any(
                task.get("scheduled_plan_id") == scheduled_plan_id
                for task in self.data["active"]
            ):
                for plan in self.data.get("scheduled_plans", []):
                    if plan.get("plan_id") == scheduled_plan_id:
                        plan["status"] = "completed"
                        break
            self.data.setdefault("completion_history", []).append({
                "date": datetime.now().date().isoformat(),
                "type": completed_task["type"],
                "category": self.get_task_category(completed_task),
                "duration": tracked_minutes,
                "duration_seconds": tracked_seconds,
                "note": note,
                "difficulty": difficulty,
                "mood": mood,
                "focus": focus or "Nie podano"
            })

            self.save_data()
            self.refresh_ui()

    def animate_rank_progress(self, target_progress):
        if self.rank_progress_animation_job is not None:
            self.after_cancel(self.rank_progress_animation_job)
            self.rank_progress_animation_job = None

        start_progress = self.rank_progress_bar.get()
        steps = 18

        def update_progress(step=1):
            fraction = step / steps
            eased_fraction = 1 - (1 - fraction) ** 3
            progress = start_progress + (target_progress - start_progress) * eased_fraction
            self.rank_progress_bar.set(progress)
            self.lbl_rank_percentage.configure(text=f"{round(progress * 100)}%")

            if step < steps:
                self.rank_progress_animation_job = self.after(
                    16,
                    lambda: update_progress(step + 1)
                )
            else:
                self.rank_progress_animation_job = None

        update_progress()

    def refresh_ui(self):
        self.btn_add_module.configure(state="normal")
        for button in getattr(self, "preset_load_buttons", []):
            button.configure(state="normal")
        self.refresh_custom_routines()
        self.refresh_preset_protocols()

        for widget in self.orders_scroll.winfo_children():
            widget.destroy()

        for i, order in enumerate(self.data["active"]):
            card = ctk.CTkFrame(self.orders_scroll)
            card.pack(fill="x", padx=10, pady=5)

            lbl = ctk.CTkLabel(card, text=f"• {order['type']}", font=ctk.CTkFont(size=14, weight="bold"))
            lbl.pack(side="left", padx=15, pady=10)

            btn_done = ctk.CTkButton(
                card, 
                text="ZALICZONE ✓", 
                fg_color="#10B981", 
                hover_color="#059669",
                font=ctk.CTkFont(weight="bold"),
                width=100,
                command=lambda idx=i: self.complete_order(idx)
            )
            btn_done.pack(side="right", padx=10, pady=10)

            is_running = (self.active_timer_index == i)
            tracked_seconds = int(order.get("tracked_seconds", 0))
            btn_timer_text = "PAUZA ⏸️" if is_running else ("WZNÓW ▶" if tracked_seconds else "START 🚀")
            btn_timer_color = "#F59E0B" if is_running else "#3B82F6"

            btn_start_task = ctk.CTkButton(
                card,
                text=btn_timer_text,
                fg_color=btn_timer_color,
                font=ctk.CTkFont(weight="bold"),
                width=90,
                command=lambda idx=i: self.toggle_task_timer(idx)
            )
            btn_start_task.pack(side="right", padx=5, pady=10)

            if is_running or tracked_seconds:
                t_mins = tracked_seconds // 60
                t_secs = tracked_seconds % 60
                timer_label = ctk.CTkLabel(
                    card, 
                    text=f"⏱️ {t_mins:02d}:{t_secs:02d}", 
                    font=ctk.CTkFont(size=16, weight="bold"), 
                    text_color="#EF4444"
                )
                timer_label.pack(side="right", padx=10)
                if is_running:
                    self.current_timer_label = timer_label

        self.lbl_plan_time.configure(text=f"Aktywne zlecenia: {len(self.data['active'])}")
        self.lbl_completed.configure(text=f"Ukończone: {self.data['completed_count']}")
        self.lbl_fatigue.configure(text=f"Wskaźnik Potu: {self.data['fatigue_score']} XP")
        current_rank = self.get_rank_for_xp(self.data["fatigue_score"])
        self.lbl_rank.configure(text=f"Ranga: {current_rank}")
        rank_name, rank_progress_text, rank_progress = self.get_rank_progress(self.data["fatigue_score"])
        self.lbl_rank_progress.configure(text=f"{rank_name}  •  {rank_progress_text}")
        self.animate_rank_progress(rank_progress)
        self.refresh_weekly_goals()
        self.refresh_streaks()
        
        total_seconds = self.get_total_seconds(self.data)
        total_hours, remainder = divmod(total_seconds, 3600)
        total_minutes, total_secs = divmod(remainder, 60)
        self.lbl_stat_time.configure(
            text=f"Łączny czas spędzony w treningu: {total_hours} godz. {total_minutes:02d} min {total_secs:02d} sek"
        )
        self.lbl_stat_xp.configure(text=f"Zdobyte Punkty Potu (Intensity XP): {self.data['fatigue_score']} XP")
        self.lbl_stat_rank.configure(text=f"Aktualna ranga: {current_rank}")
        self.lbl_stat_rank_progress.configure(text=rank_progress_text)
        self.stat_rank_progress_bar.set(rank_progress)
        self.refresh_training_history()
        self.refresh_progress_charts()
        self.refresh_skill_category_stats()
        self.refresh_planner_views()
        self.refresh_leaderboard()
        self.refresh_profile_calendar()

# Keep the existing class API while the calculation logic lives in training_utils.py.
CS2ProTrainingApp.get_total_seconds = staticmethod(get_total_seconds)
CS2ProTrainingApp.get_weekly_training_totals = staticmethod(get_weekly_training_totals)
CS2ProTrainingApp.parse_completion_date = staticmethod(parse_completion_date)
CS2ProTrainingApp.get_training_chart_data = staticmethod(get_training_chart_data)
CS2ProTrainingApp.get_training_dates = staticmethod(get_training_dates)
CS2ProTrainingApp.get_longest_training_streak = staticmethod(get_longest_training_streak)
CS2ProTrainingApp.get_current_training_streak = staticmethod(get_current_training_streak)
CS2ProTrainingApp.get_training_badges = staticmethod(get_training_badges)
CS2ProTrainingApp.get_rank_for_xp = staticmethod(get_rank_for_xp)
CS2ProTrainingApp.get_rank_progress = staticmethod(get_rank_progress)
CS2ProTrainingApp.infer_skill_category = staticmethod(infer_skill_category)
CS2ProTrainingApp.get_task_category = staticmethod(get_task_category)
for _planner_method in (
    "setup_planner_tab",
    "refresh_planner_routine_options",
    "refresh_planner_views",
    "select_planner_date",
    "change_planner_month",
    "refresh_planner_calendar",
    "schedule_routine",
    "update_scheduled_plan_status",
    "start_scheduled_plan",
    "open_scheduled_plan_training",
    "check_training_reminders",
    "show_training_reminder",
    "open_planner_from_reminder",
    "delete_scheduled_plan",
    "refresh_planner_list",
):
    setattr(CS2ProTrainingApp, _planner_method, getattr(PlannerViewMixin, _planner_method))
for _stats_method in (
    "setup_stats_filters",
    "get_filtered_completion_history",
    "refresh_stats_date_filter",
    "refresh_filtered_stats",
):
    setattr(CS2ProTrainingApp, _stats_method, getattr(StatsViewMixin, _stats_method))

if __name__ == "__main__":
    app = CS2ProTrainingApp()
    app.mainloop()