"""Grade one isolated DCF workbook via headless LibreOffice recalculation.

Key hardening features:
1. Recursive formula computation audit: blocks literal values, constant-literal formulas (=1.13),
   and alias links to hardcoded helper cells (=Helper!A1 where Helper!A1 is a static number).
2. Explicit Excel formula error audit (#REF!, #DIV/0!, #VALUE!, #NAME?, #N/A, Err:).
3. Three independent live input perturbation shocks (operations, collection, discount).
4. Dynamic Model Gate Multiplier: prevents zero-formula hardcoded sheets from outscoring genuine
   formula-driven models while keeping Oracle strictly at reward = 1.0.
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from openpyxl import load_workbook

CELL_REF_RE = re.compile(r"(?:(?:'[^']+'|[A-Za-z0-9_]+)!)?\$?[A-Za-z]{1,3}\$?\d+")
BARE_LINK_RE = re.compile(r"^=\s*(?:(?:'([^']+)'|([A-Za-z0-9_]+))!)?\$?([A-Za-z]{1,3})\$?(\d+)\s*$")
COMPUTE_OP_RE = re.compile(r"[+\-*/^]|[A-Za-z_][A-Za-z0-9_.]*\s*\(")
EXCEL_ERR_PREFIXES = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!", "Err:")


def close(a, b):
    return type(a) in (int, float) and math.isfinite(a) and abs(a - b) <= max(1e-6, abs(b) * 1e-6)


def is_excel_error(val):
    return isinstance(val, str) and val.startswith(EXCEL_ERR_PREFIXES)


def resolves_to_computation(wb, sheet_name, cell_addr, allow_pure_input_link=False, visited=None):
    """Verify a cell is a genuine formula referencing upstream cells (not a constant or static alias).

    - Bare aliases (`=OtherSheet!B5`) are traced recursively to confirm the upstream cell is either
      a genuine computation (default) or an input cell (when allow_pure_input_link=True, e.g. fixed opex).
    """
    if visited is None:
        visited = set()
    key = (sheet_name, cell_addr.replace("$", "").upper())
    if key in visited or sheet_name not in wb.sheetnames:
        return False
    visited.add(key)

    cell = wb[sheet_name][key[1]]
    if cell.data_type != "f" or not isinstance(cell.value, str):
        return False
    expr = cell.value.strip()
    if not CELL_REF_RE.search(expr):
        # Blocks constant-literal pseudo-formulas like =1.13 or =0.4
        return False

    m = BARE_LINK_RE.match(expr)
    if m:
        target_sheet = m.group(1) or m.group(2) or sheet_name
        target_addr = (m.group(3) + m.group(4)).upper()
        if target_sheet not in wb.sheetnames:
            return False
        target_cell = wb[target_sheet][target_addr]
        if target_cell.data_type == "f":
            return resolves_to_computation(wb, target_sheet, target_addr, allow_pure_input_link, visited)
        # Bare link to a numeric input cell is valid ONLY for pass-through input rows (e.g. fixed opex)
        return allow_pure_input_link and type(target_cell.value) in (int, float)

    return bool(COMPUTE_OP_RE.search(expr))


def grade(path, spec):
    if not path.is_file():
        return {"reward": 0.0, "pass_strict": False, "reason": "missing output.xlsx"}
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist()) > 30_000_000 or any(
            "vbaProject" in i.filename or "externalLinks/" in i.filename for i in z.infolist()
        ):
            return {"reward": 0.0, "pass_strict": False, "reason": "not a self-contained xlsx"}

    groups = {}
    examples = {}
    excel_errors = []

    def audit(group, address, actual, expected, ok=None):
        ok = close(actual, expected) if ok is None else ok
        pair = groups.setdefault(group, [0, 0])
        pair[0] += int(ok)
        pair[1] += 1
        if not ok and len(examples.setdefault(group, [])) < 8:
            examples[group].append([address, actual, expected])

    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        out = p / "results"
        out.mkdir()
        base = spec["base"]
        wb = load_workbook(path, keep_links=False)
        if not {"DCF", "Statements", "Inputs"}.issubset(wb.sheetnames):
            return {"reward": 0.0, "pass_strict": False, "reason": "missing required sheet(s)", "sheets": wb.sheetnames}

        for cell, v in spec["controls"].items():
            audit("controls", "Inputs!" + cell, wb["Inputs"][cell].value, v)

        # Row 8 in Statements (Cash operating expense) is an exogenous budget input, so it is graded
        # numerically in `forecast` without forcing an Excel formula (155 computed cells graded for formulas).
        for sheet, cells in base.items():
            for cell in cells:
                if sheet == "DCF" or (cell[0] != "B" and int(cell[1:]) != 8):
                    v = wb[sheet][cell]
                    ok = resolves_to_computation(wb, sheet, cell, allow_pure_input_link=False)
                    audit("formulas", sheet + "!" + cell, v.value, "live_formula_with_upstream_computation", ok)
        wb.close()

        shutil.copyfile(path, p / "base.xlsx")
        for k, v in spec["shocks"].items():
            w = load_workbook(path, keep_links=False)
            for addr, n in v["changes"].items():
                w["Inputs"][addr] = n
            w.save(p / (k + ".xlsx"))
            w.close()

        engine = os.getenv("SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice")
        if not engine:
            raise RuntimeError("Calc recalculation engine unavailable")
        subprocess.run(
            [
                engine,
                "-env:UserInstallation=" + (p / "profile").as_uri(),
                "--headless",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(out),
                *map(str, sorted(p.glob("*.xlsx"))),
            ],
            capture_output=True,
            check=True,
            timeout=125,
        )

        for k, target in [("base", base)] + [(k, v["expected"]) for k, v in spec["shocks"].items()]:
            w = load_workbook(out / (k + ".xlsx"), data_only=True, read_only=False)
            for sh, cs in target.items():
                for c, v in cs.items():
                    if k != "base" and close(v, base[sh][c]):
                        continue
                    actual_val = w[sh][c].value
                    if k == "base" and is_excel_error(actual_val) and len(excel_errors) < 20:
                        excel_errors.append([sh + "!" + c, actual_val])
                    r = int(c[1:])
                    group = (
                        "shock_" + k
                        if k != "base"
                        else ("valuation" if sh == "DCF" else "history" if c[0] == "B" else "fcff" if r >= 30 else "forecast")
                    )
                    audit(group, sh + "!" + c, actual_val, v)
            if k == "base":
                ws = w["Statements"]
                for j, cc in enumerate("BCDEFG"):
                    audit("controls", cc + "3", ws[cc + "3"].value, 2025 + j)
                for idx, cc in enumerate("CDEFG"):
                    get = lambda i: ws[cc + str(i)].value
                    prior = lambda i: ws["BCDEF"[idx] + str(i)].value
                    for label, fn in [
                        ("balance", lambda: get(24) - get(25)),
                        ("cash", lambda: get(22) - prior(22) - get(26) - get(27) - get(28)),
                        ("equity", lambda: get(23) - prior(23) - get(13)),
                        ("fcff", lambda: get(32) - get(10) + get(30) - get(9) + get(18) + get(31)),
                    ]:
                        try:
                            err = fn()
                        except (TypeError, ValueError):
                            err = None
                        audit("ties", cc + ":" + label, err, 0)
            w.close()

    weights = dict(
        controls=3,
        formulas=12,
        history=8,
        forecast=18,
        fcff=9,
        valuation=14,
        ties=9,
        shock_operations=9,
        shock_collection=9,
        shock_discount=9,
    )
    raw_score = sum(weights[g] * a / b for g, (a, b) in groups.items()) / 100.0

    # Dynamic Model Gate: prevents static hardcoded sheets from outscoring live formula models
    f_ok, f_tot = groups["formulas"]
    formula_ratio = f_ok / f_tot if f_tot else 0.0
    s_ok = sum(groups[g][0] for g in ("shock_operations", "shock_collection", "shock_discount") if g in groups)
    s_tot = sum(groups[g][1] for g in ("shock_operations", "shock_collection", "shock_discount") if g in groups)
    shock_ratio = s_ok / s_tot if s_tot else 0.0
    dynamic_gate = 0.25 + 0.75 * (0.6 * formula_ratio + 0.4 * shock_ratio)

    reward = round(raw_score * dynamic_gate, 9)
    pass_strict = (reward == 1.0) and (len(excel_errors) == 0)
    return dict(
        reward=reward,
        pass_strict=pass_strict,
        raw_score=round(raw_score, 9),
        dynamic_gate=round(dynamic_gate, 9),
        formula_ratio=round(formula_ratio, 6),
        shock_ratio=round(shock_ratio, 6),
        excel_errors=excel_errors,
        groups=groups,
        examples=examples,
    )


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("workbook", type=Path)
    a.add_argument("answers", type=Path)
    a.add_argument("report", type=Path)
    args = a.parse_args()
    try:
        res = grade(args.workbook, json.loads(args.answers.read_text()))
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, TypeError) as e:
        if isinstance(e, FileNotFoundError) and "results/" in str(e):
            res = {"reward": 0.0, "pass_strict": False, "reason": "Calc could not open submission"}
        elif isinstance(e, (FileNotFoundError, PermissionError)):
            raise
        else:
            res = {"reward": 0.0, "pass_strict": False, "reason": str(e)[:480]}
    args.report.parent.mkdir(exist_ok=True, parents=True)
    args.report.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    (args.report.parent / "reward.txt").write_text(str(res["reward"]) + "\n")
