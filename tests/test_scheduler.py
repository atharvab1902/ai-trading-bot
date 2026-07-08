"""Tests for scheduler.py timing helpers."""
import pytest


def test_hm_add_forward():
    from scheduler import _hm_add
    assert _hm_add(9, 30, 75) == 1045   # 09:30 + 75min = 10:45


def test_hm_add_backward():
    from scheduler import _hm_add
    assert _hm_add(9, 30, -45) == 845   # 09:30 - 45min = 08:45


def test_hm_add_hour_boundary():
    from scheduler import _hm_add
    assert _hm_add(9, 15, -75) == 800   # 09:15 - 75min = 08:00


def test_hm_add_close_plus_45():
    from scheduler import _hm_add
    assert _hm_add(16, 0, 45) == 1645   # 16:00 + 45min = 16:45


def test_hm_add_zero_offset():
    from scheduler import _hm_add
    assert _hm_add(9, 30, 0) == 930


def test_hm_add_large_offset():
    from scheduler import _hm_add
    # 15:15 + 45 = 16:00
    assert _hm_add(15, 15, 45) == 1600


def test_holiday_check_returns_false_no_file(tmp_path):
    from scheduler import is_market_holiday
    import datetime
    today = datetime.date(2026, 7, 4)
    is_hol, name = is_market_holiday(today, "nonexistent_holidays.json")
    assert is_hol is False
    assert name == ""


def test_holiday_check_detects_holiday(tmp_path):
    import json, datetime
    from unittest.mock import patch
    import scheduler as sched_mod

    holidays = {"2026": [{"date": "2026-07-04", "name": "Independence Day"}]}
    (tmp_path / "data").mkdir(exist_ok=True)
    hf = tmp_path / "data" / "nyse_holidays.json"
    hf.write_text(json.dumps(holidays))

    with patch.object(sched_mod, "REPO_ROOT", tmp_path):
        today = datetime.date(2026, 7, 4)
        is_hol, name = sched_mod.is_market_holiday(today, "nyse_holidays.json")
    assert is_hol is True
    assert "Independence" in name


def test_holiday_check_non_holiday(tmp_path):
    import json, datetime
    from unittest.mock import patch
    import scheduler as sched_mod

    holidays = {"2026": [{"date": "2026-07-04", "name": "Independence Day"}]}
    (tmp_path / "data").mkdir(exist_ok=True)
    hf = tmp_path / "data" / "nyse_holidays.json"
    hf.write_text(json.dumps(holidays))

    with patch.object(sched_mod, "REPO_ROOT", tmp_path):
        today = datetime.date(2026, 7, 8)
        is_hol, name = sched_mod.is_market_holiday(today, "nyse_holidays.json")
    assert is_hol is False
