"""Reference acceptance, alternative-layout verification, practitioner fairness, and 7-category negative tests.

Verifies for every task (100 total checks across 10 tasks):
1. Reference Oracle (`solution/reference.xlsx`): reward == 1.0, pass_strict == True.
2. Independent Alternative Layout (`alt_layout.xlsx`): completely different helper sheet names,
   minimal Inputs sheet (only B4:B6), exogenous numeric row 8, plain actuals without Ledger,
   equivalent alternative Excel formulas, and cross-sheet DCF!B12:B15 links -> MUST ALSO score 1.0!
3. Practitioner Fairness (`single_dep_bug.xlsx`): 100% live dynamic formulas with one upstream parenthesis
   typo in Depreciation -> `dynamic_gate == 1.0` (zero anti-hardcoding gate penalty), `ties == 20/20`,
   `ties_shock == 40/40`, `shock_collection` 100%, and `0.65 < reward < 1.0`.
4. Seven negative mutation counterexamples (70 total across 10 tasks): frozen (<0.20), terminal,
   missing, fake_formula, alias_hardcode, zero_mul_cheat, itm_filter -> ALL strictly < 1.0.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from openpyxl import Workbook, load_workbook

from audit_sources import parse_filings
from grade import build_leaf_probe_workbook, grade, run_soffice_recalc


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


def build_alt_layout_workbook(task: Path, out_path: Path):
    """Build a valid DCF workbook with a completely different layout & equivalent formulas."""
    pub = task / "environment/data"
    spec = json.loads((task / "tests/answers.json").read_text())
    parsed = parse_filings(pub)
    d = parsed["case"]
    s = d["scalar"]
    series = d["series"]

    wb = Workbook()
    # Minimal Inputs sheet: ONLY editable B4:B6, zero extra parameters here
    ws_in = wb.active
    ws_in.title = "Inputs"
    ws_in["A4"], ws_in["B4"] = "price_multiplier", s["price_multiplier"]
    ws_in["A5"], ws_in["B5"] = "dso_shift", s["dso_shift"]
    ws_in["A6"], ws_in["B6"] = "risk_free", s["risk_free"]

    # Completely different helper sheet names & coordinates
    ws_ops = wb.create_sheet("Ops_Budget")
    ws_cap = wb.create_sheet("WACC_TSM")
    ws_st = wb.create_sheet("Statements")
    ws_dcf = wb.create_sheet("DCF")

    # Store non-editable scalar assumptions on WACC_TSM (not on Inputs!)
    ws_cap["A2"], ws_cap["B2"] = "ERP", s["erp"]
    ws_cap["A3"], ws_cap["B3"] = "DebtWeight", s["debt_weight"]
    ws_cap["A4"], ws_cap["B4"] = "DebtCost", s["debt_cost"]
    ws_cap["A5"], ws_cap["B5"] = "TaxRate", s["tax_rate"]
    ws_cap["A6"], ws_cap["B6"] = "GrowthG", s["g"]
    ws_cap["A7"], ws_cap["B7"] = "ExitMult", s["exit_multiple"]
    ws_cap["A8"], ws_cap["B8"] = "DepRate", s["dep_rate"]

    # Peer unlevering table in columns D:H of WACC_TSM (parsed from raw broker memo)
    peers = parsed["peer_rows"]
    for i, rec in enumerate(peers, start=2):
        ws_cap[f"D{i}"] = rec["peer"]
        ws_cap[f"E{i}"] = rec["observed_equity_beta"]
        ws_cap[f"F{i}"] = rec["net_debt_to_equity_x"]
        ws_cap[f"G{i}"] = rec["statutory_tax_pct"] / 100.0
        ws_cap[f"H{i}"] = f"=E{i}/(1+(1-G{i})*F{i})"
    peer_end = 1 + len(peers)
    # Compute capital metrics on WACC_TSM and cross-link into DCF!B12:B15
    ws_cap["B11"] = f"=MEDIAN(H2:H{peer_end})"
    ws_cap["B12"] = "=B11*(1+(1-B5)*B3/(1-B3))"

    basic = parsed["basic_shares"] / 1e6
    quote = parsed["market_quote"]
    opts = parsed["option_tranches"]
    ws_cap["B14"] = basic
    ws_cap["B15"] = quote
    for i, (cnt, stk) in enumerate(opts, start=17):
        ws_cap[f"A{i}"] = cnt / 1e6
        ws_cap[f"B{i}"] = stk
        # Equivalent IF formula instead of MAX(0, ...)
        ws_cap[f"C{i}"] = f"=IF(B{i}<$B$15,A{i}*(1-B{i}/$B$15),0)"
    opt_end = 16 + len(opts)
    ws_cap["B22"] = f"=SUM(C17:C{opt_end})"
    ws_cap["B23"] = "=B14+B22"

    # Preserve required legacy sheet names for brownfield tasks while still testing alt layout
    for req_sh in spec.get("required_sheets") or []:
        if req_sh not in wb.sheetnames:
            ws_extra = wb.create_sheet(req_sh)
            ws_extra["A1"] = f"Preserved legacy tab: {req_sh}"

    # Put annual drivers in Ops_Budget rows 2..6 (transposed vs reference!)
    drv_keys = ["A", "B", "C", "unit_price", "cogs_pct", "opex_fixed", "capex_pct", "dso", "dio", "dpo", "repay"]
    for t in range(5):
        r = 2 + t
        ws_ops.cell(r, 1, 2026 + t)
        for j, k in enumerate(drv_keys, start=2):
            ws_ops.cell(r, j, series[k][t])

    # Statements years
    for j, y in enumerate(range(2025, 2031), start=2):
        ws_st.cell(3, j, y)

    # FY2025 actuals entered directly as aggregated numbers (no Ledger tab!)
    h = {}
    for e in d["ledger"]:
        h[e["account"]] = h.get(e["account"], 0.0) + e["amount"]
    ws_st["B4"] = s["opening_units"]
    for row_num, key in [
        (6, "revenue"), (7, "cogs"), (8, "opex"), (9, "da"), (11, "interest"),
        (12, "tax"), (14, "ar"), (15, "inv"), (16, "ap"), (19, "ppe"),
        (20, "debt"), (22, "cash"), (23, "equity"),
    ]:
        ws_st[f"B{row_num}"] = h[key]
    ws_st["B10"] = "=B6-B7-B8-B9"
    ws_st["B13"] = "=B10-B11-B12"
    ws_st["B17"] = "=B14+B15-B16"
    ws_st["B24"] = "=B22+B14+B15+B19"
    ws_st["B25"] = "=B16+B20+B23"

    # Forecast columns C..G using DIFFERENT equivalent Excel formulas + numeric Row 8!
    for t in range(5):
        col = "CDEFG"[t]
        prev = "BCDEF"[t]
        orow = 2 + t
        A, B, C = f"Ops_Budget!B{orow}", f"Ops_Budget!C{orow}", f"Ops_Budget!D{orow}"
        P, CG, CP, DSO, DIO, DPO, REP = (
            f"Ops_Budget!E{orow}", f"Ops_Budget!F{orow}", f"Ops_Budget!H{orow}",
            f"Ops_Budget!I{orow}", f"Ops_Budget!J{orow}", f"Ops_Budget!K{orow}", f"Ops_Budget!L{orow}",
        )
        u = f"{prev}4"
        end = f"{col}4"
        op = {
            "saas": (f"{u}-{u}*{B}+{A}", f"0.5*({u}+{end})*(1+{C})"),
            "foundry": (f"{u}+{A}", f"IF({end}<{B},{end},{B})*{C}"),
            "orders": (f"{u}+{A}-{col}5", f"{u}*{B}+{A}*{C}"),
            "storage": (f"{u}*(1-{B})+MIN({A},IF({C}-{u}*(1-{B})>0,{C}-{u}*(1-{B}),0))", f"{u}*(1-{B})+0.5*({end}-{u}*(1-{B}))"),
            "fleet": (f"{u}*(1-{B})+{A}", f"({u}*(1-{B})+0.5*{A})*{C}"),
            "license": (f"{u}*{B}+{A}", f"{u}*{B}+{A}*(0.5+{C})"),
            "mine": (f"IF({u}+{A}>{B},{u}+{A}-{B},0)", f"({u}+{A}-{end})*{C}"),
            "retail": (f"{u}*(1-{B})+{A}", f"{u}*(1-{B})+{A}*{C}"),
            "royalty": (f"{u}+{A}", f"MAX(0.9*{u},MIN({end},{B})+IF({end}>{B},{end}-{B},0)*{C})"),
            "returns": (f"{u}*(1-{B})+{A}", f"{u}*(1-{B})+0.5*{A}-0.4*{u}*{C}"),
        }[d["slug"]]

        ws_st[f"{col}4"] = "=" + op[0]
        ws_st[f"{col}5"] = "=" + op[1]
        ws_st[f"{col}6"] = f"={col}5*{P}*Inputs!$B$4"
        ws_st[f"{col}7"] = f"={col}6*{CG}"
        # Deliberately put exogenous fixed opex as a PLAIN NUMERIC VALUE (not a formula!)
        ws_st[f"{col}8"] = series["opex_fixed"][t]
        ws_st[f"{col}18"] = f"={col}6*{CP}"
        ws_st[f"{col}9"] = f"=WACC_TSM!$B$8*({prev}19+0.5*{col}18)"
        ws_st[f"{col}10"] = f"={col}6-{col}7-{col}8-{col}9"
        ws_st[f"{col}21"] = f"=IF({prev}20<{REP},{prev}20,{REP})"
        ws_st[f"{col}20"] = f"={prev}20-{col}21"
        ws_st[f"{col}11"] = f"=0.5*({prev}20+{col}20)*WACC_TSM!$B$4"
        ws_st[f"{col}12"] = f"=IF({col}10-{col}11>0,({col}10-{col}11)*WACC_TSM!$B$5,0)"
        ws_st[f"{col}13"] = f"={col}10-{col}11-{col}12"
        ws_st[f"{col}14"] = f"={col}6*({DSO}+Inputs!$B$5)/365"
        ws_st[f"{col}15"] = f"={col}7*{DIO}/365"
        ws_st[f"{col}16"] = f"={col}7*{DPO}/365"
        ws_st[f"{col}17"] = f"={col}14+{col}15-{col}16"
        ws_st[f"{col}19"] = f"={prev}19+{col}18-{col}9"
        ws_st[f"{col}31"] = f"={col}17-{prev}17"
        ws_st[f"{col}26"] = f"={col}13+{col}9-{col}31"
        ws_st[f"{col}27"] = f"=-{col}18"
        ws_st[f"{col}28"] = f"=-{col}21"
        ws_st[f"{col}29"] = f"={col}26+{col}27+{col}28"
        ws_st[f"{col}22"] = f"={prev}22+{col}29"
        ws_st[f"{col}23"] = f"={prev}23+{col}13"
        ws_st[f"{col}24"] = f"={col}22+{col}14+{col}15+{col}19"
        ws_st[f"{col}25"] = f"={col}16+{col}20+{col}23"
        ws_st[f"{col}30"] = f"=IF({col}10>0,{col}10*WACC_TSM!$B$5,0)"
        ws_st[f"{col}32"] = f"={col}10-{col}30+{col}9-{col}18-{col}31"
        exp = (t + 0.5) if d["timing"] == "midyear" else (t + 1)
        ws_st[f"{col}33"] = f"={col}32/((1+DCF!$B$4)^{exp})"

    # DCF sheet: cross-link B12:B15 from WACC_TSM (tests recursive computation tracing!)
    ws_dcf["B14"] = "=WACC_TSM!B11"
    ws_dcf["B12"] = "=WACC_TSM!B12"
    ws_dcf["B15"] = "=WACC_TSM!B22"
    ws_dcf["B13"] = "=WACC_TSM!B23"
    ws_dcf["B4"] = "=(Inputs!$B$6+B12*WACC_TSM!$B$2)*(1-WACC_TSM!$B$3)+WACC_TSM!$B$4*(1-WACC_TSM!$B$5)*WACC_TSM!$B$3"
    ws_dcf["B5"] = (
        "=Statements!G32*(1+WACC_TSM!$B$6)/(B4-WACC_TSM!$B$6)"
        if d["terminal"] == "perpetuity"
        else "=(Statements!G10+Statements!G9)*WACC_TSM!$B$7"
    )
    ws_dcf["B6"] = "=B5/((1+B4)^5)"
    ws_dcf["B7"] = "=Statements!C33+Statements!D33+Statements!E33+Statements!F33+Statements!G33+B6"
    ws_dcf["B8"] = "=B7+Statements!B22-Statements!B20"
    ws_dcf["B9"] = "=B8/B13"

    wb.save(out_path)


def stage_for_batch(tag: str, wb_path: Path, spec: dict, batch_in: Path):
    shutil.copyfile(wb_path, batch_in / f"{tag}__base.xlsx")
    build_leaf_probe_workbook(wb_path, batch_in / f"{tag}__leaf_probe.xlsx")
    for k, v in spec["shocks"].items():
        w = load_workbook(wb_path, keep_links=False)
        for addr, n in v["changes"].items():
            w["Inputs"][addr] = n
        w.save(batch_in / f"{tag}__{k}.xlsx")
        w.close()


def make_recalc_loader(tag: str, batch_out: Path):
    def _loader(_src: Path, out: Path):
        for suffix in ("base", "leaf_probe", *("operations", "collection", "discount")):
            f = batch_out / f"{tag}__{suffix}.xlsx"
            if f.exists():
                shutil.copyfile(f, out / f"{suffix}.xlsx")
    return _loader


def eval_task(task: Path):
    spec = json.loads((task / "tests/answers.json").read_text())
    ref = task / "solution/reference.xlsx"
    result = {"oracle_local": None, "alt_layout": None, "single_dep_bug": None, "negative": {}}

    with tempfile.TemporaryDirectory() as tmp:
        tp = Path(tmp)
        batch_in = tp / "batch_in"
        batch_out = tp / "batch_out"
        batch_in.mkdir()
        batch_out.mkdir()

        # Build positive alt_layout + fairness single_dep_bug + formula-based negative workbooks
        alt_path = tp / "alt_layout.xlsx"
        build_alt_layout_workbook(task, alt_path)

        dep_bug_path = tp / "single_dep_bug.xlsx"
        w_bug = load_workbook(ref)
        for idx_c, col_c in enumerate("CDEFG"):
            prev_c = "BCDEF"[idx_c]
            w_bug["Statements"][f"{col_c}9"] = f"=Inputs!$B$16*{prev_c}19+{col_c}18/2"
        w_bug.save(dep_bug_path)
        w_bug.close()

        staged_paths = {"oracle": ref, "alt_layout": alt_path, "single_dep_bug": dep_bug_path}
        is_brownfield = spec.get("task_mode") == "brownfield"
        formula_neg_modes = ["terminal", "fake_formula", "alias_hardcode", "zero_mul_cheat"] + (
            ["itm_filter"] if "B15" in spec["base"]["DCF"] else []
        )
        if is_brownfield:
            formula_neg_modes.extend(["unmodified_legacy", "stripped_sheets"])
        for mode in formula_neg_modes:
            p = tp / f"{mode}.xlsx"
            if mode == "terminal":
                w = load_workbook(ref)
                w["DCF"]["B6"] = "=B5/(1+B4)^4"
                w.save(p)
                w.close()
            elif mode == "fake_formula":
                w = load_workbook(ref)
                for cell in ("B12", "B13", "B14", "B15"):
                    if cell in spec["base"]["DCF"]:
                        w["DCF"][cell] = f"={spec['base']['DCF'][cell]}"
                w.save(p)
                w.close()
            elif mode == "alias_hardcode":
                w = load_workbook(ref)
                helper = w.create_sheet("Helper")
                for idx, cell in enumerate(("B12", "B13", "B14", "B15"), start=1):
                    if cell in spec["base"]["DCF"]:
                        helper[f"A{idx}"] = spec["base"]["DCF"][cell]
                        w["DCF"][cell] = f"=Helper!A{idx}"
                w.save(p)
                w.close()
            elif mode == "zero_mul_cheat":
                w = load_workbook(ref)
                for col_c in "CDEFG":
                    for row_r in (4, 5):
                        addr = f"{col_c}{row_r}"
                        w["Statements"][addr] = f"={spec['base']['Statements'][addr]}+0*Inputs!$B$4"
                for cell in ("B12", "B13", "B14", "B15"):
                    if cell in spec["base"]["DCF"]:
                        w["DCF"][cell] = f"={spec['base']['DCF'][cell]}+0*Inputs!$B$4"
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
            elif mode == "unmodified_legacy":
                shutil.copyfile(task / "environment/data/legacy_model.xlsx", p)
            elif mode == "stripped_sheets":
                w = load_workbook(ref)
                for sn in list(w.sheetnames):
                    if sn not in ("DCF", "Statements", "Inputs", "Ledger", "Capital"):
                        del w[sn]
                w.save(p)
                w.close()
            staged_paths[mode] = p

        # Single batch LibreOffice recalculation for all 8 formula workbooks (40 xlsx files in 1 soffice startup)
        for tag, wb_p in staged_paths.items():
            stage_for_batch(tag, wb_p, spec, batch_in)
        run_soffice_recalc(batch_in, batch_out, timeout=180)

        # On dcf-01-saas, also exercise standalone `grade(ref, spec)` without recalc_fn to verify CLI path
        good = grade(ref, spec) if task.name == "dcf-01-saas" else grade(ref, spec, recalc_fn=make_recalc_loader("oracle", batch_out))
        assert good["reward"] == 1.0 and good["pass_strict"], (task.name, good)
        result["oracle_local"] = good

        alt_res = grade(alt_path, spec, recalc_fn=make_recalc_loader("alt_layout", batch_out))
        assert alt_res["reward"] == 1.0 and alt_res["pass_strict"], (task.name, "alt_layout", alt_res)
        result["alt_layout"] = alt_res

        dep_res = grade(dep_bug_path, spec, recalc_fn=make_recalc_loader("single_dep_bug", batch_out))
        assert dep_res["dynamic_gate"] == 1.0, (task.name, "single_dep_bug gate penalized!", dep_res)
        assert dep_res["groups"]["ties"] == [20, 20], (task.name, "single_dep_bug base ties", dep_res)
        assert dep_res["groups"]["ties_shock"] == [40, 40], (task.name, "single_dep_bug shock ties", dep_res)
        sc_ok, sc_tot = dep_res["groups"]["shock_collection"]
        assert sc_ok == sc_tot, (task.name, "single_dep_bug collection delta double-penalized", dep_res)
        assert 0.55 < dep_res["reward"] < 1.0, (task.name, "single_dep_bug reward out of range", dep_res)
        result["single_dep_bug"] = dep_res

        # Build `frozen` from LibreOffice-recalculated oracle__base.xlsx and grade directly via standalone soffice
        frozen_path = tp / "frozen.xlsx"
        w_frz = load_workbook(batch_out / "oracle__base.xlsx", data_only=True)
        w_frz.save(frozen_path)
        w_frz.close()

        all_neg = [("frozen", frozen_path, None), ("missing", tp / "missing.xlsx", None)] + [
            (m, staged_paths[m], make_recalc_loader(m, batch_out)) for m in formula_neg_modes
        ]
        for mode, p, loader in all_neg:
            r = grade(p, spec, recalc_fn=loader)
            assert r["reward"] < 1.0 and not r["pass_strict"], (task.name, mode, r)
            if mode == "frozen":
                assert r["reward"] < 0.20, f"frozen hardcoding score too high: {r['reward']}"
                assert all(r["groups"]["shock_" + g][0] == 0 for g in ["operations", "collection", "discount"])
            if mode in ("fake_formula", "alias_hardcode", "zero_mul_cheat"):
                ok_f, tot_f = r["groups"]["formulas"]
                assert ok_f < tot_f, (mode, ok_f, tot_f)
            if mode == "zero_mul_cheat":
                assert r["reward"] < 0.97, f"zero_mul_cheat score too high: {r['reward']}"
            if mode in ("terminal", "itm_filter"):
                ok_v, tot_v = r["groups"]["valuation"]
                assert ok_v < tot_v
            if mode == "itm_filter":
                assert any(t[0] == "DCF!B9" for t in r["examples"]["valuation"])
            if mode == "unmodified_legacy":
                assert r["reward"] < 0.80, f"unmodified_legacy score too high: {r['reward']}"
            if mode == "stripped_sheets":
                assert r["structure_gate"] < 0.50 and r["reward"] < 0.50, (
                    f"stripped_sheets not penalized: gate={r['structure_gate']}, reward={r['reward']}"
                )
            result["negative"][mode] = r
    print(f"checked {task.name}: oracle={good['reward']} alt={alt_res['reward']} dep_bug={dep_res['reward']}", flush=True)
    return task.name, result


def export_oracle_trajectories(result: dict, out_dir: Path):
    if out_dir.exists():
        shutil.rmtree(out_dir)
    for task_name, entry in sorted(result.items()):
        tdir = out_dir / task_name
        (tdir / "verifier").mkdir(parents=True, exist_ok=True)
        (tdir / "agent").mkdir(parents=True, exist_ok=True)
        good = entry["oracle_local"]
        (tdir / "verifier/details.json").write_text(json.dumps(good, indent=2, ensure_ascii=False) + "\n")
        (tdir / "verifier/reward.txt").write_text(f"{good['reward']}\n")
        (tdir / "agent/trajectory.json").write_text(
            json.dumps(
                {
                    "model": "oracle",
                    "agent": "oracle (solution/solve.sh -> cp reference.xlsx)",
                    "task": task_name,
                    "delivered": True,
                    "turns": 1,
                    "total_elapsed_sec": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "reward": good["reward"],
                    "pass_strict": good["pass_strict"],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else root.parent / "DCFEval"
    tasks = sorted(target.glob("dcf-*"))
    assert len(tasks) >= 10, f"expected >=10 tasks in {target}, got {len(tasks)}"
    with ThreadPoolExecutor(max_workers=2) as ex:
        result = dict(ex.map(eval_task, tasks))
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else root.parent / "results/acceptance.json"
    dest.parent.mkdir(exist_ok=True, parents=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    if len(sys.argv) > 3:
        export_oracle_trajectories(result, Path(sys.argv[3]))
    for k, v in result.items():
        print(
            k,
            f"oracle={v['oracle_local']['reward']}",
            f"alt_layout={v['alt_layout']['reward']}",
            f"dep_bug={v['single_dep_bug']['reward']}(gate={v['single_dep_bug']['dynamic_gate']})",
            {m: r["reward"] for m, r in v["negative"].items()},
        )
