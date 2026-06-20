from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from chips_bot.handlers.common import database, reply_text
from chips_bot.repositories import games


async def cancel_game_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return

    db = database(context)
    with db.session_factory() as session:
        game = games.get_active_game(session, chat.id)
        if game is None:
            await reply_text(update, "No active game to cancel.")
            return
        if user.id != game.host_user_id:
            await reply_text(update, "Only the host can cancel this game.")
            return

        games.cancel_active_game(session, game)
        session.commit()
        await reply_text(update, f"Game #{game.id} cancelled.")
