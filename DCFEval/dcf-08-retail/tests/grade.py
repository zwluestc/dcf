"""Grade one isolated DCF workbook via headless LibreOffice recalculation (v3.0 Practitioner Edition).

Practitioner-aligned Four-Pillar Rubric (raw_score = 100%):
1. Three-Statement & FCFF Forecast Accuracy (40%):
   - `history` (7%): FY2025 closing balance sheet & income statement consolidation (19 cells).
   - `forecast` (21%): FY2026-2030 operating drivers, IS, BS, and CFS lines (130 cells).
   - `fcff` (12%): FY2026-2030 unlevered tax, Change in NWC, FCFF, and PV of FCFF (20 cells).
2. Valuation Bridge & Per-Share Accuracy (25%):
   - `valuation` (25%): Materiality-weighted DCF outputs — core valuation bridge `DCF!B4:B9` (20%,
     with intrinsic share price `B9` = 5%, `EV`/`EqV` = 3.5% each, `WACC` = 3%, `TV`/`PV(TV)` = 2.5% each)
     plus Peer Beta & TSM dilution schedule `DCF!B12:B15` (5%, 1.25% each).
3. Accounting Integrity & Model Hygiene (15%):
   - `ties` (9%): 20 base FY2026-2030 accounting identities (BS balance, Cash roll, Equity roll, FCFF tie).
   - `ties_shock` (4%): 40 post-shock dynamic accounting identities across `operations` and `collection`
     shocks (verifying the balance sheet and cash flow remain balanced when assumptions change).
   - `controls` (2%): Editable `Inputs!B4:B6`, year headers `Statements!B3:G3`, and zero Excel formula errors.
4. Assumption Sensitivity Delta Linkage (20%):
   - `shock_operations` (7%), `shock_collection` (6%), `shock_discount` (7%): Graded on shock response
     deltas `(actual_shock - actual_base)` vs `(expected_shock - expected_base)` so localized base errors
     are never double-counted when downstream sensitivity mechanics are genuinely linked.

Anti-Hardcoding Dynamic Gate (`dynamic_gate` in [0.20, 1.00]):
- Combines recursive formula AST + leaf-input perturbation (`leaf_probe`, blocking `=const + 0*Inputs!B4`
  dead-reference cheats across all 155 computed cells) with live shock responsiveness (`responsiveness_ratio`,
  checking whether shock-sensitive cells actually move, independent of base-level offsets).
- `dynamic_gate = 0.20 + 0.80 * (0.65 * formula_ratio + 0.35 * responsiveness_ratio)`.
  Genuine dynamic models achieve `dynamic_gate = 1.0`; static pasted-value workbooks get `0.20` (`reward ~ 0.15`).
"""
import hashlib
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

SKIP_PROBE_INTS = {
    0, 1, 2, 3, 4, 5,
    100, 365, 1000, 10000, 100000, 1000000,
    1015, 1210, 1320, 1520, 2112, 2315, 2710, 3105, 4100, 5105, 6202, 6710, 7102, 7900,
}

DCF_CELL_WEIGHTS = {
    "B4": 3.0,    # WACC
    "B5": 2.5,    # Terminal value at FY2030 end
    "B6": 2.5,    # PV of terminal value
    "B7": 3.5,    # Enterprise value (EV)
    "B8": 3.5,    # Equity value
    "B9": 5.0,    # Intrinsic value per diluted share (EUR)
    "B12": 1.25,  # Relevered equity beta
    "B13": 1.25,  # Diluted shares (millions)
    "B14": 1.25,  # Median unlevered peer beta
    "B15": 1.25,  # TSM incremental shares (millions)
}


def is_num(x):
    return type(x) in (int, float) and math.isfinite(x)


def close(a, b):
    return is_num(a) and abs(a - b) <= max(1e-6, abs(b) * 1e-6)


def close_delta(actual_shock, actual_base, expected_shock, expected_base):
    if not (is_num(actual_shock) and is_num(actual_base)):
        return False, None, expected_shock - expected_base
    act_d = actual_shock - actual_base
    exp_d = expected_shock - expected_base
    tol = max(1e-6, abs(exp_d) * 1e-5, abs(expected_base) * 1e-6)
    if abs(act_d - exp_d) <= tol:
        return True, act_d, exp_d
    # Also accept exact proportional elasticity (%Δ) when multiplicative linkage is exact despite upstream scale offset
    if abs(expected_base) > 1e-2 and abs(actual_base) > 1e-2 and (actual_base * expected_base > 0):
        act_pct = act_d / actual_base
        exp_pct = exp_d / expected_base
        if abs(act_pct - exp_pct) <= max(1e-6, abs(exp_pct) * 1e-5):
            return True, act_d, exp_d
    return False, act_d, exp_d


def is_excel_error(val):
    return isinstance(val, str) and val.startswith(EXCEL_ERR_PREFIXES)


def resolves_to_computation(wb, sheet_name, cell_addr, allow_pure_input_link=False, visited=None):
    """Verify a cell is a genuine formula referencing upstream cells (not a constant or static alias)."""
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
        return allow_pure_input_link and type(target_cell.value) in (int, float)

    return bool(COMPUTE_OP_RE.search(expr))


def build_leaf_probe_workbook(src_path: Path, dst_path: Path):
    """Perturb static numeric leaf inputs slightly to detect dead-reference pseudo-formulas (e.g. `=val+0*B4`)."""
    w = load_workbook(src_path, keep_links=False)
    for ws in w.worksheets:
        for r in range(1, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(row=r, column=c)
                if cell.data_type == "f":
                    continue
                val = cell.value
                if type(val) not in (int, float) or not math.isfinite(val):
                    continue
                if ws.title == "Inputs" and c == 2 and r in (4, 5, 6):
                    if r == 4:
                        cell.value = float(val) + 0.031
                    elif r == 5:
                        cell.value = float(val) + 2.3
                    else:
                        cell.value = float(val) + 0.0027
                    continue
                if float(val).is_integer():
                    iv = int(round(float(val)))
                    if 2000 <= iv <= 2100 or iv in SKIP_PROBE_INTS:
                        continue
                factor = 1.0 + 0.017 + 0.0023 * ((r * 7 + c * 13) % 9)
                cell.value = float(val) * factor
    w.save(dst_path)
    w.close()


def check_accounting_ties(ws):
    """Return list of (col_label, err_val, bs_sig) for the 20 forecast accounting ties across C..G."""
    out = []
    for idx, cc in enumerate("CDEFG"):
        get = lambda i, col=cc: ws[col + str(i)].value
        prior = lambda i, pcol="BCDEF"[idx]: ws[pcol + str(i)].value
        bs_sig = (get(14), get(22), get(24))  # AR, Cash, Total Assets
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
            out.append((f"{cc}:{label}", err, bs_sig))
    return out


def run_soffice_recalc(src_dir: Path, out_dir: Path, timeout: int = 125):
    engine = os.getenv("SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice")
    if not engine:
        raise RuntimeError("Calc recalculation engine unavailable")
    subprocess.run(
        [
            engine,
            "-env:UserInstallation=" + (src_dir / "profile").as_uri(),
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--convert-to",
            "xlsx",
            "--outdir",
            str(out_dir),
            *map(str, sorted(src_dir.glob("*.xlsx"))),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        check=True,
        timeout=timeout,
    )


def structure_fingerprint(wb, editable):
    """Hash the inherited layout and unaffected model, independent of ZIP serialization."""
    names = wb.defined_names
    entries = names.values() if hasattr(names,"values") else names.definedName
    signature = {"names":sorted((n.name,n.attr_text) for n in entries), "sheets":[]}
    for ws in wb.worksheets:
        free=set(editable.get(ws.title,()))
        cells=[]
        for row in ws.iter_rows():
            for cell in row:
                val=cell.value
                if val is None and not cell.has_style and cell.coordinate not in free: continue
                if cell.coordinate in free: val="<editable>"
                elif type(val) in (float,int): val=format(val,".12g")
                cells.append((cell.coordinate,val,cell.number_format))
        signature["sheets"].append((ws.title,ws.sheet_state,ws.freeze_panes,sorted(str(r) for r in ws.merged_cells.ranges),
            sorted((k,v.width,v.hidden) for k,v in ws.column_dimensions.items()),
            sorted((k,v.height,v.hidden) for k,v in ws.row_dimensions.items()),cells))
    return hashlib.sha256(json.dumps(signature,ensure_ascii=False).encode()).hexdigest()


FILING_HISTORY_ROWS = {"N01":6,"IS02":7,"IS03":8,"IS04":9,"IS05":11,"IS06":12,
                       "BS01":14,"BS02":15,"BS03":16,"BS04":19,"BS05":22,"BS06":23,
                       "N04":20,"N03-N04":20}


def filing_increment(ref):
    return (int(hashlib.sha256(ref.encode()).hexdigest()[:4],16)+1)/10000


def build_filing_probe(src,dst,spec):
    wb=load_workbook(src)
    if "Ledger" in wb.sheetnames:
        sheet=wb["Ledger"]
        for r in range(4,32):
            ref=sheet[f"G{r}"].value
            native=sheet[f"D{r}"].value
            if ref in spec["filing_evidence"] and is_num(native):
                sheet[f"D{r}"]=native+filing_increment(ref)*spec["filing_evidence"][ref][1]
    wb.save(dst)
    wb.close()


def grade(path, spec, recalc_fn=None):
    if not path.is_file():
        return {"reward": 0.0, "pass_strict": False, "reason": "missing output.xlsx"}
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist()) > 30_000_000 or any(
            "vbaProject" in i.filename or "externalLinks/" in i.filename for i in z.infolist()
        ):
            return {"reward": 0.0, "pass_strict": False, "reason": "not a self-contained xlsx"}

    groups = {}
    weighted_pts = {}
    examples = {}
    excel_errors = []

    def audit(group, address, actual, expected, ok=None, weight=1.0):
        ok = close(actual, expected) if ok is None else bool(ok)
        pair = groups.setdefault(group, [0, 0])
        pair[0] += int(ok)
        pair[1] += 1
        w_pair = weighted_pts.setdefault(group, [0.0, 0.0])
        w_pair[0] += weight if ok else 0.0
        w_pair[1] += weight
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

        inherited = spec.get("inherited")
        if inherited and structure_fingerprint(wb,inherited["editable"]) != inherited["digest"]:
            wb.close()
            return {"reward":0.0,"pass_strict":False,"reason":"inherited workbook structure or unaffected content changed"}
        filing_formulas = set()
        if "Ledger" in wb.sheetnames:
            for r in range(4,32):
                if wb["Ledger"][f"F{r}"].data_type=="f":
                    filing_formulas.add(r)
        for cell, v in spec["controls"].items():
            audit("controls", "Inputs!" + cell, wb["Inputs"][cell].value, v)

        # Static AST audit on the 155 computed cells (Row 8 exogenous fixed opex is exempted)
        static_formula_ok = {}
        for sheet, cells in base.items():
            for cell in cells:
                if sheet == "DCF" or (cell[0] != "B" and int(cell[1:]) != 8):
                    static_formula_ok[(sheet, cell)] = resolves_to_computation(
                        wb, sheet, cell, allow_pure_input_link=False
                    )
        wb.close()

        shutil.copyfile(path, p / "base.xlsx")
        build_leaf_probe_workbook(path, p / "leaf_probe.xlsx")
        if spec.get("filing_evidence"):
            build_filing_probe(path,p/"filing_probe.xlsx",spec)
        for k, v in spec["shocks"].items():
            w = load_workbook(path, keep_links=False)
            for addr, n in v["changes"].items():
                w["Inputs"][addr] = n
            w.save(p / (k + ".xlsx"))
            w.close()

        if recalc_fn is not None:
            recalc_fn(p, out)
        else:
            run_soffice_recalc(p, out, timeout=125)

        # 1. Read recalculated base and leaf_probe workbooks
        w_base = load_workbook(out / "base.xlsx", data_only=True, read_only=False)
        w_probe = load_workbook(out / "leaf_probe.xlsx", data_only=True, read_only=False)

        actual_base = {"Statements": {}, "DCF": {}}
        for sh, cs in base.items():
            for c, v in cs.items():
                aval = w_base[sh][c].value
                actual_base[sh][c] = aval
                if is_excel_error(aval) and len(excel_errors) < 20:
                    excel_errors.append([sh + "!" + c, aval])
                r = int(c[1:])
                if sh == "DCF":
                    audit("valuation", f"DCF!{c}", aval, v, weight=DCF_CELL_WEIGHTS.get(c, 1.25))
                elif c[0] == "B":
                    audit("history", f"Statements!{c}", aval, v)
                elif r >= 30:
                    audit("fcff", f"Statements!{c}", aval, v)
                else:
                    audit("forecast", f"Statements!{c}", aval, v)

        # Combine static AST + live leaf_probe sensitivity for the 155 formula cells
        for (sh, c), ast_ok in static_formula_ok.items():
            bval = actual_base[sh][c]
            pval = w_probe[sh][c].value
            if not ast_ok:
                audit("formulas", f"{sh}!{c}", "non_formula_or_static_alias", "live_formula", ok=False)
            elif is_num(bval) and abs(bval) > 1e-9:
                moved = is_num(pval) and abs(pval - bval) > max(1e-9, abs(bval) * 1e-8)
                audit(
                    "formulas",
                    f"{sh}!{c}",
                    bval if not moved else "live_formula",
                    "live_formula_sensitive_to_inputs",
                    ok=moved,
                )
            else:
                audit("formulas", f"{sh}!{c}", "live_formula", "live_formula", ok=True)

        if spec.get("filing_evidence"):
            filing_probe=load_workbook(out/"filing_probe.xlsx",data_only=True)
            by_source = {}
            deltas = {}
            for ref in spec["filing_evidence"]:
                hist_row=FILING_HISTORY_ROWS[ref.split("#")[1]]
                deltas[hist_row]=deltas.get(hist_row,0)+filing_increment(ref)
            if "Ledger" in w_base.sheetnames:
                ledger=w_base["Ledger"]
                for r in range(4,32):
                    ref=ledger[f"G{r}"].value
                    by_source.setdefault(ref,[]).append((r,[ledger[f"{c}{r}"].value for c in "DEF"]))
            for ref,expected in spec["filing_evidence"].items():
                found=by_source.get(ref,[])
                ok=(len(found)==1 and found[0][0] in filing_formulas and
                    all(close(v,target) for v,target in zip(found[0][1],expected)))
                if ok:
                    changed = filing_probe["Ledger"][f"F{found[0][0]}"].value
                    ok=close(changed,expected[2]+filing_increment(ref))
                audit("filings",ref,found,expected,ok=ok)
            for hist_row,delta in deltas.items():
                addr=f"B{hist_row}"
                old=w_base["Statements"][addr].value
                new=filing_probe["Statements"][addr].value
                measured=new-old if is_num(new) and is_num(old) else None
                audit("filing_links","Statements!"+addr,measured,delta)
            filing_probe.close()
        ws_base = w_base["Statements"]
        for j, cc in enumerate("BCDEFG"):
            audit("controls", cc + "3", ws_base[cc + "3"].value, 2025 + j)
        audit("controls", "Workbook!zero_excel_errors", len(excel_errors), 0, ok=(len(excel_errors) == 0))

        base_ties = check_accounting_ties(ws_base)
        base_bs_by_col = {}
        for label, err, bs_sig in base_ties:
            base_bs_by_col[label.split(":")[0]] = bs_sig
            audit("ties", label, err, 0)

        w_base.close()
        w_probe.close()

        # 2. Evaluate the 3 shocks using Delta (shock - base) + post-shock accounting ties + responsiveness
        responsive_moves = 0
        responsive_total = 0
        for k, v in spec["shocks"].items():
            w_sh = load_workbook(out / (k + ".xlsx"), data_only=True, read_only=False)
            for sh, cs in v["expected"].items():
                for c, exp_sh in cs.items():
                    exp_b = base[sh][c]
                    if abs(exp_sh - exp_b) <= max(1e-5, abs(exp_b) * 1e-5):
                        continue
                    act_sh = w_sh[sh][c].value
                    act_b = actual_base[sh][c]
                    responsive_total += 1
                    if is_num(act_sh) and is_num(act_b) and abs(act_sh - act_b) > 1e-9:
                        responsive_moves += 1
                    ok_d, act_d, exp_d = close_delta(act_sh, act_b, exp_sh, exp_b)
                    audit("shock_" + k, f"{sh}!{c}(Δ)", act_d, exp_d, ok=ok_d)

            # Operations and collection shocks directly alter BS/CFS; verify post-shock accounting ties hold
            if k in ("operations", "collection"):
                for label, err, sh_bs in check_accounting_ties(w_sh["Statements"]):
                    col_let = label.split(":")[0]
                    b_bs = base_bs_by_col.get(col_let, (None, None, None))
                    bs_moved = any(
                        is_num(sv) and is_num(bv) and abs(sv - bv) > 1e-6 for sv, bv in zip(sh_bs, b_bs)
                    )
                    tie_ok = close(err, 0) and bs_moved
                    audit("ties_shock", f"{k}:{label}", err if bs_moved else "static_unmoved_bs", 0, ok=tie_ok)
            w_sh.close()

    # Practitioner Four-Pillar Weights (Total = 100.0 points; `formulas` acts strictly via `dynamic_gate`)
    weights = dict(
        # Pillar 1: 3-Statement & FCFF Forecast Accuracy (40%)
        history=7.0,
        forecast=21.0,
        fcff=12.0,
        # Pillar 2: Valuation Bridge & Per-Share Accuracy (25%)
        valuation=25.0,
        # Pillar 3: Accounting Integrity & Model Hygiene (15%)
        ties=9.0,
        ties_shock=4.0,
        controls=2.0,
        # Pillar 4: Assumption Sensitivity Delta Linkage (20%)
        shock_operations=7.0,
        shock_collection=6.0,
        shock_discount=7.0,
    )
    raw_score = sum(
        weights[g] * (weighted_pts[g][0] / weighted_pts[g][1])
        for g in weights
        if g in weighted_pts and weighted_pts[g][1] > 0
    ) / 100.0

    # Anti-Hardcoding Dynamic Gate: checks live formula integrity + non-zero shock responsiveness
    f_ok, f_tot = groups.get("formulas", [0, 0])
    formula_ratio = f_ok / f_tot if f_tot else 0.0
    responsiveness_ratio = responsive_moves / responsive_total if responsive_total else 0.0
    s_ok = sum(groups[g][0] for g in ("shock_operations", "shock_collection", "shock_discount") if g in groups)
    s_tot = sum(groups[g][1] for g in ("shock_operations", "shock_collection", "shock_discount") if g in groups)
    shock_delta_ratio = s_ok / s_tot if s_tot else 0.0

    dynamic_gate = 0.20 + 0.80 * (0.65 * formula_ratio + 0.35 * responsiveness_ratio)
    filing_factor = 1.0
    if "filings" in groups:
        correct,total=groups["filings"]
        linked,links=groups["filing_links"]
        filing_factor=0.80+0.20*(correct+linked)/(total+links)
    reward = round(raw_score * dynamic_gate * filing_factor, 9)
    pass_strict = (reward == 1.0) and (len(excel_errors) == 0)

    pillar_scores = {
        "statements_and_fcff_40": round(
            sum(weights[g] * weighted_pts[g][0] / weighted_pts[g][1] for g in ("history", "forecast", "fcff") if g in weighted_pts),
            4,
        ),
        "valuation_bridge_25": round(
            weights["valuation"] * weighted_pts["valuation"][0] / weighted_pts["valuation"][1] if "valuation" in weighted_pts else 0.0,
            4,
        ),
        "accounting_integrity_15": round(
            sum(weights[g] * weighted_pts[g][0] / weighted_pts[g][1] for g in ("ties", "ties_shock", "controls") if g in weighted_pts),
            4,
        ),
        "sensitivity_delta_20": round(
            sum(
                weights[g] * weighted_pts[g][0] / weighted_pts[g][1]
                for g in ("shock_operations", "shock_collection", "shock_discount")
                if g in weighted_pts
            ),
            4,
        ),
    }

    return dict(
        reward=reward,
        pass_strict=pass_strict,
        raw_score=round(raw_score, 9),
        dynamic_gate=round(dynamic_gate, 9),
        formula_ratio=round(formula_ratio, 6),
        responsiveness_ratio=round(responsiveness_ratio, 6),
        shock_ratio=round(shock_delta_ratio, 6),
        pillars=pillar_scores,
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
