"""Run IDM at one fixed density over a range of acceleration parameters."""
import argparse
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ACCELS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]


def replace_toml_value(text, section, key, value):
    """Replace one TOML key in the requested table (or at the root)."""
    lines = text.splitlines(keepends=True)
    current_section = None

    for index, line in enumerate(lines):
        header = re.match(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$", line)
        if header:
            current_section = header.group(1).strip()
            continue
        if current_section != section:
            continue

        match = re.match(
            rf"^(\s*{re.escape(key)}\s*=\s*)([^#\r\n]*)(.*)$",
            line,
        )
        if match:
            newline = "\n" if line.endswith("\n") else ""
            comment = match.group(3).rstrip("\r\n")
            lines[index] = f"{match.group(1)}{value}{comment}{newline}"
            return "".join(lines)

    raise ValueError(f"Missing TOML key: [{section}] {key}")


def accel_tag(accel):
    """Return a compact filesystem-safe representation of acceleration."""
    return f"{accel:.3f}".rstrip("0").rstrip(".").replace(".", "p")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/ring/IDM_1200_accel_sweep.toml",
    )
    parser.add_argument(
        "--vehicles",
        type=int,
        help="fixed vehicle count; defaults to the config's single sweep value",
    )
    parser.add_argument(
        "--accels",
        type=float,
        nargs="+",
        default=DEFAULT_ACCELS,
        help="IDM accel values in m/s^2",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the planned experiments without running SUMO",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    original = config_path.read_text(encoding="utf-8")
    cfg = tomllib.loads(original)

    if cfg.get("model", "").upper() != "IDM":
        parser.error("the configuration must use model = 'IDM'")
    if cfg.get("vtype", {}).get("carFollowModel") != "IDM":
        parser.error("the configuration must use vtype.carFollowModel = 'IDM'")

    vehicles = args.vehicles
    if vehicles is None:
        configured = cfg["sweep"].get("vehicles")
        if not isinstance(configured, list) or len(configured) != 1:
            parser.error(
                "the config must define exactly one sweep.vehicles value, "
                "or pass --vehicles"
            )
        vehicles = int(configured[0])
    if vehicles < 2:
        parser.error("the sweep requires at least two vehicles")

    if not args.accels or any(accel <= 0 for accel in args.accels):
        parser.error("all accel values must be positive")
    if len(set(args.accels)) != len(args.accels):
        parser.error("accel values must not contain duplicates")

    length_m = float(cfg["ring"]["length_m"])
    density = vehicles / (length_m / 1000)
    seeds = cfg["sweep"]["seeds"]

    print(f"Road length: {length_m:.0f} m", flush=True)
    print(f"Vehicles: {vehicles}", flush=True)
    print(f"Density: {density:.2f} veh/km", flush=True)
    print(f"Seeds: {seeds}", flush=True)
    print(f"IDM accel values: {args.accels} m/s^2", flush=True)
    print(f"Fixed tau: {cfg['vtype']['tau']} s", flush=True)
    print(f"Fixed decel: {cfg['vtype']['decel']} m/s^2", flush=True)
    print(f"Total runs: {len(args.accels) * len(seeds)}", flush=True)

    for index, accel in enumerate(args.accels, start=1):
        tag = accel_tag(accel)
        name = f"IDM_accel_L{int(length_m)}_N{vehicles}_a{tag}"
        variant = f"accel-{tag}"

        modified = original
        modified = replace_toml_value(modified, None, "name", f'"{name}"')
        modified = replace_toml_value(modified, None, "variant", f'"{variant}"')
        modified = replace_toml_value(modified, "sweep", "vehicles", f"[{vehicles}]")
        modified = replace_toml_value(modified, "vtype", "accel", f"{accel:g}")

        print(
            f"\n[{index}/{len(args.accels)}] accel={accel:g} m/s^2, "
            f"variant={variant}, experiment={name}",
            flush=True,
        )
        if args.dry_run:
            continue

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".toml",
            prefix="_accel_",
            dir=config_path.parent,
            encoding="utf-8",
            delete=False,
        ) as tmp:
            tmp.write(modified)
            temp_path = Path(tmp.name)

        try:
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "ring_sweep.py"),
                    "--config",
                    str(temp_path),
                ],
                cwd=ROOT,
                check=True,
            )
        finally:
            temp_path.unlink(missing_ok=True)

    print("\nIDM acceleration sweep completed.", flush=True)


if __name__ == "__main__":
    main()
