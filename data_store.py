import json
import os

from app_constants import DEFAULT_MODULE_CATALOG, PRESET_PROTOCOLS


def default_users(hash_password):
    return {
        "admin": {
            "password": hash_password("Aa798397463"),
            "first_name": "Administrator",
            "last_name": "Systemu",
            "birth_date": "2000-01-01",
            "avatar_path": ""
        }
    }


def load_users(path, hash_password):
    defaults = default_users(hash_password)
    if not os.path.exists(path):
        save_users(path, defaults)
        return defaults
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        cleaned_users = {}
        for username, user_data in data.items():
            if not isinstance(username, str) or not isinstance(user_data, (dict, str)):
                continue
            if isinstance(user_data, str):
                user_data = {
                    "password": user_data,
                    "first_name": "",
                    "last_name": "",
                    "birth_date": "",
                    "avatar_path": ""
                }
            if isinstance(user_data.get("password"), str):
                cleaned_users[username] = user_data
        return cleaned_users or defaults
    except (OSError, json.JSONDecodeError, AttributeError):
        return defaults


def save_users(path, users):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(users, file, ensure_ascii=False, indent=4)


def load_remembered_login(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as file:
            remembered = json.load(file)
        return remembered if isinstance(remembered, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_remembered_login(path, username, token):
    remembered = {"username": username, "token": token}
    with open(path, "w", encoding="utf-8") as file:
        json.dump(remembered, file, ensure_ascii=False, indent=4)
    return remembered


def clear_remembered_login(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def default_training_data():
    return {
        "users": {},
        "module_catalog": [
            {"name": name, "category": category}
            for name, category in DEFAULT_MODULE_CATALOG
        ],
        "preset_protocols": {
            name: [dict(task) for task in tasks]
            for name, tasks in PRESET_PROTOCOLS.items()
        }
    }


def load_training_data(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                loaded_data = json.load(file)
            if isinstance(loaded_data, dict) and isinstance(loaded_data.get("users"), dict):
                loaded_data.setdefault(
                    "preset_protocols",
                    {name: [dict(task) for task in tasks] for name, tasks in PRESET_PROTOCOLS.items()}
                )
                loaded_data.setdefault(
                    "module_catalog",
                    [{"name": name, "category": category} for name, category in DEFAULT_MODULE_CATALOG]
                )
                return loaded_data
            return {"users": {"admin": loaded_data}, **default_training_data()}
        except (OSError, json.JSONDecodeError):
            pass
    return default_training_data()


def save_training_data(path, training_data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(training_data, file, ensure_ascii=False, indent=4)
