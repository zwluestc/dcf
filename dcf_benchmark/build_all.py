"""One-command reproducible, zero-human-in-the-loop benchmark generator for DCFEval."""
import argparse
import shutil
import tempfile
from pathlib import Path

from generate import build as build_structured
from raw import build as build_raw
from reference import main as build_reference
from audit_sources import audit


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=2026, help="Master random seed for scaling task generation")
    p.add_argument("--out", type=Path, default=Path("DCFEval"), help="Output Harbor dataset directory")
    args = p.parse_args()

    with tempfile.TemporaryDirectory() as td:
        staged = Path(td) / "structured"
        print(f"[1/4] Generating structured canonical cases (seed={args.seed})...")
        build_structured(staged, args.seed)

        print(f"[2/4] Compiling 7-exhibit raw Harbor tasks -> {args.out}...")
        build_raw(staged, args.out)

    print(f"[3/4] Generating dynamic-formula Excel reference workbooks (openpyxl)...")
    build_reference(args.out)

    print(f"[4/4] Auditing independent reconstruction strictly from public exhibits...")
    totals = {}
    for task in sorted(args.out.glob("dcf-*")):
        totals[task.name] = audit(task)
    print(f"Audit passed across {len(totals)} tasks ({sum(totals.values())} checked values).")


if __name__ == "__main__":
    main()
