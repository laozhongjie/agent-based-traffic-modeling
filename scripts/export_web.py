"""Export an experiment's validated results to the website (docs/data/<page>/<name>.js).

Run it on the computer that ran the sweep, after the sweep finished from a clean commit:
    python scripts/export_web.py --config configs/ring/idm_sweep.toml
Add --allow-dirty to preview results from uncommitted code; the file is then marked as a draft.
The file goes to docs/data/<page>/, the site page that shows it: ring, network (city runs) or
planning (a config with [network] variant); --page overrides it.
See traffic_project.export_web and GUIDE section 6, "Website files", for the format and the checks.
"""
import argparse

from traffic_project import ROOT, config, export_web


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="configs/<scenario>/<name>.toml")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="export runs from uncommitted code as a draft")
    ap.add_argument("--page", help="site page folder docs/data/<page>/ (default: from the config)")
    args = ap.parse_args()
    try:
        out = export_web.export(config.load(args.config), allow_dirty=args.allow_dirty, page=args.page)
    except ValueError as e:
        raise SystemExit(f"export failed: {e}")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
