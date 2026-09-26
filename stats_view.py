from datetime import datetime, timedelta

import customtkinter as ctk

from app_constants import SKILL_CATEGORIES


class StatsViewMixin:
    def setup_stats_filters(self):
        header = ctk.CTkFrame(self.tab_stats, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(header, text="STATYSTYKI TRENINGOWE", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        self.stats_category_filter = ctk.StringVar(value="Wszystkie")
        ctk.CTkOptionMenu(header, variable=self.stats_category_filter, values=["Wszystkie", *SKILL_CATEGORIES], width=160, command=self.refresh_filtered_stats).pack(side="right")

        date_filters = ctk.CTkFrame(self.tab_stats, fg_color="transparent")
        date_filters.pack(fill="x", padx=20, pady=(0, 5))
        ctk.CTkLabel(date_filters, text="Zakres dat:", text_color="#CBD5E1").pack(side="left", padx=(0, 8))
        self.stats_date_filter = ctk.StringVar(value="Wszystkie")
        self.stats_date_menu = ctk.CTkOptionMenu(date_filters, variable=self.stats_date_filter, values=["Wszystkie", "Dzisiaj", "Ten tydzień", "Ten miesiąc", "Własny zakres"], width=150, command=self.refresh_stats_date_filter)
        self.stats_date_menu.pack(side="left", padx=4)
        ctk.CTkLabel(date_filters, text="Od").pack(side="left", padx=(14, 4))
        self.stats_date_start = ctk.CTkEntry(date_filters, width=105, placeholder_text="DD-MM-RRRR")
        self.stats_date_start.pack(side="left", padx=3)
        ctk.CTkLabel(date_filters, text="Do").pack(side="left", padx=(8, 4))
        self.stats_date_end = ctk.CTkEntry(date_filters, width=105, placeholder_text="DD-MM-RRRR")
        self.stats_date_end.pack(side="left", padx=3)
        self.stats_date_start.bind("<Return>", lambda event: self.refresh_filtered_stats())
        self.stats_date_end.bind("<Return>", lambda event: self.refresh_filtered_stats())
        self.stats_date_start.configure(state="disabled")
        self.stats_date_end.configure(state="disabled")

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

        return [
            item for item in history
            if (selected_category == "Wszystkie" or self.get_task_category(item) == selected_category)
            and (start_date is None or (
                (completed_date := self.parse_completion_date(item)) is not None
                and start_date <= completed_date <= end_date
            ))
        ]

    def refresh_stats_date_filter(self, selected_mode=None):
        state = "normal" if self.stats_date_filter.get() == "Własny zakres" else "disabled"
        self.stats_date_start.configure(state=state)
        self.stats_date_end.configure(state=state)
        self.refresh_filtered_stats()

    def refresh_filtered_stats(self, selected_category=None):
        self.refresh_training_history()
        self.refresh_progress_charts()
