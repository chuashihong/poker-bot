from __future__ import annotations

from decimal import Decimal

from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

from chips_bot.handlers.common import database, decimal_to_storage, parse_non_negative_decimal, reply_text, user_display_name
from chips_bot.repositories import entries, games
from chips_bot.settlement import SettlementError, decimal_to_cents, format_cents

ASK_NAME = 10
ASK_REMAINING_CHIPS = 11
ASK_BUY_IN = 12
CONFIRM_SUBMIT = 13


async def start_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query is not None:
        await update.callback_query.answer()

    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return ConversationHandler.END

    db = database(context)
    with db.session_factory() as session:
        game = games.get_active_game(session, chat.id)
        if game is None:
            await reply_text(update, "No active game. Ask the host to run /newgame first.")
            return ConversationHandler.END

        context.user_data["submit"] = {
            "chat_id": chat.id,
            "game_id": game.id,
            "buy_in_mode": game.buy_in_mode,
            "chip_value_sgd": game.chip_value_sgd,
            "telegram_user_id": user.id,
            "default_name": user_display_name(user),
        }

    await reply_text(update, f"Enter your display name, or send {context.user_data['submit']['default_name']}:")
    return ASK_NAME


async def ask_remaining_chips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.effective_message.text or "").strip() if update.effective_message else ""
    if not name:
        name = context.user_data.get("submit", {}).get("default_name", "Player")
    context.user_data.setdefault("submit", {})["display_name"] = name
    await reply_text(update, "Enter your remaining chips:")
    return ASK_REMAINING_CHIPS


async def ask_buy_in(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip() if update.effective_message else ""
    try:
        remaining_chips = parse_non_negative_decimal(text, "Remaining chips")
    except SettlementError as exc:
        await reply_text(update, f"{exc}. Try again, for example: 353")
        return ASK_REMAINING_CHIPS

    context.user_data.setdefault("submit", {})["remaining_chips"] = decimal_to_storage(remaining_chips)
    mode = context.user_data["submit"]["buy_in_mode"]
    label = "SGD" if mode == games.BUY_IN_SGD else "chips"
    await reply_text(update, f"Enter your total buy-in in {label}:")
    return ASK_BUY_IN


async def confirm_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip() if update.effective_message else ""
    submit_data = context.user_data.setdefault("submit", {})
    try:
        buy_in_original = parse_non_negative_decimal(text, "Buy-in")
    except SettlementError as exc:
        await reply_text(update, f"{exc}. Try again, for example: 200")
        return ASK_BUY_IN

    chip_value = Decimal(submit_data["chip_value_sgd"])
    if submit_data["buy_in_mode"] == games.BUY_IN_CHIPS:
        buy_in_sgd = buy_in_original * chip_value
    else:
        buy_in_sgd = buy_in_original

    submit_data["buy_in_original"] = decimal_to_storage(buy_in_original)
    submit_data["buy_in_sgd"] = decimal_to_storage(buy_in_sgd)

    suffix = "SGD" if submit_data["buy_in_mode"] == games.BUY_IN_SGD else "chips"
    summary = "\n".join(
        [
            "Confirm your entry:",
            f"Name: {submit_data['display_name']}",
            f"Remaining chips: {submit_data['remaining_chips']}",
            f"Buy-in: {submit_data['buy_in_original']} {suffix}",
            f"Normalized buy-in: {format_cents(decimal_to_cents(buy_in_sgd))}",
            "",
            "Send yes to save, or no to cancel.",
        ]
    )
    await reply_text(update, summary)
    return CONFIRM_SUBMIT


async def finish_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.effective_message.text or "").strip().lower() if update.effective_message else ""
    if text not in {"yes", "y", "no", "n"}:
        await reply_text(update, "Please send yes to save or no to cancel.")
        return CONFIRM_SUBMIT
    if text in {"no", "n"}:
        context.user_data.pop("submit", None)
        await reply_text(update, "Submission cancelled.")
        return ConversationHandler.END

    data = context.user_data.get("submit", {})
    db = database(context)
    with db.session_factory() as session:
        game = games.get_active_game(session, data["chat_id"])
        if game is None or game.id != data["game_id"]:
            await reply_text(update, "That game is no longer active. Please run /status to check the current game.")
            return ConversationHandler.END

        entries.upsert_entry(
            session=session,
            game_id=data["game_id"],
            telegram_user_id=data["telegram_user_id"],
            display_name=data["display_name"],
            remaining_chips=data["remaining_chips"],
            buy_in_original=data["buy_in_original"],
            buy_in_sgd=data["buy_in_sgd"],
        )
        session.commit()

    context.user_data.pop("submit", None)
    await reply_text(update, "Entry saved. You can run /submit again to update it before calculation.")
    return ConversationHandler.END


async def cancel_submit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("submit", None)
    await reply_text(update, "Submission cancelled.")
    return ConversationHandler.END


def submit_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("submit", start_submit),
            CommandHandler("join", start_submit),
            CallbackQueryHandler(start_submit, pattern="^submit_entry$"),
        ],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_remaining_chips)],
            ASK_REMAINING_CHIPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_buy_in)],
            ASK_BUY_IN: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_submit)],
            CONFIRM_SUBMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finish_submit)],
        },
        fallbacks=[CommandHandler("cancel", cancel_submit_conversation)],
    )
