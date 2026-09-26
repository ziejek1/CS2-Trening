import json
import copy
import mimetypes
import os
import urllib.parse
import urllib.request


class CloudDataService:
    def __init__(self, base_url, anon_key):
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key

    @property
    def enabled(self):
        return bool(self.base_url and self.anon_key)

    def _request(self, method, path, payload=None, prefer="return=representation"):
        url = f"{self.base_url}/rest/v1/{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("apikey", self.anon_key)
        request.add_header("Authorization", f"Bearer {self.anon_key}")
        request.add_header("Content-Type", "application/json")
        request.add_header("Prefer", prefer)
        with urllib.request.urlopen(request, timeout=8) as response:
            content = response.read().decode("utf-8")
            return json.loads(content) if content else []

    def get_user_data(self, username):
        encoded_username = urllib.parse.quote(username, safe="")
        rows = self._request("GET", f"user_training_data?select=username,data&username=eq.{encoded_username}")
        return rows[0].get("data") if rows else None

    def get_all_users(self):
        rows = self._request("GET", "app_users?select=username,data&order=username.asc")
        return {
            row["username"]: row.get("data", {})
            for row in rows
            if row.get("username") and isinstance(row.get("data"), dict)
        }

    def save_user_account(self, username, data):
        return self._request(
            "POST",
            "app_users?on_conflict=username",
            {"username": username, "data": data},
            prefer="return=minimal,resolution=merge-duplicates"
        )

    def delete_user_account(self, username):
        encoded_username = urllib.parse.quote(username, safe="")
        return self._request(
            "DELETE",
            f"app_users?username=eq.{encoded_username}",
            prefer="return=minimal"
        )

    def upload_avatar(self, username, file_path):
        extension = os.path.splitext(file_path)[1].lower() or ".jpg"
        object_name = f"{urllib.parse.quote(username, safe='')}{extension}"
        with open(file_path, "rb") as avatar_file:
            body = avatar_file.read()
        content_type = mimetypes.guess_type(file_path)[0] or "image/jpeg"
        url = f"{self.base_url}/storage/v1/object/avatars/{object_name}"
        request = urllib.request.Request(url, data=body, method="POST")
        request.add_header("apikey", self.anon_key)
        request.add_header("Authorization", f"Bearer {self.anon_key}")
        request.add_header("Content-Type", content_type)
        request.add_header("x-upsert", "true")
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
        return f"{self.base_url}/storage/v1/object/public/avatars/{object_name}"

    def get_all_data(self):
        rows = self._request("GET", "user_training_data?select=username,data")
        return {
            row["username"]: row.get("data", {})
            for row in rows
            if row.get("username")
        }

    def save_user_data(self, username, data):
        return self._request(
            "POST",
            "user_training_data?on_conflict=username",
            {"username": username, "data": data},
            prefer="return=minimal,resolution=merge-duplicates"
        )

    def get_shared_config(self):
        rows = self._request("GET", "app_shared_config?select=id,data&id=eq.main")
        return rows[0].get("data") if rows else None

    def save_shared_config(self, data):
        return self._request(
            "POST",
            "app_shared_config?on_conflict=id",
            {"id": "main", "data": data},
            prefer="return=minimal,resolution=merge-duplicates"
        )


def merge_training_data(local_data, cloud_data):
    """Merge two device histories without letting an empty cloud record erase local progress."""
    local_data = local_data if isinstance(local_data, dict) else {}
    cloud_data = cloud_data if isinstance(cloud_data, dict) else {}
    merged = copy.deepcopy(local_data)

    history = []
    seen_history = set()
    for item in local_data.get("completion_history", []) + cloud_data.get("completion_history", []):
        if not isinstance(item, dict):
            continue
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen_history:
            seen_history.add(key)
            history.append(copy.deepcopy(item))
    merged["completion_history"] = history

    history_seconds = sum(int(item.get("duration_seconds", 0) or 0) for item in history)
    merged["total_seconds_spent"] = max(
        history_seconds,
        int(local_data.get("total_seconds_spent", 0) or 0),
        int(cloud_data.get("total_seconds_spent", 0) or 0)
    )
    merged["total_minutes_spent"] = merged["total_seconds_spent"] // 60
    history_xp = sum(int(item.get("duration", 0) or 0) * 12 for item in history)
    merged["fatigue_score"] = max(
        history_xp,
        int(local_data.get("fatigue_score", 0) or 0),
        int(cloud_data.get("fatigue_score", 0) or 0)
    )
    merged["completed_count"] = max(
        len(history),
        int(local_data.get("completed_count", 0) or 0),
        int(cloud_data.get("completed_count", 0) or 0)
    )
    for field in ("custom_routines", "scheduled_plans"):
        local_items = local_data.get(field, [])
        cloud_items = cloud_data.get(field, [])
        if isinstance(local_items, list) and isinstance(cloud_items, list):
            merged_items = copy.deepcopy(local_items)
            existing = {json.dumps(item, ensure_ascii=False, sort_keys=True) for item in merged_items}
            for item in cloud_items:
                key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if key not in existing:
                    merged_items.append(copy.deepcopy(item))
            merged[field] = merged_items
    return merged
