import pytest
from src.parser import parse_time_to_seconds, seconds_to_time_str, parse_pace_to_seconds, seconds_to_pace_str, clean_numeric


def test_time_conversions():
    assert parse_time_to_seconds("00:25:30") == 1530
    assert parse_time_to_seconds("25:30") == 1530
    assert parse_time_to_seconds("1:00:00") == 3600
    assert parse_time_to_seconds("") == 0

    assert seconds_to_time_str(1530) == "25:30"
    assert seconds_to_time_str(3665) == "01:01:05"


def test_pace_conversions():
    assert parse_pace_to_seconds("5:00") == 300.0
    assert parse_pace_to_seconds("4:30") == 270.0
    assert parse_pace_to_seconds("") == 0.0

    assert seconds_to_pace_str(300.0) == "5:00"
    assert seconds_to_pace_str(270.0) == "4:30"
    assert seconds_to_pace_str(0.0) == "--:--"


def test_clean_numeric():
    assert clean_numeric("1,234") == 1234.0
    assert clean_numeric("--") == 0.0
    assert clean_numeric(None) == 0.0
    assert clean_numeric("12.5") == 12.5
