from __future__ import annotations

import json
import threading

import cv2
import numpy as np
import requests

from .i18n import Translator


class DiscordError(RuntimeError):
    pass


class DiscordNotifier:
    def __init__(
        self,
        webhook_url: str = "",
        timeout_seconds: float = 12,
        translator: Translator | None = None,
    ):
        self.webhook_url = webhook_url.strip()
        self.timeout_seconds = timeout_seconds
        self.tr = translator or Translator()
        self._lock = threading.Lock()

    def set_webhook(self, webhook_url: str) -> None:
        with self._lock:
            self.webhook_url = webhook_url.strip()

    @property
    def configured(self) -> bool:
        return self.webhook_url.startswith("https://discord.com/api/webhooks/")

    def send(self, content: str, frame: np.ndarray | None = None) -> None:
        with self._lock:
            webhook_url = self.webhook_url
        if not webhook_url:
            raise DiscordError(self.tr("error.webhook_missing"))
        if not webhook_url.startswith("https://discord.com/api/webhooks/"):
            raise DiscordError(self.tr("error.webhook_invalid"))

        payload = {
            "content": content[:1900],
            "allowed_mentions": {"parse": []},
        }
        files = None
        if frame is not None:
            ok, encoded = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88]
            )
            if ok:
                files = {
                    "files[0]": (
                        "digimon-alert.jpg",
                        encoded.tobytes(),
                        "image/jpeg",
                    )
                }
        try:
            response = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload, ensure_ascii=False)},
                files=files,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise DiscordError(
                self.tr("error.discord_connect", error=exc)
            ) from exc
        if response.status_code not in (200, 204):
            detail = response.text[:300].strip()
            raise DiscordError(
                self.tr(
                    "error.discord_http",
                    status=response.status_code,
                    detail=f": {detail}" if detail else "",
                )
            )
