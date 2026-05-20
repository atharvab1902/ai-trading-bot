"""Minimal Telegram notifier. Not a full bot — just one-way alerts from executor → user."""
import os
import requests


class Telegram:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)

    def send(self, text: str):
        if not self.enabled:
            print(f"[telegram disabled] {text}")
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=5,
            )
        except Exception as e:
            print(f"[telegram error] {e}: {text}")
