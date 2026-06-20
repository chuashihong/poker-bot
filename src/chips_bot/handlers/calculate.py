from __future__ import annotations

from decimal import Decimal

from telegram import Update
from telegram.ext import ContextTypes

from chips_bot.formatters import format_result
from chips_bot.handlers.common import database, reply_text
from chips_bot.repositories import entries, games, results
from chips_bot.settlement import PlayerEntry, SettlementError, calculate_settlement


async def calculate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer()

    chat = update.effective_chat
    user = update.effective_user
    if chat is None or user is None:
        return

    db = database(context)
    with db.session_factory() as session:
        game = games.get_active_game(session, chat.id)
        if game is None:
            await reply_text(update, "No active game to calculate.")
            return
        if user.id != game.host_user_id:
            await reply_text(update, "Only the host can calculate this game.")
            return

        game_entries = entries.list_entries(session, game.id)
        if len(game_entries) < 2:
            await reply_text(update, "At least 2 player submissions are required before calculating.")
            return

        settlement_entries = [
            PlayerEntry(
                telegram_user_id=entry.telegram_user_id,
                name=entry.display_name,
                remaining_chips=Decimal(entry.remaining_chips),
                buy_in_sgd=Decimal(entry.buy_in_sgd),
            )
            for entry in game_entries
        ]

        try:
            settlement = calculate_settlement(
                entries=settlement_entries,
                chip_value_sgd=Decimal(game.chip_value_sgd),
                host_telegram_user_id=game.host_user_id,
                host_commission_percent=Decimal(game.host_commission_percent),
                host_name=game.host_display_name,
            )
        except SettlementError as exc:
            await reply_text(update, f"Cannot calculate yet: {exc}")
            return

        results.save_settlement(
            session=session,
            game_id=game.id,
            host_user_id=game.host_user_id,
            host_display_name=game.host_display_name,
            settlement=settlement,
        )
        games.mark_completed(session, game)
        session.commit()

        await reply_text(update, format_result(game, settlement))
