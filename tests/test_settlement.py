from decimal import Decimal

import pytest

from chips_bot.settlement import PlayerEntry, SettlementError, calculate_settlement, settle_transactions


def entry(user_id: int, name: str, chips: str, buy_in: str) -> PlayerEntry:
    return PlayerEntry(
        telegram_user_id=user_id,
        name=name,
        remaining_chips=Decimal(chips),
        buy_in_sgd=Decimal(buy_in),
    )


def result_by_name(settlement):
    return {result.name: result for result in settlement.player_results}


def test_basic_no_commission_case():
    settlement = calculate_settlement(
        entries=[entry(1, "A", "300", "20"), entry(2, "B", "100", "20")],
        chip_value_sgd=Decimal("0.1"),
        host_telegram_user_id=1,
        host_commission_percent=Decimal("0"),
    )

    assert settlement.total_host_commission_cents == 0
    assert result_by_name(settlement)["A"].final_net_cents == 1000
    assert result_by_name(settlement)["B"].final_net_cents == -1000
    assert len(settlement.transactions) == 1
    assert settlement.transactions[0].from_player == "B"
    assert settlement.transactions[0].to_player == "A"
    assert settlement.transactions[0].amount_cents == 1000


def test_commission_case_with_host_losing():
    settlement = calculate_settlement(
        entries=[
            entry(1, "es", "562", "20"),
            entry(2, "Gzs", "0", "20"),
            entry(3, "Chua", "575", "60"),
            entry(4, "Balancer", "0", "13.70"),
        ],
        chip_value_sgd=Decimal("0.1"),
        host_telegram_user_id=3,
        host_commission_percent=Decimal("2"),
    )

    results = result_by_name(settlement)
    assert results["es"].commission_paid_cents == 72
    assert settlement.total_host_commission_cents == 72
    assert results["es"].final_net_cents == 3548
    assert results["Chua"].final_net_cents == -178
    assert sum(result.final_net_cents for result in settlement.player_results) == 0


def test_host_also_winning_pays_and_receives_commission():
    settlement = calculate_settlement(
        entries=[
            entry(1, "Chua", "500", "0"),
            entry(2, "A", "200", "0"),
            entry(3, "B", "0", "70"),
        ],
        chip_value_sgd=Decimal("0.1"),
        host_telegram_user_id=1,
        host_commission_percent=Decimal("2"),
    )

    results = result_by_name(settlement)
    assert results["Chua"].net_before_commission_cents == 5000
    assert results["Chua"].commission_paid_cents == 100
    assert results["A"].commission_paid_cents == 40
    assert settlement.total_host_commission_cents == 140
    assert results["Chua"].final_net_cents == 5040
    assert results["A"].final_net_cents == 1960
    assert results["B"].final_net_cents == -7000
    assert sum(result.final_net_cents for result in settlement.player_results) == 0


def test_real_style_multi_player_case():
    settlement = calculate_settlement(
        entries=[
            entry(1, "es", "562", "20"),
            entry(2, "Gzg", "335", "20"),
            entry(3, "Gzs", "0", "20"),
            entry(4, "samson", "0", "40"),
            entry(5, "ziyi", "353", "20"),
            entry(6, "jervin", "635", "60"),
            entry(7, "chester", "610", "60"),
            entry(8, "ruvy", "136", "20"),
            entry(9, "gianice", "194", "20"),
            entry(10, "Chua", "575", "60"),
        ],
        chip_value_sgd=Decimal("0.1"),
        host_telegram_user_id=10,
        host_commission_percent=Decimal("2"),
    )

    results = result_by_name(settlement)
    assert results["es"].net_before_commission_cents == 3620
    assert results["Gzg"].net_before_commission_cents == 1350
    assert results["Gzs"].net_before_commission_cents == -2000
    assert results["samson"].net_before_commission_cents == -4000
    assert results["ziyi"].net_before_commission_cents == 1530
    assert results["jervin"].net_before_commission_cents == 350
    assert results["chester"].net_before_commission_cents == 100
    assert results["ruvy"].net_before_commission_cents == -640
    assert results["gianice"].net_before_commission_cents == -60
    assert results["Chua"].net_before_commission_cents == -250

    assert settlement.total_host_commission_cents == 139
    assert results["Chua"].final_net_cents == -111
    assert sum(result.final_net_cents for result in settlement.player_results) == 0
    assert sum(transaction.amount_cents for transaction in settlement.transactions) == sum(
        -result.final_net_cents for result in settlement.player_results if result.final_net_cents < 0
    )


def test_settle_transactions_minimizes_with_two_pointers():
    transactions = settle_transactions({"es": 3548, "Gzg": 1323, "Gzs": -2000, "samson": -2871})

    assert [(tx.from_player, tx.to_player, tx.amount_cents) for tx in transactions] == [
        ("samson", "es", 2871),
        ("Gzs", "es", 677),
        ("Gzs", "Gzg", 1323),
    ]


def test_unbalanced_game_raises_clear_error():
    with pytest.raises(SettlementError, match="Final nets do not balance"):
        calculate_settlement(
            entries=[entry(1, "A", "100", "0"), entry(2, "B", "100", "0")],
            chip_value_sgd=Decimal("0.1"),
            host_telegram_user_id=1,
            host_commission_percent=Decimal("0"),
        )
