"""Reference acceptance and 6-category negative mutation tests (60 counterexamples) via LibreOffice."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from openpyxl import load_workbook

from grade import grade


def find_otm_row(ws_cap):
    quote = None
    for r in range(1, ws_cap.max_row + 1):
        if ws_cap.cell(row=r, column=1).value == "Market quote (EUR)":
            quote = float(ws_cap.cell(row=r, column=2).value)
            break
    for r in range(1, ws_cap.max_row + 1):
        lbl = ws_cap.cell(row=r, column=1).value
        if isinstance(lbl, str) and lbl.startswith("Tranche "):
            strike = float(ws_cap.cell(row=r, column=3).value)
            if quote is not None and strike > quote:
                return r
    raise ValueError("No OTM option tranche found in Capital sheet")


def eval_task(task: Path):
    spec = json.loads((task / "tests/answers.json").read_text())
    ref = task / "solution/reference.xlsx"
    good = grade(ref, spec)
    assert good["reward"] == 1.0 and good["pass_strict"], (task, good)
    result = {"oracle_local": good, "negative": {}}

    with tempfile.TemporaryDirectory() as tmp:
        tp = Path(tmp)
        engine = os.getenv("SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice")
        recalc_dir = tp / "recalc"
        recalc_dir.mkdir()
        subprocess.run(
            [
                engine,
                "-env:UserInstallation=" + (tp / "prof").as_uri(),
                "--headless",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(recalc_dir),
                str(ref),
            ],
            capture_output=True,
            check=True,
            timeout=60,
        )
        cached_ref = recalc_dir / ref.name

        modes = ["frozen", "terminal", "missing", "fake_formula", "alias_hardcode"] + (
            ["itm_filter"] if "B15" in spec["base"]["DCF"] else []
        )
        for mode in modes:
            p = tp / (mode + ".xlsx")
            if mode == "frozen":
                w = load_workbook(cached_ref, data_only=True)
                w.save(p)
                w.close()
            elif mode == "terminal":
                w = load_workbook(ref)
                w["DCF"]["B6"] = "=B5/(1+B4)^4"
                w.save(p)
                w.close()
            elif mode == "fake_formula":
                # Constant-literal pseudo-formulas without cell references
                w = load_workbook(ref)
                for cell in ("B12", "B13", "B14", "B15"):
                    if cell in spec["base"]["DCF"]:
                        w["DCF"][cell] = f"={spec['base']['DCF'][cell]}"
                w.save(p)
                w.close()
            elif mode == "alias_hardcode":
                # Sneaky bare-link alias to hardcoded numbers in a helper sheet
                w = load_workbook(ref)
                helper = w.create_sheet("Helper")
                for idx, cell in enumerate(("B12", "B13", "B14", "B15"), start=1):
                    if cell in spec["base"]["DCF"]:
                        helper[f"A{idx}"] = spec["base"]["DCF"][cell]
                        w["DCF"][cell] = f"=Helper!A{idx}"
                w.save(p)
                w.close()
            elif mode == "itm_filter":
                w = load_workbook(ref)
                otm_r = find_otm_row(w["Capital"])
                quote_r = next(
                    r for r in range(1, w["Capital"].max_row + 1) if w["Capital"].cell(row=r, column=1).value == "Market quote (EUR)"
                )
                w["Capital"][f"D{otm_r}"] = f"=B{otm_r}*(1-C{otm_r}/$B${quote_r})"
                w.save(p)
                w.close()

            r = grade(p, spec)
            assert r["reward"] < 1.0 and not r["pass_strict"], (task.name, mode, r)
            if mode == "frozen":
                assert r["reward"] < 0.25, f"frozen hardcoding score too high: {r['reward']}"
                assert all(r["groups"]["shock_" + g][0] == 0 for g in ["operations", "collection", "discount"])
            if mode in ("fake_formula", "alias_hardcode"):
                ok_f, tot_f = r["groups"]["formulas"]
                assert ok_f < tot_f, (mode, ok_f, tot_f)
            if mode in ("terminal", "itm_filter"):
                ok_v, tot_v = r["groups"]["valuation"]
                assert ok_v < tot_v
            if mode == "itm_filter":
                assert any(t[0] == "DCF!B9" for t in r["examples"]["valuation"])
            result["negative"][mode] = r
    return task.name, result


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else root.parent / "DCFEval"
    tasks = sorted(target.glob("dcf-*"))
    assert len(tasks) >= 10, f"expected >=10 tasks in {target}, got {len(tasks)}"
    with ThreadPoolExecutor(max_workers=2) as ex:
        result = dict(ex.map(eval_task, tasks))
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "results/acceptance.json"
    dest.parent.mkdir(exist_ok=True, parents=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for k, v in result.items():
        print(k, v["oracle_local"]["reward"], {m: r["reward"] for m, r in v["negative"].items()})
