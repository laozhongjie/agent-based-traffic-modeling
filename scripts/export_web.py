"""Export an experiment's validated results to the website (docs/data/<scenario>/<name>.js).

Run it on the computer that ran the sweep, after the sweep finished from a clean commit:
    python scripts/export_web.py --config configs/ring/idm_sweep.toml
Add --allow-dirty to preview results from uncommitted code; the file is then marked as a draft.
See traffic_project.export_web for the file format and the checks.
"""
import argparse

from traffic_project import ROOT, config, export_web


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/<scenario>/<name>.toml")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="export runs from uncommitted code as a draft")
    args = ap.parse_args()
    try:
        out = export_web.export(config.load(args.config), allow_dirty=args.allow_dirty)
    except ValueError as e:
        raise SystemExit(f"export failed: {e}")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
