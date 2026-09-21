import customtkinter as ctk
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime
from tkinter import filedialog
from PIL import Image

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DATA_FILE = "pro_training_data.json"
USERS_FILE = "users.json"
PASSWORD_SCHEME = "pbkdf2_sha256"

PRESET_PROTOCOLS = {
    "🔥 Pro Aim & Reflex (45 min)": [
        {"type": "Warmup: Aim Lab (Gridshot / Microflex)", "duration": 10},
        {"type": "Aim Botz: One-Taps & Counter-Strafe", "duration": 15},
        {"type": "Recoil Control (AK-47 / M4A1-S Spray)", "duration": 10},
        {"type": "FFA Deathmatch (Headshot Only)", "duration": 10}
    ],
    "🎯 Sniper & Flick Master (30 min)": [
        {"type": "Warmup: Aim Lab (Flickshot)", "duration": 10},
        {"type": "CS2 Workshop: AWP Angles & Flicks", "duration": 10},
        {"type": "FFA DM: AWP Positioning & Reaction", "duration": 10}
    ],
    "🧠 Utility & Tactical Drive (40 min)": [
        {"type": "Mirage Lineups (Smokes & Flashes)", "duration": 15},
        {"type": "Anubis & Inferno Execute Lineups", "duration": 15},
        {"type": "Retake Servers (Utility Application)", "duration": 10}
    ]
}

class CS2ProTrainingApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CS2 AIM PROTOCOL — PRO E-SPORT EDITION")
        self.geometry("1150x880")

        self.users = self.load_users()
        self.training_data = self.load_data()
        self.data = self.empty_training_data()
        self.current_user = None

        # Stan stoperów
        self.active_timer_index = None
        self.task_timer_seconds = 0
        self.session_timer_seconds = 0
        self.timer_job = None

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
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)

        self.tab_dashboard = self.tabview.add("⚡ Centrum Dowodzenia")
        self.tab_presets = self.tabview.add("🏆 Gotowe Rutyny Pro")
        self.tab_stats = self.tabview.add("📊 Statystyki & Pot")
        self.tab_profile = self.tabview.add("👤 Mój Profil")

        self.setup_dashboard()
        self.setup_presets()
        self.setup_stats()
        self.setup_profile_tab()

        # Zegarek systemowy
        self.update_realtime_clock()
        self.refresh_ui()

        # Otwarcie okna logowania
        self.show_login_dialog()

    # --- ZARZĄDZANIE UŻYTKOWNIKAMI I PROFILAMI ---
    def load_users(self):
        default_users = {
            "admin": {
                "password": self.hash_password("Aa798397463"),
                "first_name": "Administrator",
                "last_name": "Systemu",
                "birth_date": "2000-01-01",
                "avatar_path": ""
            }
        }
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for u_name, u_data in data.items():
                        if isinstance(u_data, str):
                            data[u_name] = {
                                "password": u_data,
                                "first_name": "",
                                "last_name": "",
                                "birth_date": "",
                                "avatar_path": ""
                            }
                    return data
            except Exception:
                return default_users
        else:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(default_users, f, ensure_ascii=False, indent=4)
            return default_users

    def save_users(self):
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.users, f, ensure_ascii=False, indent=4)

    @staticmethod
    def hash_password(password):
        salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
        return f"{PASSWORD_SCHEME}${salt.hex()}${digest.hex()}"

    @classmethod
    def verify_password(cls, password, stored_password):
        if not isinstance(stored_password, str):
            return False, False

        if not stored_password.startswith(f"{PASSWORD_SCHEME}$"):
            return hmac.compare_digest(stored_password, password), True

        try:
            _, salt_hex, digest_hex = stored_password.split("$", 2)
            salt = bytes.fromhex(salt_hex)
            expected_digest = bytes.fromhex(digest_hex)
            actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
            return hmac.compare_digest(actual_digest, expected_digest), False
        except (ValueError, TypeError):
            return False, False

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
        return user_info

    # --- EKRAN LOGOWANIA ---
    def show_login_dialog(self):
        self.withdraw()

        login_win = ctk.CTkToplevel(self)
        login_win.title("CS2 PROTOCOL — ZALOGUJ SIĘ")
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

        def check_login():
            user = entry_username.get().strip()
            pwd = entry_password.get().strip()

            if user in self.users:
                user_info = self.get_user_data(user)
                password_matches, is_legacy_password = self.verify_password(pwd, user_info.get("password", ""))
                if password_matches:
                    self.current_user = user
                    if is_legacy_password:
                        user_info["password"] = self.hash_password(pwd)
                        self.save_users()
                    self.load_user_training_data()
                    self.session_timer_seconds = 0
                    self.refresh_timer_displays()
                    self.lbl_user_info.configure(text=f"{self.current_user}")
                    login_win.destroy()
                    
                    # Ładowanie profilu i avatara zalogowanego użytkownika
                    self.load_user_profile_data()

                    # Jeśli zalogował się admin - dodajemy zakładkę Administratora
                    if self.current_user == "admin":
                        if not hasattr(self, "tab_admin"):
                            self.tab_admin = self.tabview.add("🛡️ Panel Administratora")
                            self.setup_admin_tab()
                    
                    self.deiconify()
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

        login_win.bind("<Return>", lambda event: check_login())

    # --- SYSTEM WYLOGOWANIA ---
    def logout(self):
        self.stop_timer()
        if self.current_user:
            self.save_data()
        self.current_user = None
        self.data = self.empty_training_data()
        self.session_timer_seconds = 0
        
        if hasattr(self, "tab_admin"):
            try:
                self.tabview.delete("🛡️ Panel Administratora")
            except Exception:
                pass
            delattr(self, "tab_admin")

        self.show_login_dialog()

    @staticmethod
    def empty_training_data():
        return {
            "active": [],
            "completed_count": 0,
            "total_minutes_spent": 0,
            "fatigue_score": 0
        }

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    if isinstance(loaded_data, dict) and isinstance(loaded_data.get("users"), dict):
                        return loaded_data
                    return {"users": {"admin": loaded_data}}
            except Exception:
                pass
        return {"users": {}}

    def load_user_training_data(self):
        user_data = self.training_data.setdefault("users", {}).get(self.current_user)
        if not isinstance(user_data, dict):
            user_data = self.empty_training_data()
            self.training_data["users"][self.current_user] = user_data
        self.data = user_data
        self.save_data()

    def save_data(self):
        if not self.current_user:
            return
        self.training_data.setdefault("users", {})[self.current_user] = self.data
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.training_data, f, ensure_ascii=False, indent=4)

    # --- ZAKŁADKA 1: Centrum Dowodzenia ---
    def setup_dashboard(self):
        header = ctk.CTkLabel(
            self.tab_dashboard, 
            text="CS2 PERFORMANCE & AIM PROTOCOL", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        header.pack(pady=(10, 5))

        self.stats_summary_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="#1E293B")
        self.stats_summary_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_plan_time = ctk.CTkLabel(self.stats_summary_frame, text="Plan: 0 min", font=ctk.CTkFont(size=14, weight="bold"), text_color="#3B82F6")
        self.lbl_plan_time.pack(side="left", padx=15, pady=10)

        self.lbl_completed = ctk.CTkLabel(self.stats_summary_frame, text="Ukończone: 0", font=ctk.CTkFont(size=14, weight="bold"), text_color="#10B981")
        self.lbl_completed.pack(side="left", padx=15, pady=10)

        self.lbl_fatigue = ctk.CTkLabel(self.stats_summary_frame, text="Wskaźnik Potu: 0 XP", font=ctk.CTkFont(size=14, weight="bold"), text_color="#F59E0B")
        self.lbl_fatigue.pack(side="left", padx=15, pady=10)

        self.lbl_session_timer = ctk.CTkLabel(
            self.stats_summary_frame, 
            text="⏱️ Aktywny Trening: 00:00", 
            font=ctk.CTkFont(size=14, weight="bold"), 
            text_color="#EF4444"
        )
        self.lbl_session_timer.pack(side="right", padx=20, pady=10)

        form_frame = ctk.CTkFrame(self.tab_dashboard)
        form_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(form_frame, text="Moduł:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=10)
        self.entry_custom_type = ctk.CTkOptionMenu(
            form_frame, 
            values=[
                "Aim Botz (1000 Kills / Fast Taps)", 
                "Aim Lab (Gridshot / Microflex)", 
                "Recoil Master (AK47 Spray Control)", 
                "CS2 Workshop (Prefire Maps)", 
                "DM Headshot Only (FFA)", 
                "KZ / Surf (Movement)"
            ],
            width=260
        )
        self.entry_custom_type.grid(row=0, column=1, padx=10, pady=10)

        ctk.CTkLabel(form_frame, text="Czas (min):", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=10, pady=10)
        self.entry_custom_duration = ctk.CTkEntry(form_frame, placeholder_text="20", width=80)
        self.entry_custom_duration.grid(row=0, column=3, padx=10, pady=10)

        btn_add = ctk.CTkButton(form_frame, text="+ Dodaj Moduł", command=self.add_custom_order, font=ctk.CTkFont(weight="bold"))
        btn_add.grid(row=0, column=4, padx=15, pady=10)

        self.orders_scroll = ctk.CTkScrollableFrame(self.tab_dashboard, label_text="Aktualny Plan Treningowy (Kliknij START przy module)")
        self.orders_scroll.pack(fill="both", expand=True, padx=10, pady=10)

    # --- ZAKŁADKA 2: Gotowe Rutyny Pro ---
    def setup_presets(self):
        header = ctk.CTkLabel(self.tab_presets, text="GOTOWE PROTOKOŁY E-SPORTOWE", font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(pady=15)

        for preset_name, tasks in PRESET_PROTOCOLS.items():
            card = ctk.CTkFrame(self.tab_presets)
            card.pack(fill="x", padx=15, pady=10)

            title = ctk.CTkLabel(card, text=preset_name, font=ctk.CTkFont(size=16, weight="bold"), text_color="#3B82F6")
            title.pack(anchor="w", padx=15, pady=(10, 5))

            desc_text = " • " + "\n • ".join([f"{t['type']} ({t['duration']} min)" for t in tasks])
            desc = ctk.CTkLabel(card, text=desc_text, justify="left", font=ctk.CTkFont(size=13))
            desc.pack(anchor="w", padx=15, pady=5)

            btn_load = ctk.CTkButton(
                card, 
                text="Załaduj Ten Protokół", 
                fg_color="#8B5CF6", 
                hover_color="#7C3AED",
                font=ctk.CTkFont(weight="bold"),
                command=lambda p=tasks: self.load_preset_protocol(p)
            )
            btn_load.pack(anchor="e", padx=15, pady=10)

    # --- ZAKŁADKA 3: Statystyki ---
    def setup_stats(self):
        header = ctk.CTkLabel(self.tab_stats, text="PROGRESSION & FATIGUE ANALYTICS", font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(pady=15)

        self.stats_card = ctk.CTkFrame(self.tab_stats)
        self.stats_card.pack(fill="x", padx=20, pady=10)

        self.lbl_stat_time = ctk.CTkLabel(self.stats_card, text="Łączny czas spędzony w treningu: 0 minut", font=ctk.CTkFont(size=15, weight="bold"))
        self.lbl_stat_time.pack(anchor="w", padx=20, pady=10)

        self.lbl_stat_xp = ctk.CTkLabel(self.stats_card, text="Zdobyte Punkty Potu (Intensity XP): 0 XP", font=ctk.CTkFont(size=15, weight="bold"), text_color="#F59E0B")
        self.lbl_stat_xp.pack(anchor="w", padx=20, pady=10)

        advice_card = ctk.CTkFrame(self.tab_stats, fg_color="#0F172A")
        advice_card.pack(fill="both", expand=True, padx=20, pady=15)

        ctk.CTkLabel(advice_card, text="💡 ZASADY REGENERACJI PRO:", font=ctk.CTkFont(size=16, weight="bold"), text_color="#10B981").pack(anchor="w", padx=15, pady=10)
        advice_txt = (
            "1. Po każdych 45 minutach intensywnego treningu aimu zrób 10 minut przerwy dla mięśni dłoni.\n"
            "2. Dbaj o nawodnienie – brak płynów obniża czas reakcji o ponad 12%.\n"
            "3. Skupiaj się na precyzji (placement celownika), a nie tylko na szybkości."
        )
        ctk.CTkLabel(advice_card, text=advice_txt, justify="left", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=15, pady=5)

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

        btn_choose_avatar = ctk.CTkButton(
            left_col, 
            text="📷 Wybierz Avatar", 
            command=self.choose_avatar_file,
            fg_color="#3B82F6",
            hover_color="#2563EB",
            font=ctk.CTkFont(weight="bold")
        )
        btn_choose_avatar.pack(pady=10)

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

        ctk.CTkLabel(f_form, text="Data urodzenia (YYYY-MM-DD):", font=ctk.CTkFont(weight="bold")).grid(row=2, column=0, sticky="w", pady=5)
        self.entry_birth_date = ctk.CTkEntry(f_form, width=220, placeholder_text="2000-01-01")
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

    def choose_avatar_file(self):
        file_path = filedialog.askopenfilename(
            title="Wybierz zdjęcie profilowe",
            filetypes=[("Pliki graficzne", "*.png *.jpg *.jpeg *.bmp")]
        )
        if file_path and self.current_user:
            user_info = self.get_user_data(self.current_user)
            user_info["avatar_path"] = file_path
            self.save_users()
            self.load_user_profile_data()
            if hasattr(self, "refresh_users_list"):
                self.refresh_users_list()
            self.lbl_profile_status.configure(text="✓ Zaktualizowano avatar profilowy!", text_color="#10B981")

    def load_user_profile_data(self):
        if not self.current_user:
            return

        user_info = self.get_user_data(self.current_user)

        self.entry_first_name.delete(0, "end")
        self.entry_first_name.insert(0, user_info.get("first_name", ""))

        self.entry_last_name.delete(0, "end")
        self.entry_last_name.insert(0, user_info.get("last_name", ""))

        self.entry_birth_date.delete(0, "end")
        self.entry_birth_date.insert(0, user_info.get("birth_date", ""))

        self.entry_old_pass.delete(0, "end")
        self.entry_new_pass.delete(0, "end")

        avatar_path = user_info.get("avatar_path", "")
        if avatar_path and os.path.exists(avatar_path):
            try:
                img = Image.open(avatar_path)
                
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

    def save_profile_info(self):
        if not self.current_user:
            return

        user_info = self.get_user_data(self.current_user)
        user_info["first_name"] = self.entry_first_name.get().strip()
        user_info["last_name"] = self.entry_last_name.get().strip()
        user_info["birth_date"] = self.entry_birth_date.get().strip()

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

        if user_info.get("password") != old_p:
            self.lbl_profile_status.configure(text="❌ Podane obecne hasło jest nieprawidłowe!", text_color="#EF4444")
            return

        user_info["password"] = new_p
        self.save_users()

        self.entry_old_pass.delete(0, "end")
        self.entry_new_pass.delete(0, "end")
        self.lbl_profile_status.configure(text="✓ Hasło zostało pomyślnie zmienione!", text_color="#10B981")

    # --- ZAKŁADKA 5: Panel Administratora (AWATAR OBOK NAZWY UŻYTKOWNIKA) ---
    def setup_admin_tab(self):
        header = ctk.CTkLabel(self.tab_admin, text="🛡️ PANEL ADMINISTRATORA — ZARZĄDZANIE SYSTEMEM", font=ctk.CTkFont(size=22, weight="bold"))
        header.pack(pady=10)

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

    def refresh_users_list(self):
        for widget in self.users_scroll.winfo_children():
            widget.destroy()

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
                    img = Image.open(avatar_path)
                    avatar_img_list = ctk.CTkImage(light_image=img, dark_image=img, size=(28, 28))
                    lbl_avatar.configure(image=avatar_img_list)
                except Exception:
                    lbl_avatar.configure(text="👤")
            else:
                lbl_avatar.configure(text="👤")

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
            entry_pass.insert(0, password)
            entry_pass.pack(side="left", padx=5, pady=5)

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

    def edit_user(self, old_username, new_username, new_password):
        if not new_username or not new_password:
            self.lbl_admin_msg.configure(text="❌ Login i Hasło nie mogą być puste!", text_color="#EF4444")
            return

        if old_username == "admin" and new_username != "admin":
            self.lbl_admin_msg.configure(text="❌ Nie można zmienić loginu konta Administratora!", text_color="#EF4444")
            self.refresh_users_list()
            return

        if new_username != old_username and new_username in self.users:
            self.lbl_admin_msg.configure(text=f"❌ Użytkownik '{new_username}' już istnieje!", text_color="#EF4444")
            return

        user_data = self.get_user_data(old_username)
        user_data["password"] = new_password

        if new_username != old_username:
            del self.users[old_username]
            self.users[new_username] = user_data
            if self.current_user == old_username:
                self.current_user = new_username

        self.save_users()
        self.lbl_admin_msg.configure(text=f"✓ Pomyślnie zaktualizowano konto: {new_username}", text_color="#10B981")
        self.refresh_users_list()

    def delete_user(self, username):
        if username == "admin":
            self.lbl_admin_msg.configure(text="❌ Nie można usunąć konta administratora!", text_color="#EF4444")
            return

        if username in self.users:
            del self.users[username]
            self.save_users()
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
            "password": new_password,
            "first_name": "",
            "last_name": "",
            "birth_date": "",
            "avatar_path": ""
        }
        self.save_users()

        self.new_user_entry.delete(0, "end")
        self.new_pass_entry.delete(0, "end")
        self.lbl_admin_msg.configure(text=f"✓ Pomyślnie utworzono konto dla: {new_username}", text_color="#10B981")
        
        self.refresh_users_list()

    # --- Zegar Systemowy ---
    def update_realtime_clock(self):
        now = datetime.now().strftime("%Y-%m-%d | %H:%M:%S")
        if hasattr(self, "lbl_clock"):
            self.lbl_clock.configure(text=f"📅 Aktualny czas systemowy: {now}")
        self.after(1000, self.update_realtime_clock)

    # --- OBSŁUGA STOPERA DLA MODUŁÓW I SESJI ---
    def toggle_task_timer(self, index):
        if self.active_timer_index == index:
            self.stop_timer()
            self.refresh_ui()
        else:
            self.stop_timer()
            self.active_timer_index = index
            self.task_timer_seconds = 0
            self.run_timer()
            self.refresh_ui()

    def stop_timer(self):
        if self.timer_job:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        self.active_timer_index = None

    def run_timer(self):
        if self.active_timer_index is not None:
            self.task_timer_seconds += 1
            self.session_timer_seconds += 1
            self.refresh_timer_displays()
            self.timer_job = self.after(1000, self.run_timer)

    def refresh_timer_displays(self):
        hrs = self.session_timer_seconds // 3600
        s_mins = (self.session_timer_seconds % 3600) // 60
        s_secs = self.session_timer_seconds % 60
        
        if hasattr(self, "lbl_admin_session_time"):
            self.lbl_admin_session_time.configure(text=f"⏳ Czas obecnej sesji użytkownika: {hrs:02d}:{s_mins:02d}:{s_secs:02d}")

        self.lbl_session_timer.configure(text=f"⏱️ Aktywny Trening: {s_mins:02d}:{s_secs:02d}")

        if self.active_timer_index is not None and hasattr(self, "current_timer_label"):
            t_mins = self.task_timer_seconds // 60
            t_secs = self.task_timer_seconds % 60
            if self.current_timer_label.winfo_exists():
                self.current_timer_label.configure(text=f"⏱️ {t_mins:02d}:{t_secs:02d}")

    # --- LOGIKA ZDAREŃ ---
    def load_preset_protocol(self, tasks):
        for t in tasks:
            self.data["active"].append({"type": t["type"], "duration": t["duration"]})
        self.save_data()
        self.refresh_ui()
        self.tabview.set("⚡ Centrum Dowodzenia")

    def add_custom_order(self):
        t_type = self.entry_custom_type.get()
        dur_str = self.entry_custom_duration.get().strip()
        dur = int(dur_str) if dur_str.isdigit() else 15

        self.data["active"].append({"type": t_type, "duration": dur})
        self.save_data()
        self.refresh_ui()
        self.entry_custom_duration.delete(0, "end")

    def complete_order(self, index):
        if 0 <= index < len(self.data["active"]):
            if self.active_timer_index == index:
                self.stop_timer()
            elif self.active_timer_index is not None and self.active_timer_index > index:
                self.active_timer_index -= 1

            completed_task = self.data["active"].pop(index)
            self.data["completed_count"] += 1
            self.data["total_minutes_spent"] += completed_task["duration"]
            self.data["fatigue_score"] += completed_task["duration"] * 12

            self.save_data()
            self.refresh_ui()

    def refresh_ui(self):
        for widget in self.orders_scroll.winfo_children():
            widget.destroy()

        total_min = 0
        for i, order in enumerate(self.data["active"]):
            total_min += order["duration"]

            card = ctk.CTkFrame(self.orders_scroll)
            card.pack(fill="x", padx=10, pady=5)

            lbl = ctk.CTkLabel(card, text=f"• {order['type']} — {order['duration']} min", font=ctk.CTkFont(size=14, weight="bold"))
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
            btn_timer_text = "PAUZA ⏸️" if is_running else "START 🚀"
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

            if is_running:
                t_mins = self.task_timer_seconds // 60
                t_secs = self.task_timer_seconds % 60
                self.current_timer_label = ctk.CTkLabel(
                    card, 
                    text=f"⏱️ {t_mins:02d}:{t_secs:02d}", 
                    font=ctk.CTkFont(size=16, weight="bold"), 
                    text_color="#EF4444"
                )
                self.current_timer_label.pack(side="right", padx=10)

        self.lbl_plan_time.configure(text=f"Plan: {total_min} min")
        self.lbl_completed.configure(text=f"Ukończone: {self.data['completed_count']}")
        self.lbl_fatigue.configure(text=f"Wskaźnik Potu: {self.data['fatigue_score']} XP")
        
        self.lbl_stat_time.configure(text=f"Łączny czas spędzony w treningu: {self.data['total_minutes_spent']} minut")
        self.lbl_stat_xp.configure(text=f"Zdobyte Punkty Potu (Intensity XP): {self.data['fatigue_score']} XP")

if __name__ == "__main__":
    app = CS2ProTrainingApp()
    app.mainloop()