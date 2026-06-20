from urllib.parse import urlencode

import hashlib
import hmac
import json

from chips_bot.mini_app import (
    PendingNewGame,
    build_new_game_url,
    cleanup_expired_setups,
    validate_telegram_init_data,
    url_origin,
)


def signed_init_data(bot_token: str, fields: dict[str, str]) -> str:
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})


def test_validate_telegram_init_data_returns_signed_user():
    bot_token = "123:test-token"
    user = {"id": 42, "first_name": "Ada"}
    init_data = signed_init_data(bot_token, {"auth_date": "1000", "user": json.dumps(user, separators=(",", ":"))})

    assert validate_telegram_init_data(init_data, bot_token, now=1000) == user


def test_validate_telegram_init_data_rejects_tampering():
    bot_token = "123:test-token"
    init_data = signed_init_data(bot_token, {"auth_date": "1000", "user": json.dumps({"id": 42})})
    tampered = init_data.replace("42", "43")

    try:
        validate_telegram_init_data(tampered, bot_token, now=1000)
    except ValueError as exc:
        assert "verification failed" in str(exc).lower()
    else:
        raise AssertionError("Tampered init data should not validate")


def test_build_new_game_url_preserves_existing_query():
    assert build_new_game_url("https://example.test/mini-app?theme=dark", "abc") == "https://example.test/mini-app?theme=dark&token=abc"


def test_url_origin_removes_path_query_and_fragment():
    assert url_origin("https://frontend.example.test/mini-app?x=1#top") == "https://frontend.example.test"


def test_cleanup_expired_setups_removes_only_expired_tokens():
    pending = {
        "old": PendingNewGame(chat_id=1, host_user_id=2, host_display_name="Old", expires_at=10),
        "new": PendingNewGame(chat_id=1, host_user_id=2, host_display_name="New", expires_at=30),
    }

    cleanup_expired_setups(pending, now=20)

    assert list(pending) == ["new"]