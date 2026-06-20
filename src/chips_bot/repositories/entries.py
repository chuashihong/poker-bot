from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from chips_bot.models import PlayerEntryModel
from chips_bot.repositories.games import utc_now


def upsert_entry(
    session: Session,
    game_id: int,
    telegram_user_id: int,
    display_name: str,
    remaining_chips: str,
    buy_in_original: str,
    buy_in_sgd: str,
) -> PlayerEntryModel:
    existing = session.scalar(
        select(PlayerEntryModel).where(
            PlayerEntryModel.game_id == game_id,
            PlayerEntryModel.telegram_user_id == telegram_user_id,
        )
    )
    now = utc_now()
    if existing is None:
        entry = PlayerEntryModel(
            game_id=game_id,
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            remaining_chips=remaining_chips,
            buy_in_original=buy_in_original,
            buy_in_sgd=buy_in_sgd,
            created_at=now,
            updated_at=now,
        )
        session.add(entry)
        session.flush()
        return entry

    existing.display_name = display_name
    existing.remaining_chips = remaining_chips
    existing.buy_in_original = buy_in_original
    existing.buy_in_sgd = buy_in_sgd
    existing.updated_at = now
    session.add(existing)
    session.flush()
    return existing


def list_entries(session: Session, game_id: int) -> list[PlayerEntryModel]:
    return list(
        session.scalars(
            select(PlayerEntryModel)
            .where(PlayerEntryModel.game_id == game_id)
            .order_by(PlayerEntryModel.updated_at.asc(), PlayerEntryModel.id.asc())
        )
    )
