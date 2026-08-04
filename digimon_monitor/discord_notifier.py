from __future__ import annotations

import json
import re
import threading
import time
from urllib.parse import urlsplit

import cv2
import numpy as np
import requests

from .i18n import Translator


class DiscordError(RuntimeError):
    """A safe, localizable Discord delivery error.

    ``retry_after_seconds`` and ``permanent`` are intentionally kept as
    structured attributes so callers can apply backoff without parsing the
    localized message.
    """

    def __init__(
        self,
        message: str,
        *,
        retry_after_seconds: float | None = None,
        permanent: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.permanent = permanent
        self.status_code = status_code


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
        self._lock = threading.Lock()  # protects webhook and backoff state
        self._send_lock = threading.Lock()  # serializes network requests
        self._permanent_webhook: str | None = None
        self._permanent_status: int | None = None
        self._rate_limited_webhook: str | None = None
        self._rate_limited_until = 0.0

    @staticmethod
    def is_valid_webhook_url(url: str) -> bool:
        """Validate a Discord webhook URL without making a network request."""
        if not isinstance(url, str) or not url:
            return False
        # Reject control characters (including CR/LF) before URL parsing.
        if any(ord(char) < 0x20 or ord(char) == 0x7F for char in url):
            return False
        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            port = parsed.port
        except (TypeError, ValueError):
            return False
        if parsed.scheme.lower() != "https" or hostname != "discord.com":
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        # A port, query string, or fragment is not part of the canonical URL.
        if (
            port is not None
            or parsed.query
            or parsed.fragment
            or "?" in url
            or "#" in url
        ):
            return False
        return re.fullmatch(
            r"/api/webhooks/[0-9]+/[A-Za-z0-9._~-]{1,256}", parsed.path
        ) is not None

    def set_webhook(self, webhook_url: str) -> None:
        with self._lock:
            new_url = webhook_url.strip()
            if new_url != self.webhook_url:
                self._permanent_webhook = None
                self._permanent_status = None
                self._rate_limited_webhook = None
                self._rate_limited_until = 0.0
            self.webhook_url = new_url

    @property
    def configured(self) -> bool:
        with self._lock:
            return self.is_valid_webhook_url(self.webhook_url)

    def send(self, content: str, frame: np.ndarray | None = None) -> None:
        # Serialize requests while keeping set_webhook/configured responsive
        # during a potentially slow network call.
        with self._send_lock:
            with self._lock:
                webhook_url = self.webhook_url
                permanent_webhook = self._permanent_webhook
                permanent_status = self._permanent_status
                rate_webhook = self._rate_limited_webhook
                rate_until = self._rate_limited_until
            if not webhook_url:
                raise DiscordError(self.tr("error.webhook_missing"))
            if not self.is_valid_webhook_url(webhook_url):
                raise DiscordError(self.tr("error.webhook_invalid"))

            if permanent_webhook == webhook_url:
                status = permanent_status or 403
                raise DiscordError(
                    self.tr("error.discord_suspended"),
                    permanent=True,
                    status_code=status,
                )

            now = time.monotonic()
            if rate_webhook == webhook_url:
                remaining = rate_until - now
                if remaining > 0:
                    raise DiscordError(
                        self.tr(
                            "error.discord_rate_limited",
                            seconds=f"{remaining:.1f}",
                        ),
                        retry_after_seconds=remaining,
                        status_code=429,
                    )
                with self._lock:
                    if self._rate_limited_webhook == webhook_url:
                        self._rate_limited_webhook = None
                        self._rate_limited_until = 0.0

            payload = {
                "content": content[:1900],
                "allowed_mentions": {"parse": []},
            }
            files = None
            if frame is not None:
                try:
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
                except Exception:
                    # Encoding failures should still deliver the text alert.
                    files = None
            try:
                if files is None:
                    response = requests.post(
                        webhook_url,
                        json=payload,
                        timeout=self.timeout_seconds,
                    )
                else:
                    response = requests.post(
                        webhook_url,
                        data={
                            "payload_json": json.dumps(
                                payload, ensure_ascii=False
                            )
                        },
                        files=files,
                        timeout=self.timeout_seconds,
                    )
            except requests.RequestException as exc:
                # Never include exception text: requests may echo the webhook.
                raise DiscordError(self.tr("error.discord_connect")) from exc

            status = int(response.status_code)
            if status in (200, 204):
                return

            retry_after = None
            if status == 429:
                try:
                    headers = getattr(response, "headers", {}) or {}
                    header_value = next(
                        (
                            value
                            for key, value in headers.items()
                            if str(key).lower() == "retry-after"
                        ),
                        None,
                    )
                    retry_after = float(header_value)
                except (AttributeError, TypeError, ValueError):
                    retry_after = None
                if retry_after is None:
                    try:
                        body = response.json()
                        value = body.get("retry_after") if isinstance(body, dict) else None
                        retry_after = float(value) if value is not None else None
                    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
                        retry_after = None
                if retry_after is not None and retry_after >= 0:
                    with self._lock:
                        if self.webhook_url == webhook_url:
                            self._rate_limited_webhook = webhook_url
                            # Use post-response time so network latency is not
                            # subtracted from Discord's requested delay.
                            self._rate_limited_until = (
                                time.monotonic() + retry_after
                            )
                else:
                    retry_after = None

            permanent = status in (401, 403, 404)
            if permanent:
                with self._lock:
                    if self.webhook_url == webhook_url:
                        self._permanent_webhook = webhook_url
                        self._permanent_status = status
            raise DiscordError(
                self.tr("error.discord_http", status=status),
                retry_after_seconds=retry_after,
                permanent=permanent,
                status_code=status,
            )
