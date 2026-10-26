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


if __name__ == "__main__":
    test_catalogue()
    print("ok")
