"""Reconstruct canonical inputs strictly from the 3 raw unstructured financial filings (zero CSVs)
and verify exact mathematical equivalence against tests/answers.json.
"""
import json
import math
import re
import sys
from pathlib import Path
from statistics import median

from model import calculate
from forward import forward

CHART = dict(
    zip(
        "4100 5105 6202 6710 7102 7900 1210 1320 2315 1520 2112 2710 1015 3105".split(),
        "revenue cogs opex da interest tax ar inv ap ppe debt debt cash equity".split(),
    )
)

NUM_RE = r"([\d,]+(?:\.\d+)?)"


def num(s: str) -> float:
    return float(s.replace(",", "").rstrip("."))


def get_num(pattern: str, text: str) -> float:
    m = re.search(pattern, text)
    if not m:
        raise ValueError(f"Pattern not found: {pattern}")
    return num(m.group(1))


def parse_filings(p: Path):
    """Parse and clean the 3 raw financial filings into structured inputs (no CSVs)."""
    ar = (p / "annual_report_fy2025.txt").read_text()
    mg = (p / "management_guidance_fy26_30.md").read_text()
    bm = (p / "broker_comps_and_treasury_memo.md").read_text()

    # Strip Superseded Q3 Preliminary Draft section from management guidance before parsing
    mg_clean = mg[mg.index("## 2. Approved Operating Contract") :]

    # 1. Scalars from broker_comps_and_treasury_memo.md & management_guidance_fy26_30.md
    s = dict(
        opening_units=get_num(r"Audited FY2025 closing .+?:\s*\*\*" + NUM_RE + r"\*\*", mg_clean),
        price_multiplier=get_num(r"price multiplier:\s*\*\*" + NUM_RE + r"\*\*", bm),
        dso_shift=get_num(r"DSO shift\):\s*\*\*" + NUM_RE + r"\*\*", bm),
        dep_rate=get_num(r"depreciation rate:\s*\*\*" + NUM_RE + r"%\*\*", bm) / 100.0,
        g=get_num(r"growth mandate =\s*\*\*" + NUM_RE + r"%\*\*", bm) / 100.0,
        exit_multiple=get_num(r"exit EBITDA multiple assumption =\s*\*\*" + NUM_RE + r"x\*\*", bm),
        tax_rate=get_num(r"Statutory corporate tax rate:\s*\*\*" + NUM_RE + r"%\*\*", bm) / 100.0,
        debt_weight=get_num(r"debt represents\s*\*\*" + NUM_RE + r"%\*\*", bm) / 100.0,
        debt_cost=get_num(r"pre-tax cost of debt:\s*\*\*" + NUM_RE + r"\s*bp\*\*", bm) / 10000.0,
        risk_free=get_num(r"Risk-free rate:\s*\*\*" + NUM_RE + r"\s*bp\*\*", bm) / 10000.0,
        erp=get_num(r"equity risk premium \(ERP\):\s*\*\*" + NUM_RE + r"\s*bp\*\*", bm) / 10000.0,
    )

    # 2. Comparable companies (APPROVED PEER only; drop EXCLUDED distressed peers)
    peer_rows = []
    for line in bm.splitlines():
        if not line.lstrip().startswith("- [APPROVED PEER]"):
            continue
        m = re.search(
            r"\[APPROVED PEER\]\s+\*\*(.+?)\*\*:\s*observed equity beta\s*=\s*"
            + NUM_RE
            + r",\s*net debt / equity\s*=\s*"
            + NUM_RE
            + r"x,\s*statutory tax rate\s*=\s*"
            + NUM_RE
            + r"%",
            line,
        )
        if not m:
            raise ValueError(f"Failed to parse peer line: {line}")
        peer_rows.append(
            {
                "peer": m.group(1).strip(),
                "observed_equity_beta": num(m.group(2)),
                "net_debt_to_equity_x": num(m.group(3)),
                "statutory_tax_pct": num(m.group(4)),
            }
        )
    if not peer_rows:
        raise ValueError("No approved peers parsed from broker_comps_and_treasury_memo.md")

    asset = median(
        r["observed_equity_beta"] / (1.0 + (1.0 - r["statutory_tax_pct"] / 100.0) * r["net_debt_to_equity_x"])
        for r in peer_rows
    )
    s["beta"] = asset * (1.0 + (1.0 - s["tax_rate"]) * s["debt_weight"] / (1.0 - s["debt_weight"]))

    # 3. Note 11: Basic shares & TSM option tranches from annual_report_fy2025.txt
    basic_shares = get_num(r"basic ordinary shares totaled\s+" + NUM_RE + r"\s+shares", ar)
    mkt_quote = get_num(r"reference market quote is EUR\s+" + NUM_RE + r"\s+per ordinary share", ar)
    opt_rows = [
        (num(cnt), num(stk))
        for cnt, stk in re.findall(
            r"Tranche \d+:\s*" + NUM_RE + r"\s+vested/unvested options exercisable at EUR\s+" + NUM_RE, ar
        )
    ]
    dilution = sum(cnt * max(0.0, 1.0 - stk / mkt_quote) for cnt, stk in opt_rows) / 1e6
    s["shares"] = basic_shares / 1e6 + dilution

    # 4. FY2026-2030 year-by-year approved operating & budget guidance
    series = {
        k: []
        for k in ("A", "B", "C", "unit_price", "cogs_pct", "opex_fixed", "capex_pct", "dso", "dio", "dpo", "repay")
    }
    driver_labels = {}
    blocks = re.split(r"(?=### FY20\d\d Approved Plan)", mg_clean)
    fy_blocks = [b for b in blocks if b.startswith("### FY20")]
    if len(fy_blocks) != 5:
        raise ValueError(f"Expected 5 FY blocks in guidance, got {len(fy_blocks)}")
    for block in fy_blocks:
        for key in "ABC":
            series[key].append(get_num(r"\(" + key + r"\)\s*=\s*" + NUM_RE, block))
            if key not in driver_labels:
                m_lbl = re.search(r"(?:Drivers\*\*:|;)\s*([^:;]+?)\s*\(" + key + r"\)\s*=", block)
                if m_lbl:
                    driver_labels[key] = m_lbl.group(1).strip()
        series["unit_price"].append(get_num(r"full annual unit price\s*=\s*EUR\s+" + NUM_RE, block) / 1e6)
        series["cogs_pct"].append(get_num(r"cash COGS\s*=\s*" + NUM_RE + r"%\s+of sales", block) / 100.0)
        series["opex_fixed"].append(get_num(r"fixed cash operating expenses \(ex-D&A\)\s*=\s*EUR\s+" + NUM_RE + r"\s+thousand", block) / 1000.0)
        series["capex_pct"].append(get_num(r"capital expenditure\s*=\s*" + NUM_RE + r"%\s+of sales", block) / 100.0)
        series["dso"].append(get_num(r"collection days \(DSO\)\s*=\s*" + NUM_RE + r"\s+days", block))
        series["dio"].append(get_num(r"inventory days \(DIO\)\s*=\s*" + NUM_RE + r"\s+days", block))
        series["dpo"].append(get_num(r"payables days \(DPO\)\s*=\s*" + NUM_RE + r"\s+days", block))
        series["repay"].append(get_num(r"principal repayment\s*=\s*EUR\s+" + NUM_RE + r"\s+thousand", block) / 1000.0)

    # 5. FY2025 POSTED divisional ledger rows from annual_report_fy2025.txt (drop VOID & FY2024 COMPARATIVE)
    ledger_rows = []
    cur_site = None
    for line in ar.splitlines():
        if "NORTH DIVISION GENERAL LEDGER EXTRACT" in line:
            cur_site = "North"
            continue
        if "SOUTH DIVISION GENERAL LEDGER EXTRACT" in line:
            cur_site = "South"
            continue
        if cur_site is None or not line.lstrip().startswith("[FY2025 | POSTED]"):
            continue
        m = re.search(
            r"\[FY2025 \| POSTED\]\s*\|\s*Acct\s+(\d{4})\s*\|\s*(.+?)\s*\|\s*(Dr|Cr)\s*\|\s*"
            + NUM_RE
            + r"\s+(EUR THOUSANDS|EUR UNITS)",
            line,
        )
        if not m:
            raise ValueError(f"Failed to parse posted ledger line: {line}")
        acct, caption, side, raw_amt, unit_str = m.group(1), m.group(2).strip(), m.group(3), num(m.group(4)), m.group(5)
        scale = 1000 if unit_str == "EUR THOUSANDS" else 1000000
        ledger_rows.append(
            {
                "site": cur_site,
                "account_code": acct,
                "account": CHART[acct],
                "caption": caption,
                "side": side,
                "native_amount": raw_amt,
                "scale": scale,
                "amount": raw_amt / scale,
            }
        )

    terminal = re.search(r"Terminal value method:\s*\*\*(.+?)\*\*", bm).group(1).strip()
    timing = re.search(r"Discounting convention:\s*\*\*(\S+?)\*\*", bm).group(1).strip()

    case = dict(
        slug=p.parent.parent.name.split("-", 2)[2],
        ledger=[{"site": r["site"], "account": r["account"], "amount": r["amount"]} for r in ledger_rows],
        series=series,
        scalar=s,
        driver_labels=driver_labels,
        terminal=terminal,
        timing=timing,
    )
    return {
        "case": case,
        "asset_beta": asset,
        "dilution": dilution,
        "ledger_rows": ledger_rows,
        "peer_rows": peer_rows,
        "basic_shares": basic_shares,
        "market_quote": mkt_quote,
        "option_tranches": opt_rows,
    }


def reconstruct(p: Path):
    parsed = parse_filings(p)
    return parsed["case"], parsed["asset_beta"], parsed["dilution"]


def audit(task: Path):
    case, asset, inc = reconstruct(task / "environment/data")
    root = task / "tests"
    gold = json.loads((root / "answers.json").read_text())
    canon = json.loads((task / "solution/canonical.json").read_text())
    eq = lambda a, b: math.isclose(a, b, abs_tol=1e-8, rel_tol=1e-10)

    for k, v in canon["scalar"].items():
        assert eq(case["scalar"][k], v), (task, k, case["scalar"][k], v)
    for k, v in canon["series"].items():
        assert len(case["series"][k]) == len(v) and all(eq(a, b) for a, b in zip(case["series"][k], v)), (task, k)

    n = 0
    for mode, target, override in [("base", gold["base"], {})] + [
        (key, data["expected"], {{"B4": "price_multiplier", "B5": "dso_shift", "B6": "risk_free"}[cell]: v for cell, v in data["changes"].items()})
        for key, data in gold["shocks"].items()
    ]:
        computed = calculate(case, override)
        computed["DCF"].update(B12=case["scalar"]["beta"], B13=case["scalar"]["shares"], B14=asset, B15=inc)
        for sh, values in target.items():
            for cell, v in values.items():
                assert eq(computed[sh][cell], v), (task, mode, sh, cell, computed[sh][cell], v)
                n += 1

    (task / "solution/reference_financials.json").write_text(json.dumps(forward(canon), ensure_ascii=False, indent=2) + "\n")
    return n


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("DCFEval")
    res = {p.name: audit(p) for p in sorted(root.glob("dcf-*"))}
    print(json.dumps(res, indent=2))
