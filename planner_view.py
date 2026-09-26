import secrets
from collections import defaultdict
from datetime import datetime, timedelta
from tkinter import messagebox

import customtkinter as ctk


class PlannerViewMixin:
    def setup_planner_tab(self):
        ctk.CTkLabel(self.tab_planner, text="PLAN TRENINGOWY", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(15, 5))
        ctk.CTkLabel(self.tab_planner, text="Przypisz rutynę do konkretnego dnia i kontroluj jej realizację.", text_color="#94A3B8").pack(pady=(0, 12))
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
        ctk.CTkButton(planner_form, text="+ Zaplanuj rutynę", fg_color="#059669", hover_color="#047857", font=ctk.CTkFont(weight="bold"), command=self.schedule_routine).grid(row=1, column=4, padx=12, pady=(0, 12), sticky="w")
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
        routine_map = {name: tasks for name, tasks in self.get_preset_protocols().items()}
        for routine in self.data.get("custom_routines", []):
            routine_map[routine.get("name", "Własna rutyna")] = routine.get("tasks", [])
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
        for column, weekday in enumerate(("Pon", "Wt", "Śr", "Czw", "Pt", "Sob", "Nd")):
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
            color = "#047857" if any(plan.get("status") == "completed" for plan in plans) else "#B45309" if any(plan.get("status") == "started" for plan in plans) else "#1D4ED8" if plans else "#1E293B"
            position = first_weekday + day - 1
            ctk.CTkButton(self.planner_calendar_body, text=f"{day}\n{len(plans)} planów" if plans else str(day), width=92, height=45, fg_color=color, hover_color="#334155", border_width=2 if selected_date == selected else 0, border_color="#FBBF24", command=lambda selected_day=selected: self.select_planner_date(selected_day)).grid(row=position // 7 + 1, column=position % 7, padx=3, pady=3, sticky="ew")

    def schedule_routine(self):
        try:
            selected_date = datetime.strptime(self.planner_date_entry.get().strip(), "%Y-%m-%d").date()
            selected_time = datetime.strptime(self.planner_time_entry.get().strip(), "%H:%M").strftime("%H:%M")
        except ValueError:
            messagebox.showerror("Nieprawidłowa data lub godzina", "Użyj daty RRRR-MM-DD i godziny HH:MM.", parent=self)
            return
        routine_name = self.planner_routine_menu.get()
        tasks = self.planner_routine_map.get(routine_name)
        if not tasks:
            messagebox.showerror("Brak rutyny", "Najpierw utwórz lub wybierz rutynę.", parent=self)
            return
        self.data.setdefault("scheduled_plans", []).append({"date": selected_date.isoformat(), "routine_name": routine_name, "tasks": [dict(task) for task in tasks], "status": "planned", "plan_id": secrets.token_hex(8), "time": selected_time, "reminder_enabled": bool(self.planner_reminder_enabled.get()), "reminder_notified": False})
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
        if 0 <= plan_index < len(self.data.get("scheduled_plans", [])):
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
        reminder.geometry(f"+{reminder.winfo_screenwidth() - reminder.winfo_width() - 24}+55")
        ctk.CTkLabel(reminder, text="CZAS NA TRENING", font=ctk.CTkFont(size=16, weight="bold"), text_color="#34D399").pack(pady=(16, 4))
        ctk.CTkLabel(reminder, text=routine_name, font=ctk.CTkFont(size=13, weight="bold"), wraplength=330).pack(padx=15, pady=3)
        ctk.CTkButton(reminder, text="Otwórz plan treningowy", width=190, command=lambda: self.open_planner_from_reminder(reminder)).pack(pady=(8, 14))

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
            ctk.CTkLabel(row, text=plan.get("routine_name", "Rutyna") + (f" · {plan_time}" if plan_time else ""), anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left", fill="x", expand=True, padx=8, pady=10)
            ctk.CTkLabel(row, text=status_names.get(status, status.upper()), width=125, text_color=status_colors.get(status, "#CBD5E1"), font=ctk.CTkFont(weight="bold")).pack(side="left", padx=5, pady=10)
            if status == "planned":
                ctk.CTkButton(row, text="Rozpocznij rutynę", width=125, command=lambda plan_index=index: self.start_scheduled_plan(plan_index)).pack(side="right", padx=3, pady=6)
            elif status == "started":
                ctk.CTkButton(row, text="Otwórz trening", width=105, fg_color="#059669", hover_color="#047857", command=lambda plan_index=index: self.open_scheduled_plan_training(plan_index)).pack(side="right", padx=3, pady=6)
            ctk.CTkButton(row, text="Usuń", width=62, fg_color="#991B1B", hover_color="#B91C1C", command=lambda plan_index=index: self.delete_scheduled_plan(plan_index)).pack(side="right", padx=3, pady=6)
