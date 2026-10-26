import importlib.util
import pathlib
from datetime import date

_spec = importlib.util.spec_from_file_location(
    "daily",
    pathlib.Path(__file__).parent.parent / "custom_components/eco_water_tank/daily.py",
)
daily = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(daily)

D1, D2 = date(2026, 10, 26), date(2026, 10, 27)


def test_counts_from_first_reading():
    b = daily.DailyBaseline()
    assert b.today(1000, D1) == 0
    assert b.today(1150, D1) == 150


def test_rollover_at_midnight():
    b = daily.DailyBaseline()
    b.today(1000, D1)
    b.rollover(1400, D2)
    assert b.today(1450, D2) == 50


def test_missed_midnight_resets_on_new_day():
    b = daily.DailyBaseline(1000, D1)
    assert b.today(1500, D2) == 0


def test_meter_reset_counts_from_zero():
    b = daily.DailyBaseline(1000, D1)
    assert b.today(30, D1) == 30


def test_restored_baseline_kept_same_day():
    b = daily.DailyBaseline(1000, D1)
    assert b.today(1200, D1) == 200


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
