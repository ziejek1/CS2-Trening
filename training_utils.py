from collections import defaultdict
from datetime import datetime, timedelta

from app_constants import CS2_RANKS, SKILL_CATEGORIES


def get_total_seconds(training_data):
    if "total_seconds_spent" in training_data:
        return int(training_data.get("total_seconds_spent", 0))
    return int(training_data.get("total_minutes_spent", 0)) * 60


def parse_completion_date(item):
    try:
        return datetime.strptime(item.get("date", ""), "%Y-%m-%d").date()
    except (AttributeError, TypeError, ValueError):
        return None


def get_weekly_training_totals(training_data, today=None):
    today = today or datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    next_week = week_start + timedelta(days=7)
    completed_count = 0
    total_seconds = 0
    for item in training_data.get("completion_history", []):
        completed_date = parse_completion_date(item)
        if completed_date is None or not week_start <= completed_date < next_week:
            continue
        completed_count += 1
        try:
            duration_seconds = int(item.get("duration_seconds", int(item.get("duration", 0)) * 60))
        except (AttributeError, TypeError, ValueError):
            duration_seconds = 0
        total_seconds += max(0, duration_seconds)
    return completed_count, total_seconds


def get_training_chart_data(training_data, period="week", today=None):
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
        completed_date = parse_completion_date(item)
        if completed_date is None or not start_date <= completed_date <= today:
            continue
        daily_completed[completed_date] += 1
        try:
            duration_seconds = int(item.get("duration_seconds", int(item.get("duration", 0)) * 60))
        except (AttributeError, TypeError, ValueError):
            duration_seconds = 0
        daily_seconds[completed_date] += max(0, duration_seconds)
    return labels, [daily_seconds[date] / 60 for date in dates], [daily_completed[date] for date in dates]


def get_training_dates(training_data):
    return {
        completed_date
        for item in training_data.get("completion_history", [])
        if (completed_date := parse_completion_date(item)) is not None
    }


def get_longest_training_streak(training_data):
    completed_dates = get_training_dates(training_data)
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


def get_current_training_streak(training_data, today=None):
    today = today or datetime.now().date()
    training_dates = get_training_dates(training_data)
    if not training_dates:
        return 0
    streak_end = today if today in training_dates else today - timedelta(days=1)
    if streak_end not in training_dates:
        return 0
    streak = 0
    while streak_end - timedelta(days=streak) in training_dates:
        streak += 1
    return streak


def get_training_badges(training_data):
    longest_streak = get_longest_training_streak(training_data)
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


def get_rank_for_xp(xp):
    current_rank = CS2_RANKS[0][1]
    for required_xp, rank_name in CS2_RANKS:
        if xp >= required_xp:
            current_rank = rank_name
        else:
            break
    return current_rank


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


def get_task_category(task):
    category = task.get("category") if isinstance(task, dict) else None
    return category if category in SKILL_CATEGORIES else infer_skill_category(
        task.get("type", "") if isinstance(task, dict) else task
    )
