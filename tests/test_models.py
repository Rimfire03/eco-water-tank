import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "models",
    pathlib.Path(__file__).parent.parent / "custom_components/eco_water_tank/models.py",
)
models = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(models)


def test_catalogue():
    assert len(models.MODELS) == 10
    assert models.MODELS["ETY05000"].liters == 5000
    assert models.MODELS["ETM10000"].liters == 10000
    assert models.MODELS["ETY05000"].label == "Plasteau ECOCITER 5000 L (ETY05000)"
    assert models.CUSTOM not in models.MODELS


def test_box():
    assert models.box_liters(200, 100, 150) == 3000


def test_custom_liters():
    assert models.custom_liters(models.SHAPE_RECT, width=200, length=100, height=150) == 3000
    assert models.custom_liters(models.SHAPE_ROUND, diameter=100, height=100) == 785.4
    assert models.custom_liters(models.SHAPE_ROUND, width=100, length=100, height=100) is None
    assert models.custom_liters(models.SHAPE_RECT, diameter=100, height=100) is None


if __name__ == "__main__":
    test_catalogue()
    test_box()
    test_custom_liters()
    print("ok")
