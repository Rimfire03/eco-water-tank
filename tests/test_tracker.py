import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "tracker",
    pathlib.Path(__file__).parent.parent / "custom_components/eco_water_tank/tracker.py",
)
tracker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tracker)


def test_fill_counts():
    t = tracker.InflowTracker(threshold=10)
    t.update(100)
    assert t.update(300) == 200


def test_noise_ignored():
    t = tracker.InflowTracker(threshold=10)
    t.update(100)
    for v in (103, 99, 104, 101, 105):
        t.update(v)
    assert t.total == 0


def test_drain_with_outlet_is_not_inflow():
    t = tracker.InflowTracker(threshold=10)
    t.update(500, outflow=0)
    assert t.update(400, outflow=100) == 0


def test_fill_while_drawing():
    t = tracker.InflowTracker(threshold=10)
    t.update(500, outflow=0)
    assert t.update(500, outflow=50) == 50  # 50 L came in, 50 L left


def test_leak_moves_reference():
    t = tracker.InflowTracker(threshold=10)
    t.update(500)
    t.update(400)  # unmetered loss
    assert t.update(450) == 50


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
