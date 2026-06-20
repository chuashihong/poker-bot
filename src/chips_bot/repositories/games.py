from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from chips_bot.models import Game

ACTIVE = "ACTIVE"
COMPLETED = "COMPLETED"
CANCELLED = "CANCELLED"
BUY_IN_SGD = "SGD"
BUY_IN_CHIPS = "CHIPS"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def create_game(
    session: Session,
    chat_id: int,
    host_user_id: int,
    host_display_name: str,
    chip_value_sgd: str,
    host_commission_percent: str,
    buy_in_mode: str,
) -> Game:
    game = Game(
        chat_id=chat_id,
        host_user_id=host_user_id,
        host_display_name=host_display_name,
        chip_value_sgd=chip_value_sgd,
        host_commission_percent=host_commission_percent,
        buy_in_mode=buy_in_mode,
        status=ACTIVE,
        created_at=utc_now(),
        completed_at=None,
    )
    session.add(game)
    session.flush()
    return game


def get_active_game(session: Session, chat_id: int) -> Game | None:
    return session.scalar(select(Game).where(Game.chat_id == chat_id, Game.status == ACTIVE).order_by(Game.id.desc()))


def get_game(session: Session, game_id: int) -> Game | None:
    return session.get(Game, game_id)


def mark_completed(session: Session, game: Game) -> None:
    game.status = COMPLETED
    game.completed_at = utc_now()
    session.add(game)


def cancel_active_game(session: Session, game: Game) -> None:
    game.status = CANCELLED
    game.completed_at = utc_now()
    session.add(game)


def list_recent_completed_games(session: Session, chat_id: int, limit: int = 10) -> list[Game]:
    return list(
        session.scalars(
            select(Game)
            .where(Game.chat_id == chat_id, Game.status == COMPLETED)
            .order_by(Game.completed_at.desc(), Game.id.desc())
            .limit(limit)
        )
    )
