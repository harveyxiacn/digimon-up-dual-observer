from unittest.mock import patch

import numpy as np
import pytest
import requests

from digimon_monitor.discord_notifier import DiscordError, DiscordNotifier


URL = "https://discord.com/api/webhooks/123456789/token_safe-1"


class Response:
    def __init__(self, status_code, *, headers=None, body=None, text=""):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body
        self.text = text

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


@pytest.mark.parametrize(
    "url",
    [
        URL,
        "https://discord.com/api/webhooks/1/a-b_c.d~e",
    ],
)
def test_valid_webhook_urls(url):
    assert DiscordNotifier.is_valid_webhook_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://discord.com/api/webhooks/1/token",
        "https://evil.discord.com/api/webhooks/1/token",
        "https://discord.com.evil.test/api/webhooks/1/token",
        "https://discord.com/api/webhooks//token",
        "https://discord.com/api/webhooks/1/",
        "https://discord.com/api/webhooks/1/token?x=1",
        "https://discord.com/api/webhooks/1/token?",
        "https://discord.com/api/webhooks/1/token#",
        "https://user:pass@discord.com/api/webhooks/1/token",
        "https://discord.com/api/webhooks/1/token\n",
    ],
)
def test_invalid_webhook_urls(url):
    assert not DiscordNotifier.is_valid_webhook_url(url)


def test_json_payload_without_attachment():
    response = Response(200)
    with patch("digimon_monitor.discord_notifier.requests.post", return_value=response) as post:
        DiscordNotifier(URL).send("hello")
    assert post.call_args.kwargs["json"] == {
        "content": "hello",
        "allowed_mentions": {"parse": []},
    }
    assert "files" not in post.call_args.kwargs
    assert "data" not in post.call_args.kwargs


def test_jpeg_attachment_uses_multipart():
    with patch("digimon_monitor.discord_notifier.requests.post", return_value=Response(204)) as post:
        DiscordNotifier(URL).send("hello", np.zeros((4, 4, 3), dtype=np.uint8))
    kwargs = post.call_args.kwargs
    assert "json" not in kwargs
    assert "payload_json" in kwargs["data"]
    assert kwargs["files"]["files[0]"][2] == "image/jpeg"


def test_encode_failure_falls_back_to_json():
    with patch("digimon_monitor.discord_notifier.cv2.imencode", return_value=(False, None)):
        with patch("digimon_monitor.discord_notifier.requests.post", return_value=Response(200)) as post:
            DiscordNotifier(URL).send("hello", np.zeros((2, 2, 3), dtype=np.uint8))
    assert "json" in post.call_args.kwargs
    assert "files" not in post.call_args.kwargs


@pytest.mark.parametrize("status", [200, 204])
def test_success_statuses(status):
    with patch("digimon_monitor.discord_notifier.requests.post", return_value=Response(status)):
        DiscordNotifier(URL).send("ok")


def test_network_error_message_does_not_leak_webhook():
    secret = URL + "/secret"
    with patch(
        "digimon_monitor.discord_notifier.requests.post",
        side_effect=requests.ConnectionError(secret),
    ):
        with pytest.raises(DiscordError) as caught:
            DiscordNotifier(URL).send("hello")
    assert secret not in str(caught.value)


def test_http_error_message_does_not_leak_response_body():
    secret = "token_secret_response"
    with patch(
        "digimon_monitor.discord_notifier.requests.post",
        return_value=Response(500, text=secret),
    ):
        with pytest.raises(DiscordError) as caught:
            DiscordNotifier(URL).send("hello")
    assert "500" in str(caught.value)
    assert secret not in str(caught.value)


def test_rate_limit_header_and_json_retry_after():
    notifier = DiscordNotifier(URL)
    with patch(
        "digimon_monitor.discord_notifier.requests.post",
        return_value=Response(429, headers={"Retry-After": "2.5"}),
    ) as post:
        with pytest.raises(DiscordError) as caught:
            notifier.send("hello")
        assert caught.value.retry_after_seconds == pytest.approx(2.5)
        with pytest.raises(DiscordError):
            notifier.send("again")
    assert post.call_count == 1

    notifier = DiscordNotifier(URL)
    with patch(
        "digimon_monitor.discord_notifier.requests.post",
        return_value=Response(429, body={"retry_after": 1.25}),
    ):
        with pytest.raises(DiscordError) as caught:
            notifier.send("hello")
    assert caught.value.retry_after_seconds == pytest.approx(1.25)


def test_set_webhook_clears_rate_limit_state():
    new_url = "https://discord.com/api/webhooks/999999/new_token"
    with patch(
        "digimon_monitor.discord_notifier.requests.post",
        side_effect=[Response(429, headers={"Retry-After": "30"}), Response(204)],
    ) as post:
        notifier = DiscordNotifier(URL)
        with pytest.raises(DiscordError):
            notifier.send("limited")
        notifier.set_webhook(new_url)
        notifier.send("new webhook")
    assert post.call_count == 2


def test_permanent_error_blocks_until_webhook_changes():
    new_url = "https://discord.com/api/webhooks/999999/new_token"
    with patch(
        "digimon_monitor.discord_notifier.requests.post",
        side_effect=[Response(401), Response(204)],
    ) as post:
        notifier = DiscordNotifier(URL)
        with pytest.raises(DiscordError) as caught:
            notifier.send("hello")
        assert caught.value.permanent
        with pytest.raises(DiscordError):
            notifier.send("again")
        notifier.set_webhook(new_url)
        notifier.send("recovered")
    assert post.call_count == 2
