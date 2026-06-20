from __future__ import annotations

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from chips_bot.handlers.common import (
    database,
    decimal_to_storage,
    game_actions_keyboard,
    parse_non_negative_decimal,
    reply_text,
    user_display_name,
)
from chips_bot.repositories import games
from chips_bot.settlement import SettlementError

ASK_CHIP_VALUE = 1
ASK_COMMISSION = 2
ASK_BUY_IN_MODE = 3


async def start_new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return ConversationHandler.END

    db = database(context)
    with db.session_factory() as session:
        active_game = games.get_active_game(session, chat.id)
        if active_game is not None:
            await reply_text(update, f"Game #{active_game.id} is already active. Use /status or /cancelgame first.")
            return ConversationHandler.END

    context.user_data["new_game"] = {
        "chat_id": chat.id,
        "host_user_id": user.id,
        "host_display_name": user_display_name(user),
    }
    await reply_text(update, "Enter chip value in SGD, or send 0.1 for the default:")
    return ASK_CHIP_VALUE


async def ask_commission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip() if update.effective_message else ""
    try:
        chip_value = parse_non_negative_decimal(text or "0.1", "Chip value")
        if chip_value <= 0:
            raise SettlementError("Chip value must be greater than zero")
    except SettlementError as exc:
        await reply_text(update, f"{exc}. Try again, for example: 0.1")
        return ASK_CHIP_VALUE

    context.user_data.setdefault("new_game", {})["chip_value_sgd"] = decimal_to_storage(chip_value)
    await reply_text(update, "Enter host commission percentage, or send 0 for none:")
    return ASK_COMMISSION


async def ask_buy_in_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip() if update.effective_message else ""
    try:
        commission = parse_non_negative_decimal(text or "0", "Commission")
        if commission > 100:
            raise SettlementError("Commission must be 100 or less")
    except SettlementError as exc:
        await reply_text(update, f"{exc}. Try again, for example: 2")
        return ASK_COMMISSION

    context.user_data.setdefault("new_game", {})["host_commission_percent"] = decimal_to_storage(commission)
    await reply_text(update, "Will buy-ins be entered as SGD or CHIPS?")
    return ASK_BUY_IN_MODE


async def finish_new_game(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip().upper() if update.effective_message else ""
    if text in {"SGD", "S", "1"}:
        buy_in_mode = games.BUY_IN_SGD
    elif text in {"CHIPS", "CHIP", "C", "2"}:
        buy_in_mode = games.BUY_IN_CHIPS
    else:
        await reply_text(update, "Please enter SGD or CHIPS.")
        return ASK_BUY_IN_MODE

    data = context.user_data.get("new_game", {})
    db = database(context)
    with db.session_factory() as session:
        active_game = games.get_active_game(session, data["chat_id"])
        if active_game is not None:
            await reply_text(update, f"Game #{active_game.id} is already active.")
            return ConversationHandler.END

        game = games.create_game(
            session=session,
            chat_id=data["chat_id"],
            host_user_id=data["host_user_id"],
            host_display_name=data["host_display_name"],
            chip_value_sgd=data["chip_value_sgd"],
            host_commission_percent=data["host_commission_percent"],
            buy_in_mode=buy_in_mode,
        )
        session.commit()

    context.user_data.pop("new_game", None)
    await reply_text(
        update,
        "\n".join(
            [
                f"Game #{game.id} started.",
                f"Host: {game.host_display_name}",
                f"Chip value: SGD {game.chip_value_sgd}",
                f"Host commission: {game.host_commission_percent}%",
                f"Buy-in mode: {game.buy_in_mode}",
                "",
                "Players can submit entries now.",
            ]
        ),
        reply_markup=game_actions_keyboard(),
    )
    return ConversationHandler.END


async def cancel_new_game_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_game", None)
    await reply_text(update, "New game setup cancelled.")
    return ConversationHandler.END


def new_game_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("newgame", start_new_game)],
        states={
            ASK_CHIP_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_commission)],
            ASK_COMMISSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_buy_in_mode)],
            ASK_BUY_IN_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_new_game)],
        },
        fallbacks=[CommandHandler("cancel", cancel_new_game_conversation)],
    )
