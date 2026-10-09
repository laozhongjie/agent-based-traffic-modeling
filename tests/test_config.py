import pytest

from traffic_project import config


def test_load_adds_path_and_hash(tmp_root):
    path = tmp_root / "configs" / "ring" / "a.toml"
    path.parent.mkdir(parents=True)
    path.write_text('name = "a"\nscenario = "ring"\nmodel = "IDM"\n[run]\nend_s = 10\n')
    cfg = config.load(path)
    assert cfg["run"]["end_s"] == 10
    assert cfg["_path"] == "configs/ring/a.toml"
    assert len(cfg["_sha256"]) == 12

    path.write_text(path.read_text().replace("10", "20"))
    assert config.load(path)["_sha256"] != cfg["_sha256"]


@pytest.mark.parametrize("missing", ["name", "scenario", "model"])
def test_load_requires_top_level_keys(tmp_root, missing):
    keys = {"name": "a", "scenario": "ring", "model": "IDM"}
    del keys[missing]
    path = tmp_root / "a.toml"
    path.write_text("".join(f'{k} = "{v}"\n' for k, v in keys.items()))
    with pytest.raises(ValueError, match=missing):
        config.load(path)
