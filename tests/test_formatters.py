from chips_bot.settlement import format_cents, format_signed_cents


def test_format_cents():
    assert format_cents(0) == "SGD 0.00"
    assert format_cents(139) == "SGD 1.39"
    assert format_cents(-250) == "-SGD 2.50"


def test_format_signed_cents():
    assert format_signed_cents(3620) == "+SGD 36.20"
    assert format_signed_cents(0) == "+SGD 0.00"
    assert format_signed_cents(-111) == "-SGD 1.11"
