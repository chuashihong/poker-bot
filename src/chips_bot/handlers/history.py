from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from chips_bot.formatters import format_history
from chips_bot.handlers.common import database, reply_text
from chips_bot.repositories import games, results


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is None:
        return

    db = database(context)
    with db.session_factory() as session:
        recent_games = games.list_recent_completed_games(session, chat.id)
        rows = [(game, results.get_game_commission(session, game.id)) for game in recent_games]
        await reply_text(update, format_history(rows))
