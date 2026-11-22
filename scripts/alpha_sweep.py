"""Run TraCI OVM at one fixed density over a range of relaxation rates."""
import argparse
import math
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# At 30 veh/km with the default config, continuous OVM theory predicts
# alpha_c = 2 V'(h) ~= 5.59 /s. Sample more densely around that boundary.
DEFAULT_ALPHAS = [1.0, 2.0, 3.0, 4.0, 5.0]


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


def alpha_tag(alpha):
    """Return a compact filesystem-safe representation of alpha."""
    return f"{alpha:.3f}".rstrip("0").rstrip(".").replace(".", "p")


def theoretical_threshold(cfg, vehicles):
    """Return (effective uniform gap, V'(gap), alpha_c) for this experiment."""
    length_m = float(cfg["ring"]["length_m"])
    spacing = length_m / vehicles
    gap = spacing - float(cfg["vtype"]["length"]) - float(cfg["vtype"]["minGap"])
    if gap < 0:
        raise ValueError("configured vehicles do not fit on the ring")

    vmax = float(cfg["vtype"]["maxSpeed"])
    h_c = float(cfg["ovm"]["h_c"])
    scale = float(cfg["ovm"]["h_scale"])
    if scale <= 0:
        raise ValueError("ovm.h_scale must be positive")

    x = (gap - h_c) / scale
    v_prime = (vmax / scale) / (math.cosh(x) ** 2 * (1 + math.tanh(h_c / scale)))
    return gap, v_prime, 2 * v_prime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="configs/ring/OVM_1200_alpha_sweep.toml",
    )
    parser.add_argument(
        "--vehicles",
        type=int,
        help="fixed vehicle count; defaults to the config's single sweep value",
    )
    parser.add_argument(
        "--alphas",
        type=float,
        nargs="+",
        default=DEFAULT_ALPHAS,
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

    if cfg.get("model", "").upper() != "OVM":
        parser.error("the configuration must use model = 'OVM'")
    if str(cfg.get("implementation", "traci")).lower() != "traci":
        parser.error("the alpha sweep requires implementation = 'traci'")
    if "ovm" not in cfg:
        parser.error("the configuration must contain an [ovm] table")

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
        parser.error("OVM requires at least two vehicles")

    if not args.alphas or any(alpha <= 0 for alpha in args.alphas):
        parser.error("all alpha values must be positive")
    if len(set(args.alphas)) != len(args.alphas):
        parser.error("alpha values must not contain duplicates")

    dt = float(cfg["run"]["step_s"])
    overshooting = [alpha for alpha in args.alphas if alpha * dt > 1 + 1e-12]
    if overshooting:
        parser.error(
            "alpha * step_s must not exceed 1 for this sweep; "
            f"reduce step_s or remove {overshooting}"
        )

    length_m = float(cfg["ring"]["length_m"])
    density = vehicles / (length_m / 1000)
    gap, v_prime, alpha_c = theoretical_threshold(cfg, vehicles)
    seeds = cfg["sweep"]["seeds"]

    print(f"Road length: {length_m:.0f} m", flush=True)
    print(f"Vehicles: {vehicles}", flush=True)
    print(f"Density: {density:.2f} veh/km", flush=True)
    print(f"Uniform effective gap h: {gap:.3f} m", flush=True)
    print(f"V'(h): {v_prime:.4f} 1/s", flush=True)
    print(f"Continuous-theory alpha_c = 2 V'(h): {alpha_c:.4f} 1/s", flush=True)
    print(f"Seeds: {seeds}", flush=True)
    print(f"Alpha values: {args.alphas}", flush=True)
    print(f"Total runs: {len(args.alphas) * len(seeds)}", flush=True)

    for index, alpha in enumerate(args.alphas, start=1):
        tag = alpha_tag(alpha)
        name = f"OVM_alpha_L{int(length_m)}_N{vehicles}_a{tag}"
        variant = f"traci-dt{str(dt).replace('.', 'p')}-alpha-{tag}"
        prediction = "unstable" if alpha < alpha_c else "stable"

        modified = original
        modified = replace_toml_value(modified, None, "name", f'"{name}"')
        modified = replace_toml_value(modified, None, "variant", f'"{variant}"')
        modified = replace_toml_value(modified, "sweep", "vehicles", f"[{vehicles}]")
        modified = replace_toml_value(modified, "ovm", "alpha", f"{alpha:g}")

        print(
            f"\n[{index}/{len(args.alphas)}] alpha={alpha:g} 1/s, "
            f"theory={prediction}, experiment={name}",
            flush=True,
        )
        if args.dry_run:
            continue

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".toml",
            prefix="_alpha_",
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

    print("\nAlpha sweep completed.", flush=True)


if __name__ == "__main__":
    main()
