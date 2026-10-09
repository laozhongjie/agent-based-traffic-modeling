"""Shared simulation and analysis code for the traffic-congestion project.

Modules:
    config        load an experiment configuration (TOML)
    io            read SUMO outputs, write result tables
    runner        run SUMO for one run folder, write the run record and checks
    measurements  turn SUMO outputs into measured quantities
    results       result data format: writers for experiments, readers for analysis
    export_web    export validated results to the website (docs/data/<scenario>/)

Scripts in scripts/ import from here instead of copying code. Changes to this
package go through a pull request reviewed by A (see docs/guide.html).
Run the tests in tests/ with pytest from the repository root after every change.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
