import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "learner",
    pathlib.Path(__file__).parent.parent / "custom_components/eco_water_tank/learner.py",
)
learner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(learner)


def _cycle(lr, true_l_per_pct, cycles=60):
    out = 0.0
    p = 100.0
    lr.update(p, None, out)
    for _ in range(cycles):
        for _ in range(19):  # drain 5 % steps
            p -= 5
            out += 5 * true_l_per_pct
            lr.update(p, None, out)
        p = 100.0  # refill unmetered: skipped (no inlet), ref moves
        lr.update(p, None, out)


def test_prior_only_is_linear():
    lr = learner.Learner(1000, False, True)
    assert abs(lr.volume(50) - 500) < 1e-9
    assert abs(lr.volume(100) - 1000) < 1e-9


def test_learns_real_capacity_from_outlet():
    lr = learner.Learner(1000, False, True)  # user typed 1000, tank is 2000
    _cycle(lr, 20)
    assert abs(lr.volume(100) - 2000) < 100


def test_rise_without_inlet_ignored():
    lr = learner.Learner(1000, False, True)
    lr.update(10, None, 0)
    assert lr.update(60, None, 0) is False


def test_inlet_learns_rise():
    lr = learner.Learner(1000, True, False)
    lr.update(0, 0, None)
    assert lr.update(50, 1000, None) is True
    assert lr.volume(50) > 500


def test_meter_reset_skipped():
    lr = learner.Learner(1000, False, True)
    lr.update(80, None, 500)
    assert lr.update(40, None, 0) is False


def test_calibrate_pulls_curve():
    lr = learner.Learner(1000, False, False)  # no meter: calibration is the only data
    lr.calibrate(50, 600)  # prior says 500 L at 50 %
    assert 550 < lr.volume(50) < 600
    assert lr.volume(100) > 1000  # bins above 50 % untouched, below raised


def test_calibrate_repeated_converges():
    lr = learner.Learner(1000, False, False)
    for _ in range(10):
        lr.calibrate(80, 1600)
    assert abs(lr.volume(80) - 1600) < 60


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
