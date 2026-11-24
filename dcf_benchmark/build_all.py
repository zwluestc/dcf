"""One-command reproducible, zero-human-in-the-loop benchmark generator for DCFEval."""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from audit_sources import audit
from generate import build as build_structured
from raw import build as build_raw
from reference import main as build_reference


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(dataset_dir: Path, manifest_path: Path, seed: int, waves: int, audit_counts: dict):
    tasks = []
    quadrants = {}
    for task in sorted(dataset_dir.glob("dcf-*")):
        canon = json.loads((task / "solution/canonical.json").read_text())
        ans = json.loads((task / "tests/answers.json").read_text())
        st = ans["base"]["Statements"]
        dcf = ans["base"]["DCF"]
        ebitda25 = st["B10"] + st["B9"]
        quad = f"{canon['terminal']} / {canon['timing']}"
        quadrants[quad] = quadrants.get(quad, 0) + 1
        tasks.append(
            {
                "task": task.name,
                "wave": canon.get("wave", 0) + 1,
                "company": canon.get("company", ""),
                "slug": canon["slug"],
                "title": canon["title"],
                "seed": canon["seed"],
                "terminal": canon["terminal"],
                "timing": canon["timing"],
                "fy25_revenue": round(st["B6"], 4),
                "fy25_ebitda": round(ebitda25, 4),
                "wacc": round(dcf["B4"], 6),
                "tv": round(dcf["B5"], 4),
                "pv_tv": round(dcf["B6"], 4),
                "ev": round(dcf["B7"], 4),
                "equity_value": round(dcf["B8"], 4),
                "share_price": round(dcf["B9"], 4),
                "pv_tv_share": round(dcf["B6"] / dcf["B7"], 4),
                "ev_to_fy25_ebitda": round(dcf["B7"] / ebitda25, 2),
                "audit_checked_values": audit_counts.get(task.name, 0),
                "sha256": {
                    "instruction": sha256_file(task / "instruction.md"),
                    "answers": sha256_file(task / "tests/answers.json"),
                    "grade": sha256_file(task / "tests/grade.py"),
                    "operations_memo": sha256_file(task / "environment/data/operations_memo.md"),
                },
            }
        )
    manifest = {
        "schema_version": "3.0",
        "seed": seed,
        "waves": waves,
        "num_tasks": len(tasks),
        "quadrant_counts": quadrants,
        "total_audit_checked_values": sum(audit_counts.values()),
        "tasks": tasks,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=2026, help="Master random seed for scaling task generation")
    p.add_argument("--waves", type=int, default=2, help="Number of 10-case waves (default 2 -> 20 tasks)")
    p.add_argument("--out", type=Path, default=Path("DCFEval"), help="Output Harbor dataset directory")
    p.add_argument("--manifest", type=Path, default=Path("results/manifest.json"), help="Output manifest JSON path")
    args = p.parse_args()

    with tempfile.TemporaryDirectory() as td:
        staged = Path(td) / "structured"
        print(f"[1/4] Generating structured canonical cases (seed={args.seed}, waves={args.waves})...")
        build_structured(staged, args.seed, waves=args.waves)

        print(f"[2/4] Compiling 7-exhibit raw Harbor tasks -> {args.out}...")
        build_raw(staged, args.out)

    print("[3/4] Generating dynamic-formula Excel reference workbooks strictly from public exhibits (openpyxl)...")
    build_reference(args.out)

    print("[4/4] Auditing independent round-trip reconstruction strictly from public exhibits...")
    totals = {}
    for task in sorted(args.out.glob("dcf-*")):
        totals[task.name] = audit(task)
    manifest = write_manifest(args.out, args.manifest, args.seed, args.waves, totals)
    print(
        f"Audit passed across {manifest['num_tasks']} tasks "
        f"({manifest['total_audit_checked_values']:,} checked values, quadrants={manifest['quadrant_counts']})."
    )
    print(f"Wrote manifest -> {args.manifest}")


if __name__ == "__main__":
    main()
