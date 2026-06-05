"""Run the full analytics export pipeline."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    ROOT / "python" / "data_cleaning.py",
    ROOT / "python" / "segmentation.py",
    ROOT / "python" / "cohort_analysis.py",
    ROOT / "python" / "churn_analysis.py",
]


def main() -> None:
    for script in SCRIPTS:
        print(f"Running {script.name}...")
        subprocess.run([sys.executable, str(script)], check=True)
    print("Pipeline complete. Tableau exports are available in tableau/exports.")


if __name__ == "__main__":
    main()
