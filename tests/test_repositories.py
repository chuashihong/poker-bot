from chips_bot.db import create_database, init_db
from chips_bot.repositories import entries, games, results
from chips_bot.settlement import PlayerResult, SettlementResult, Transaction


def test_game_entry_result_repository_round_trip():
    database = create_database("sqlite:///:memory:")
    init_db(database)

    with database.session_factory() as session:
        game = games.create_game(
            session=session,
            chat_id=123,
            host_user_id=1,
            host_display_name="Host",
            chip_value_sgd="0.1",
            host_commission_percent="2",
            buy_in_mode=games.BUY_IN_SGD,
        )
        entries.upsert_entry(session, game.id, 2, "A", "300", "20", "20")
        entries.upsert_entry(session, game.id, 2, "A2", "250", "20", "20")
        session.commit()

        assert games.get_active_game(session, 123).id == game.id
        game_entries = entries.list_entries(session, game.id)
        assert len(game_entries) == 1
        assert game_entries[0].display_name == "A2"

        settlement = SettlementResult(
            player_results=[
                PlayerResult(telegram_user_id=1, name="Host", net_before_commission_cents=0, commission_paid_cents=0, final_net_cents=100),
                PlayerResult(telegram_user_id=2, name="A2", net_before_commission_cents=-100, commission_paid_cents=0, final_net_cents=-100),
            ],
            transactions=[Transaction(from_player="A2", to_player="Host", amount_cents=100)],
            total_host_commission_cents=100,
        )
        results.save_settlement(session, game.id, 1, "Host", settlement)
        games.mark_completed(session, game)
        session.commit()

        assert results.get_total_commission_for_chat(session, 123) == 100
        assert results.get_commission_by_host_for_chat(session, 123) == [("Host", 1, 100)]
