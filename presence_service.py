import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


class PresenceService:
    def __init__(self, base_url, anon_key, ttl_seconds=90):
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key
        self.ttl_seconds = ttl_seconds

    @property
    def enabled(self):
        return bool(self.base_url and self.anon_key)

    def _request(self, method, path, payload=None):
        url = f"{self.base_url}/rest/v1/{path}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("apikey", self.anon_key)
        request.add_header("Authorization", f"Bearer {self.anon_key}")
        request.add_header("Content-Type", "application/json")
        request.add_header("Prefer", "return=representation,resolution=merge-duplicates")
        with urllib.request.urlopen(request, timeout=8) as response:
            content = response.read().decode("utf-8")
            return json.loads(content) if content else []

    def heartbeat(self, username):
        timestamp = datetime.now(timezone.utc).isoformat()
        return self._request(
            "POST",
            "user_presence?on_conflict=username",
            {"username": username, "last_seen": timestamp}
        )

    def remove(self, username):
        encoded_username = urllib.parse.quote(username, safe="")
        return self._request("DELETE", f"user_presence?username=eq.{encoded_username}")

    def online_users(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=self.ttl_seconds)).isoformat()
        encoded_cutoff = urllib.parse.quote(cutoff, safe="")
        result = self._request(
            "GET",
            f"user_presence?select=username,last_seen&last_seen=gt.{encoded_cutoff}&order=username.asc"
        )
        return [item["username"] for item in result if item.get("username")]
