from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from chips_bot.models import Game, GameResult, HostCommissionStat, SettlementTransaction
from chips_bot.repositories.games import utc_now
from chips_bot.settlement import SettlementResult


def save_settlement(
    session: Session,
    game_id: int,
    host_user_id: int,
    host_display_name: str,
    settlement: SettlementResult,
) -> None:
    for player_result in settlement.player_results:
        session.add(
            GameResult(
                game_id=game_id,
                telegram_user_id=player_result.telegram_user_id,
                display_name=player_result.name,
                net_before_commission_cents=player_result.net_before_commission_cents,
                commission_paid_cents=player_result.commission_paid_cents,
                final_net_cents=player_result.final_net_cents,
            )
        )

    for transaction in settlement.transactions:
        session.add(
            SettlementTransaction(
                game_id=game_id,
                from_display_name=transaction.from_player,
                to_display_name=transaction.to_player,
                amount_cents=transaction.amount_cents,
            )
        )

    session.add(
        HostCommissionStat(
            game_id=game_id,
            host_user_id=host_user_id,
            host_display_name=host_display_name,
            total_commission_cents=settlement.total_host_commission_cents,
            created_at=utc_now(),
        )
    )


def get_game_commission(session: Session, game_id: int) -> int:
    value = session.scalar(select(HostCommissionStat.total_commission_cents).where(HostCommissionStat.game_id == game_id))
    return int(value or 0)


def get_total_commission_for_chat(session: Session, chat_id: int) -> int:
    value = session.scalar(
        select(func.coalesce(func.sum(HostCommissionStat.total_commission_cents), 0))
        .join(Game, Game.id == HostCommissionStat.game_id)
        .where(Game.chat_id == chat_id, Game.status == "COMPLETED")
    )
    return int(value or 0)


def get_commission_by_host_for_chat(session: Session, chat_id: int) -> list[tuple[str, int, int]]:
    rows = session.execute(
        select(
            HostCommissionStat.host_display_name,
            func.count(HostCommissionStat.id),
            func.coalesce(func.sum(HostCommissionStat.total_commission_cents), 0),
        )
        .join(Game, Game.id == HostCommissionStat.game_id)
        .where(Game.chat_id == chat_id, Game.status == "COMPLETED")
        .group_by(HostCommissionStat.host_user_id, HostCommissionStat.host_display_name)
        .order_by(func.sum(HostCommissionStat.total_commission_cents).desc())
    ).all()
    return [(str(name), int(count), int(total)) for name, count, total in rows]
