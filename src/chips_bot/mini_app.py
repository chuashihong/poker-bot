from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telegram import Bot

from chips_bot.db import Database
from chips_bot.handlers.common import decimal_to_storage, game_actions_keyboard, parse_non_negative_decimal
from chips_bot.repositories import games
from chips_bot.settlement import SettlementError


SETUP_TTL_SECONDS = 15 * 60
INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class PendingNewGame:
    chat_id: int
    host_user_id: int
    host_display_name: str
    expires_at: float


class NewGameRequest(BaseModel):
    token: str
    init_data: str
    chip_value_sgd: str
    host_commission_percent: str
    buy_in_mode: str


def create_setup_token() -> str:
    return secrets.token_urlsafe(24)


def build_new_game_url(mini_app_url: str, token: str) -> str:
    parts = urlsplit(mini_app_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["token"] = token
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def url_origin(url: str) -> str:
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
                raise ValueError("URL must include scheme and host")
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))


def cleanup_expired_setups(pending_setups: dict[str, PendingNewGame], now: float | None = None) -> None:
    current_time = time.time() if now is None else now
    expired_tokens = [token for token, setup in pending_setups.items() if setup.expires_at <= current_time]
    for token in expired_tokens:
        pending_setups.pop(token, None)


def validate_telegram_init_data(init_data: str, bot_token: str, now: float | None = None) -> dict:
    fields = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise ValueError("Open this form from Telegram so your identity can be verified.")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise ValueError("Telegram verification failed. Reopen the Mini App and try again.")

    auth_date = fields.get("auth_date")
    if auth_date is None:
        raise ValueError("Telegram verification is missing an auth date.")
    try:
        auth_timestamp = int(auth_date)
    except ValueError as exc:
        raise ValueError("Telegram verification has an invalid auth date.") from exc

    current_time = int(time.time() if now is None else now)
    if auth_timestamp < current_time - INIT_DATA_MAX_AGE_SECONDS:
        raise ValueError("Telegram verification expired. Reopen the Mini App and try again.")

    try:
        user = json.loads(fields.get("user", "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("Telegram verification has invalid user data.") from exc
    if not isinstance(user, dict) or "id" not in user:
        raise ValueError("Telegram verification is missing the user.")
    return user


def create_mini_app(
    *,
    database: Database,
    bot: Bot,
    bot_token: str,
    pending_setups: dict[str, PendingNewGame],
  allowed_origins: list[str],
) -> FastAPI:
  app = FastAPI(title="Poker Bot Mini App API")
  app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
  )

  @app.get("/health")
  async def health() -> dict[str, bool]:
    return {"ok": True}

    @app.post("/api/new-game")
    async def create_new_game(request: NewGameRequest) -> dict[str, object]:
        cleanup_expired_setups(pending_setups)
        setup = pending_setups.get(request.token)
        if setup is None:
            raise HTTPException(status_code=410, detail="This setup link expired. Run /newgame again.")

        try:
            telegram_user = validate_telegram_init_data(request.init_data, bot_token)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        if int(telegram_user["id"]) != setup.host_user_id:
            raise HTTPException(status_code=403, detail="Only the host who ran /newgame can use this setup link.")

        try:
            chip_value = parse_non_negative_decimal(request.chip_value_sgd or "0.1", "Chip value")
            if chip_value <= 0:
                raise SettlementError("Chip value must be greater than zero")
            commission = parse_non_negative_decimal(request.host_commission_percent or "0", "Commission")
            if commission > 100:
                raise SettlementError("Commission must be 100 or less")
        except SettlementError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        buy_in_mode = request.buy_in_mode.upper()
        if buy_in_mode not in {games.BUY_IN_SGD, games.BUY_IN_CHIPS}:
            raise HTTPException(status_code=400, detail="Buy-in mode must be SGD or CHIPS.")

        with database.session_factory() as session:
            active_game = games.get_active_game(session, setup.chat_id)
            if active_game is not None:
                pending_setups.pop(request.token, None)
                raise HTTPException(status_code=409, detail=f"Game #{active_game.id} is already active.")

            game = games.create_game(
                session=session,
                chat_id=setup.chat_id,
                host_user_id=setup.host_user_id,
                host_display_name=setup.host_display_name,
                chip_value_sgd=decimal_to_storage(chip_value),
                host_commission_percent=decimal_to_storage(commission),
                buy_in_mode=buy_in_mode,
            )
            session.commit()

        pending_setups.pop(request.token, None)
        message = "\n".join(
            [
                f"Game #{game.id} started.",
                f"Host: {game.host_display_name}",
                f"Chip value: SGD {game.chip_value_sgd}",
                f"Host commission: {game.host_commission_percent}%",
                f"Buy-in mode: {game.buy_in_mode}",
                "",
                "Players can submit entries now.",
            ]
        )
        await bot.send_message(chat_id=setup.chat_id, text=message, reply_markup=game_actions_keyboard())
        return {"ok": True, "game_id": game.id, "message": message}

    return app
