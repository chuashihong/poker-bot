from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from chips_bot.formatters import format_status
from chips_bot.handlers.common import database, reply_text
from chips_bot.repositories import entries, games


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer()

    chat = update.effective_chat
    if chat is None:
        return

    db = database(context)
    with db.session_factory() as session:
        game = games.get_active_game(session, chat.id)
        if game is None:
            await reply_text(update, "No active game. The host can start one with /newgame.")
            return
        game_entries = entries.list_entries(session, game.id)
        await reply_text(update, format_status(game, game_entries))
