from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


class SettlementError(ValueError):
    """Raised when a game cannot be settled consistently."""


@dataclass(frozen=True)
class PlayerEntry:
    telegram_user_id: int
    name: str
    remaining_chips: Decimal
    buy_in_sgd: Decimal


@dataclass(frozen=True)
class PlayerResult:
    telegram_user_id: int
    name: str
    net_before_commission_cents: int
    commission_paid_cents: int
    final_net_cents: int


@dataclass(frozen=True)
class Transaction:
    from_player: str
    to_player: str
    amount_cents: int


@dataclass(frozen=True)
class SettlementResult:
    player_results: list[PlayerResult]
    transactions: list[Transaction]
    total_host_commission_cents: int


@dataclass
class Balance:
    name: str
    amount_cents: int


def parse_decimal(value: str | int | float | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, AttributeError) as exc:
        raise SettlementError(f"Invalid decimal value: {value!r}") from exc


def decimal_to_cents(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}SGD {cents // 100}.{cents % 100:02d}"


def format_signed_cents(cents: int) -> str:
    sign = "+" if cents >= 0 else "-"
    cents = abs(cents)
    return f"{sign}SGD {cents // 100}.{cents % 100:02d}"


def commission_cents(net_before_commission_cents: int, host_commission_percent: Decimal) -> int:
    if net_before_commission_cents <= 0:
        return 0
    amount = (Decimal(net_before_commission_cents) / Decimal("100")) * (host_commission_percent / Decimal("100"))
    return decimal_to_cents(amount)


def calculate_settlement(
    entries: list[PlayerEntry],
    chip_value_sgd: Decimal,
    host_telegram_user_id: int,
    host_commission_percent: Decimal,
    host_name: str | None = None,
) -> SettlementResult:
    chip_value_sgd = parse_decimal(chip_value_sgd)
    host_commission_percent = parse_decimal(host_commission_percent)

    if not entries:
        raise SettlementError("At least one player entry is required")
    if chip_value_sgd <= 0:
        raise SettlementError("Chip value must be greater than zero")
    if host_commission_percent < 0 or host_commission_percent > 100:
        raise SettlementError("Host commission percent must be between 0 and 100")

    initial_results: list[PlayerResult] = []
    total_commission = 0
    host_index: int | None = None

    for index, entry in enumerate(entries):
        if not entry.name.strip():
            raise SettlementError("Player name is required")
        if entry.remaining_chips < 0 or entry.buy_in_sgd < 0:
            raise SettlementError("Remaining chips and buy-in must be non-negative")

        ending_value_sgd = entry.remaining_chips * chip_value_sgd
        net_before_commission_cents = decimal_to_cents(ending_value_sgd - entry.buy_in_sgd)
        paid_commission = commission_cents(net_before_commission_cents, host_commission_percent)
        total_commission += paid_commission
        final_net_cents = net_before_commission_cents - paid_commission

        if entry.telegram_user_id == host_telegram_user_id:
            host_index = index

        initial_results.append(
            PlayerResult(
                telegram_user_id=entry.telegram_user_id,
                name=entry.name.strip(),
                net_before_commission_cents=net_before_commission_cents,
                commission_paid_cents=paid_commission,
                final_net_cents=final_net_cents,
            )
        )

    results = list(initial_results)
    if host_index is None:
        if total_commission > 0:
            results.append(
                PlayerResult(
                    telegram_user_id=host_telegram_user_id,
                    name=(host_name or "Host").strip() or "Host",
                    net_before_commission_cents=0,
                    commission_paid_cents=0,
                    final_net_cents=total_commission,
                )
            )
    else:
        host_result = results[host_index]
        results[host_index] = PlayerResult(
            telegram_user_id=host_result.telegram_user_id,
            name=host_result.name,
            net_before_commission_cents=host_result.net_before_commission_cents,
            commission_paid_cents=host_result.commission_paid_cents,
            final_net_cents=host_result.final_net_cents + total_commission,
        )

    total_final_net = sum(result.final_net_cents for result in results)
    if total_final_net != 0:
        raise SettlementError(
            "Final nets do not balance. Check that total remaining chip value equals total buy-ins. "
            f"Difference: {format_cents(total_final_net)}"
        )

    return SettlementResult(
        player_results=results,
        transactions=settle_result_transactions(results),
        total_host_commission_cents=total_commission,
    )


def settle_transactions(final_nets: dict[str, int]) -> list[Transaction]:
    balances = [Balance(name=name, amount_cents=amount) for name, amount in final_nets.items()]
    return settle_balances(balances)


def settle_result_transactions(results: list[PlayerResult]) -> list[Transaction]:
    balances = [Balance(name=result.name, amount_cents=result.final_net_cents) for result in results]
    return settle_balances(balances)


def settle_balances(balances: list[Balance]) -> list[Transaction]:
    creditors = [Balance(balance.name, balance.amount_cents) for balance in balances if balance.amount_cents > 0]
    debtors = [Balance(balance.name, -balance.amount_cents) for balance in balances if balance.amount_cents < 0]

    creditors.sort(key=lambda balance: balance.amount_cents, reverse=True)
    debtors.sort(key=lambda balance: balance.amount_cents, reverse=True)

    transactions: list[Transaction] = []
    debtor_index = 0
    creditor_index = 0

    while debtor_index < len(debtors) and creditor_index < len(creditors):
        debtor = debtors[debtor_index]
        creditor = creditors[creditor_index]
        amount_cents = min(debtor.amount_cents, creditor.amount_cents)

        if amount_cents > 0:
            transactions.append(
                Transaction(
                    from_player=debtor.name,
                    to_player=creditor.name,
                    amount_cents=amount_cents,
                )
            )

        debtor.amount_cents -= amount_cents
        creditor.amount_cents -= amount_cents

        if debtor.amount_cents == 0:
            debtor_index += 1
        if creditor.amount_cents == 0:
            creditor_index += 1

    return transactions
