"""Load experiment configurations from configs/<scenario>/<name>.toml."""
import hashlib
import tomllib
from pathlib import Path

from . import ROOT


def load(path):
    """Return the configuration as a dict, plus its repository-relative path and hash.

    The hash goes into every run record, so a result can be traced back to the
    exact configuration even if the file is edited later.
    """
    path = Path(path).resolve()
    raw = path.read_bytes()
    cfg = tomllib.loads(raw.decode("utf-8"))
    for key in ("name", "scenario", "model"):
        if key not in cfg:
            raise ValueError(f"{path.name}: missing top-level key '{key}'")
    cfg["_path"] = str(path.relative_to(ROOT))
    cfg["_sha256"] = hashlib.sha256(raw).hexdigest()[:12]
    return cfg
