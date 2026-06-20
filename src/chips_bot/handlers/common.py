from __future__ import annotations

from decimal import Decimal

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.ext import ContextTypes

from chips_bot.db import Database
from chips_bot.settlement import SettlementError, parse_decimal


def database(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.application.bot_data["database"]


def user_display_name(user: User) -> str:
    if user.full_name:
        return user.full_name
    if user.username:
        return user.username
    return str(user.id)


async def reply_text(update: Update, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    if update.effective_message is not None:
        await update.effective_message.reply_text(text, reply_markup=reply_markup)


def game_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Submit My Entry", callback_data="submit_entry")],
            [InlineKeyboardButton("View Status", callback_data="view_status")],
            [InlineKeyboardButton("Calculate Result", callback_data="calculate_game")],
        ]
    )


def parse_non_negative_decimal(text: str, label: str) -> Decimal:
    value = parse_decimal(text)
    if value < 0:
        raise SettlementError(f"{label} must be non-negative")
    return value


def decimal_to_storage(value: Decimal) -> str:
    return format(value.normalize(), "f")
