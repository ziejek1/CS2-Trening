import json
import urllib.request


class ChatService:
    def __init__(self, base_url, anon_key):
        self.base_url = base_url.rstrip("/")
        self.anon_key = anon_key

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
        request.add_header("Prefer", "return=representation")
        with urllib.request.urlopen(request, timeout=8) as response:
            content = response.read().decode("utf-8")
            return json.loads(content) if content else []

    def get_messages(self, limit=100):
        return self._request(
            "GET",
            f"chat_messages?select=username,message,created_at&order=created_at.desc,id.desc&limit=10"
        )

    def send_message(self, username, message):
        return self._request(
            "POST",
            "chat_messages",
            {"username": username, "message": message}
        )
