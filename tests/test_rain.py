import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "rain",
    pathlib.Path(__file__).parent.parent / "custom_components/eco_water_tank/rain.py",
)
rain = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rain)


def test_collected_estimate():
    r = rain.RainTracker(100, 0.8)  # 100 m², 80 %
    r.update(0, 0, 10)
    r.update(1.0, 0, 10)  # 1 mm -> 100 L potential, 80 L collected
    assert abs(r.total - 80) < 1e-9


def test_learns_efficiency():
    r = rain.RainTracker(100, 0.9)
    mm, intake = 0.0, 0.0
    r.update(mm, intake, 20)
    for _ in range(100):
        mm += 1
        intake += 60  # tank really gains 60 % of the potential
        r.update(mm, intake, 40)
    assert abs(r.efficiency() - 0.6) < 0.05


def test_overflow_when_full():
    r = rain.RainTracker(100, 0.8)
    r.update(0, 0, 95)
    r.update(1.0, 0, 95)  # tank full, gained nothing
    assert abs(r.overflow - 80) < 1e-9
    assert r.s_rain == 0  # not learned from a full tank


def test_mains_topup_ignored():
    r = rain.RainTracker(100, 0.8)
    r.update(0, 0, 10)
    r.update(0.5, 2000, 40)  # 50 L potential but tank gained 2000 L
    assert r.s_rain == 0


def test_small_step_and_reset():
    r = rain.RainTracker(100, 0.8)
    r.update(5, 0, 10)
    r.update(5.1, 0, 10)  # below one gauge tick: waits
    assert r.total == 0
    r.update(1, 0, 10)  # gauge reset: no negative sample
    assert r.total == 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
