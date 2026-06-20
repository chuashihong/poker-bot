from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable

from chips_bot.models import Game, PlayerEntryModel
from chips_bot.settlement import SettlementResult, decimal_to_cents, format_cents, format_signed_cents


def format_decimal(value: str | Decimal) -> str:
    decimal_value = value if isinstance(value, Decimal) else Decimal(value)
    return format(decimal_value.normalize(), "f")


def format_status(game: Game, entries: Iterable[PlayerEntryModel]) -> str:
    lines = [
        f"Current game #{game.id}",
        f"Host: {game.host_display_name}",
        f"Chip value: {format_cents(decimal_to_cents(Decimal(game.chip_value_sgd)))}",
        f"Host commission: {format_decimal(game.host_commission_percent)}%",
        f"Buy-in mode: {game.buy_in_mode}",
        "",
        "Submitted players:",
    ]

    entry_list = list(entries)
    if not entry_list:
        lines.append("No submissions yet.")
        return "\n".join(lines)

    for index, entry in enumerate(entry_list, start=1):
        suffix = "SGD" if game.buy_in_mode == "SGD" else "chips"
        lines.append(
            f"{index}. {entry.display_name} - {format_decimal(entry.remaining_chips)} chips, "
            f"buy-in {format_decimal(entry.buy_in_original)} {suffix}"
        )
    return "\n".join(lines)


def format_result(game: Game, settlement: SettlementResult) -> str:
    lines = [
        f"Final Result - Game #{game.id}",
        "",
        f"Each chip = {format_cents(decimal_to_cents(Decimal(game.chip_value_sgd)))}",
        f"Host commission = {format_decimal(game.host_commission_percent)}%",
        f"Host = {game.host_display_name}",
        "",
        "Net before commission:",
    ]

    for result in settlement.player_results:
        commission_note = f", commission {format_cents(result.commission_paid_cents)}"
        if result.telegram_user_id == game.host_user_id and settlement.total_host_commission_cents:
            commission_note += f", commission received {format_cents(settlement.total_host_commission_cents)}"
        lines.append(
            f"- {result.name}: {format_signed_cents(result.net_before_commission_cents)}"
            f"{commission_note}, final {format_signed_cents(result.final_net_cents)}"
        )

    lines.extend(["", "Settlement:"])
    if settlement.transactions:
        for transaction in settlement.transactions:
            lines.append(
                f"- {transaction.from_player} pays {transaction.to_player} {format_cents(transaction.amount_cents)}"
            )
    else:
        lines.append("No payments needed.")

    lines.extend(["", f"Host commission total: {format_cents(settlement.total_host_commission_cents)}"])
    return "\n".join(lines)


def format_history(rows: Iterable[tuple[Game, int]]) -> str:
    row_list = list(rows)
    if not row_list:
        return "No completed games yet."

    lines = ["Recent games:"]
    for game, commission_cents in row_list:
        completed = _format_date(game.completed_at or game.created_at)
        lines.append(
            f"#{game.id} - {completed} - Host: {game.host_display_name} - "
            f"Commission: {format_cents(commission_cents)}"
        )
    return "\n".join(lines)


def format_stats(total_commission_cents: int, by_host: Iterable[tuple[str, int, int]]) -> str:
    lines = [
        "Total commission given to host across all completed games in this group: "
        f"{format_cents(total_commission_cents)}"
    ]

    host_rows = list(by_host)
    if host_rows:
        lines.extend(["", "By host:"])
        for host_name, game_count, commission_cents in host_rows:
            game_word = "game" if game_count == 1 else "games"
            lines.append(f"- {host_name}: {format_cents(commission_cents)} across {game_count} {game_word}")
    return "\n".join(lines)


def _format_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError:
        return value[:10]
