from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from chips_bot.formatters import format_stats
from chips_bot.handlers.common import database, reply_text
from chips_bot.repositories import results


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is None:
        return

    db = database(context)
    with db.session_factory() as session:
        total = results.get_total_commission_for_chat(session, chat.id)
        by_host = results.get_commission_by_host_for_chat(session, chat.id)
        await reply_text(update, format_stats(total, by_host))
