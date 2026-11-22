"""Run NaSch at one fixed density over a range of slowdown probabilities."""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SIGMAS = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50,]


def replace_toml_value(text, section, key, value):
    """Replace a TOML key in a specified section (or at root)."""
    lines = text.splitlines(keepends=True)
    current_section = None
    found = False

    for i, line in enumerate(lines):
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
            lines[i] = f"{match.group(1)}{value}{comment}{newline}"
            found = True
            break

    if not found:
        raise ValueError(f"Missing TOML key: [{section}] {key}")

    return "".join(lines)


def set_root_toml_value(text, key, value):
    """Replace a root TOML key, or add it before the first table."""
    try:
        return replace_toml_value(text, None, key, value)
    except ValueError:
        lines = text.splitlines(keepends=True)
        insert_at = next(
            (i for i, line in enumerate(lines) if re.match(r"^\s*\[", line)),
            len(lines),
        )
        lines.insert(insert_at, f'{key} = {value}\n\n')
        return "".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/ring/NaSch_refined_4800_NaSch.toml",
    )
    parser.add_argument(
        "--vehicles",
        type=int,
        help="fixed vehicle count; defaults to the config's single sweep value",
    )
    parser.add_argument(
        "--sigmas",
        type=float,
        nargs="+",
        default=DEFAULT_SIGMAS,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print configurations without running SUMO",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path

    original = config_path.read_text(encoding="utf-8")

    # Read road length for reporting.
    import tomllib
    cfg = tomllib.loads(original)
    length_m = float(cfg["ring"]["length_m"])

    vehicles = args.vehicles
    if vehicles is None:
        configured = cfg["sweep"].get("vehicles")
        if not isinstance(configured, list) or len(configured) != 1:
            parser.error(
                "the config must define exactly one sweep.vehicles value, "
                "or pass --vehicles"
            )
        vehicles = int(configured[0])

    density = vehicles / (length_m / 1000)

    if vehicles < 1:
        parser.error("--vehicles must be positive")

    if any(not 0 <= sigma <= 1 for sigma in args.sigmas):
        parser.error("All sigma values must be between 0 and 1")

    seeds = cfg["sweep"]["seeds"]
    print(f"Road length: {length_m:.0f} m", flush=True)
    print(f"Vehicles: {vehicles}", flush=True)
    print(f"Density: {density:.2f} veh/km", flush=True)
    print(f"Seeds: {seeds}", flush=True)
    print(f"Sigma values: {args.sigmas}", flush=True)
    print(f"Total runs: {len(args.sigmas) * len(seeds)}", flush=True)

    for index, sigma in enumerate(args.sigmas, start=1):
        sigma_tag = f"{sigma:.2f}".replace(".", "p")
        name = (
            f"NaSch_sigma_L{int(length_m)}"
            f"_N{vehicles}_p{sigma_tag}"
        )
        variant = f"sigma_{sigma_tag}"

        modified = original
        modified = set_root_toml_value(modified, "name", f'"{name}"')
        modified = set_root_toml_value(modified, "variant", f'"{variant}"')
        modified = replace_toml_value(
            modified, "sweep", "vehicles", f"[{vehicles}]"
        )
        modified = replace_toml_value(
            modified, "vtype", "sigma", f"{sigma:.2f}"
        )

        print(
            f"\n[{index}/{len(args.sigmas)}] "
            f"sigma={sigma:.2f}, variant={variant}, experiment={name}",
            flush=True,
        )

        if args.dry_run:
            continue

        # Keep temporary config next to the original config.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".toml",
            prefix="_sigma_",
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

    print("\nSigma sweep completed.", flush=True)


if __name__ == "__main__":
    main()
