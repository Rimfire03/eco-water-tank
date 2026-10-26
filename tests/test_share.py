import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "share",
    pathlib.Path(__file__).parent.parent / "custom_components/eco_water_tank/share.py",
)
share = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(share)


def test_build():
    url, text = share.build({"name": "My tank", "capacity": 3000, "curve": [10.0, 11.5]})
    assert url.startswith(share.REPO + "/issues/new?template=tank-model.yml")
    assert "capacity=3000" in url and "My+tank" in url
    assert '"capacity": 3000' in text


def test_refusals():
    assert share.refusal(1e6, 0, 0) is not None  # not learned
    assert share.refusal(1e6, 1e6 - 3600, 500) is not None  # cooldown
    assert share.refusal(1e6, 1e6 - 90000, 500) is None
    assert share.refusal(1e6, 0, 500) is None


if __name__ == "__main__":
    test_build()
    test_refusals()
    print("ok")
