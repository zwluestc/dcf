"""Compile canonical cases into v4.0 Hard-Mode public Harbor tasks:
1) Zero CSV tables — all 20 tasks provide raw narrative/text financial reports & footnotes requiring data cleaning.
2) 30% (6/20) of tasks are Brownfield 15-sheet legacy Excel takeover tasks with planted formula bugs & stale assumptions.
"""
import json
import random
import shutil
import sys
from decimal import Decimal
from pathlib import Path

GL = {
    "revenue": ("4100", "Product and service billings", "Cr"),
    "cogs": ("5105", "Direct fulfilment", "Dr"),
    "opex": ("6202", "Administration and selling", "Dr"),
    "da": ("6710", "Depreciation expense", "Dr"),
    "interest": ("7102", "Interest charged", "Dr"),
    "tax": ("7900", "Current income tax", "Dr"),
    "ar": ("1210", "Trade receivables", "Dr"),
    "inv": ("1320", "Stock on hand", "Dr"),
    "ap": ("2315", "Supplier balances", "Cr"),
    "ppe": ("1520", "Net operating plant", "Dr"),
    "debt": ("2710", "Bank facility", "Cr"),
    "cash": ("1015", "Cash balances", "Dr"),
    "equity": ("3105", "Closing book equity", "Cr"),
}

PEER_POOL = [
    "Haven",
    "Aster",
    "Birch",
    "Cinder",
    "Dune",
    "Alder",
    "Beryl",
    "Cobalt",
    "Flint",
    "Linden",
    "Maple",
    "Onyx",
    "Quartz",
    "Slate",
    "Vesper",
]

EXCLUDED_PEERS = ["Kestrel (Distressed)", "Marrow (Pre-Revenue)", "Tarmac (LBO Private)"]

# 30% (6/20) Brownfield 15-sheet legacy takeover tasks (3 Wave 1 + 3 Wave 2, covering all 4 quadrants)
BROWNFIELD_TASKS = {
    "dcf-02-foundry",
    "dcf-05-fleet",
    "dcf-08-retail",
    "dcf-11-saas",
    "dcf-14-storage",
    "dcf-17-mine",
}

LEGACY_SHEETS = [
    "Cover",
    "Inputs",
    "Statements",
    "DCF",
    "Ledger",
    "Capital",
    "Drivers",
    "Revenue_Build",
    "Cost_OpEx",
    "Working_Capital",
    "PPE_Capex",
    "Debt_Schedule",
    "Peer_Comps",
    "TSM_Dilution",
    "Checks_Audit",
]


def D(x):
    return Decimal(str(x))


def fmt_comma(val: Decimal) -> str:
    """Format Decimal with thousands commas while preserving exact precision."""
    s = format(val.normalize(), "f")
    if "." in s:
        whole, frac = s.split(".", 1)
        return f"{int(whole):,}.{frac}"
    return f"{int(s):,}"


def fmt_plain(val: Decimal) -> str:
    return format(val.normalize(), "f")


def sources(d, p: Path):
    """Generate 3 raw unstructured/semi-structured financial filings (ZERO CSV tables)."""
    p.mkdir(parents=True, exist_ok=True)
    s = d["scalar"]
    series = d["series"]
    rng = random.Random(int(d.get("seed", 1017)) + 9973)

    curr_frac = D(rng.choice(["0.20", "0.25", "0.30", "0.35"]))
    noncurr_frac = D("1") - curr_frac
    void_amt = D(rng.choice([2, 3, 4, 5]))
    undrawn_revolver = rng.choice([15, 20, 25, 30])

    # Dynamic TSM option tranches
    market = D(rng.choice([16, 20, 24, 25, 30, 32, 40]))
    n_itm = rng.choice([1, 2])
    tranches = []
    increment = D(0)
    used_strikes = set()
    for _ in range(n_itm):
        k_mult = rng.randint(1, 3)
        count_shares = int(market) * 10000 * k_mult
        strike = rng.randint(int(market * D("0.40")), int(market * D("0.80")))
        while strike in used_strikes:
            strike += 1
        used_strikes.add(strike)
        tranches.append((count_shares, strike))
        increment += D(count_shares) * (D(1) - D(strike) / market) / D(1000000)

    otm_count = rng.randrange(250000, 650000, 50000)
    otm_strike = int(market) + rng.randint(4, 12)
    tranches.append((otm_count, otm_strike))
    rng.shuffle(tranches)

    basic = D(s["shares"]) - increment
    assert basic > D(1), f"invalid basic shares {basic}"
    basic_str = fmt_comma(basic * D(1000000))
    tranche_lines = [
        f"    - Tranche {idx + 1}: {cnt:,} vested/unvested options exercisable at EUR {stk} per ordinary share"
        for idx, (cnt, stk) in enumerate(tranches)
    ]

    # -------------------------------------------------------------------------
    # Exhibit 1: annual_report_fy2025.txt (Full FY2025 Financial Report & Notes)
    # -------------------------------------------------------------------------
    company = d.get("company", d["title"])
    report_lines = [
        "=" * 84,
        f"ANNUAL FINANCIAL REPORT & STATUTORY FOOTNOTES — {company.upper()}",
        "FISCAL YEAR ENDED 31 DECEMBER 2025 (SYNTHETIC FILING FOR VALUATION AUDIT)",
        "=" * 84,
        "",
        "NOTE 1 — BASIS OF CONSOLIDATION, REPORTING SCALES AND CLEANING RULES",
        "The Group operates two wholly owned reporting divisions: North Division and South",
        "Division. There are no intercompany eliminations. All figures below are unsigned",
        "magnitudes accompanied by their normal accounting side (Dr / Cr).",
        "  * North Division statutory ledger extracts are stated in EUR THOUSANDS (EUR '000).",
        "  * South Division statutory ledger extracts are stated in whole EUR UNITS (EUR 1).",
        "  * Only rows stamped [FY2025 | POSTED] represent audited FY2025 balances/flows.",
        "  * Rows marked [VOID], [REVERSED], or [FY2024 COMPARATIVE] are disclosed solely",
        "    for audit trail completeness and MUST be excluded from FY2025 consolidation.",
        "  * Income-statement accounts (4100, 5105, 6202, 6710, 7102, 7900) are full-year",
        "    FY2025 flows; balance-sheet accounts are 31 Dec 2025 closing balances.",
        "  * Closing book equity (3105) ALREADY incorporates FY2025 net income; do NOT",
        "    double-count FY2025 earnings into closing equity.",
        "",
    ]

    for site in ["North", "South"]:
        unit_label = "EUR THOUSANDS" if site == "North" else "EUR UNITS"
        factor = D(1000 if site == "North" else 1000000)
        report_lines.append("-" * 84)
        report_lines.append(f"SCHEDULE 2.{1 if site == 'North' else 2} — {site.upper()} DIVISION GENERAL LEDGER EXTRACT ({unit_label})")
        report_lines.append("-" * 84)
        # Distractor FY2024 comparative line at top
        comp_rev = (D(rng.randint(80, 140)) * factor)
        report_lines.append(
            f"  [FY2024 COMPARATIVE] | Acct 4100 | Product and service billings           | Cr | {fmt_comma(comp_rev)} {unit_label}"
        )
        for e in d["ledger"]:
            if e["site"] != site:
                continue
            code, label, side = GL[e["account"]]
            v = D(e["amount"]) * factor
            parts = (
                [(code, label, v)]
                if e["account"] != "debt"
                else [
                    ("2112", "Bank facility due within 12 months", v * curr_frac),
                    ("2710", "Bank facility due after 12 months", v * noncurr_frac),
                ]
            )
            for c_code, c_label, a in parts:
                report_lines.append(
                    f"  [FY2025 | POSTED]    | Acct {c_code} | {c_label:<36} | {side} | {fmt_comma(a)} {unit_label}"
                )
        # Distractor VOID line
        report_lines.append(
            f"  [FY2025 | VOID]      | Acct 4100 | Product and service billings (void)    | Cr | {fmt_comma(void_amt * factor)} {unit_label}"
        )
        report_lines.append("")

    report_lines.extend([
        "-" * 84,
        "NOTE 8 — BORROWINGS, CREDIT FACILITIES AND OFF-BALANCE-SHEET COMMITMENTS",
        "-" * 84,
        "Both Bank Facility account 2112 (current portion due within 12 months) and account",
        "2710 (non-current portion due after 12 months) are interest-bearing term debt and",
        "must be summed into FY2025 closing Term Debt. Account 2112 is NOT supplier credit.",
        f"[OFF-BALANCE-SHEET MEMO] The Group also maintains an undrawn committed revolving",
        f"credit facility of EUR {undrawn_revolver}.0 million maturing in 2029 (EUR 0.0 drawn at close;",
        "do NOT include undrawn commitments in balance-sheet debt or EV bridge).",
        "",
        "-" * 84,
        "NOTE 11 — SHARE CAPITAL AND EMPLOYEE OPTION TRANCHES (TREASURY STOCK METHOD)",
        "-" * 84,
        f"As of 31 December 2025, issued and outstanding basic ordinary shares totaled",
        f"{basic_str} shares. For treasury stock method (TSM) dilution testing only, the",
        f"Board-approved reference market quote is EUR {fmt_plain(market)} per ordinary share.",
        "Each option converts into one ordinary share. Include ONLY in-the-money (ITM)",
        "incremental shares under TSM (ignore out-of-the-money tranches; do not add",
        "hypothetical option exercise proceeds again in the EV-to-Equity bridge):",
        *tranche_lines,
        "",
    ])
    (p / "annual_report_fy2025.txt").write_text("\n".join(report_lines) + "\n")

    # -------------------------------------------------------------------------
    # Exhibit 2: management_guidance_fy26_30.md (Replaces ops memo + budget CSV)
    # -------------------------------------------------------------------------
    # Create a clearly superseded Q3 draft distractor block to test cleaning discipline
    draft_cogs = round(float(series["cogs_pct"][0]) * 100 + 3.5, 2)
    draft_dso = int(round(float(series["dso"][0]))) + 9
    guidance_lines = [
        f"# Management Operating & Financial Guidance | {company} (FY2026–FY2030)",
        "",
        "## 1. Superseded Q3 Preliminary Draft [SUPERSEDED — DO NOT USE]",
        f"> Preliminary Q3 internal draft assumed cash COGS of {draft_cogs}% of sales and",
        f"> collection period of {draft_dso} days with flat pricing. That draft was formally",
        "> superseded by the Board-approved FY2026–FY2030 guidance in Sections 2 and 3 below.",
        "",
        "## 2. Approved Operating Contract & Volume Recognition Policy",
        f"Audited FY2025 closing {d['unit']}: **{s['opening_units']}**. Fractional activity is permitted.",
        d["rule"],
        "",
        "## 3. Approved FY2026–FY2030 Year-by-Year Operating & Financial Budget",
        "All percentages below are stated in percentage points (e.g., 42.5% = 0.425 decimal),",
        "while operating ratios (A/B/C) are stated directly in the contract basis. Fixed",
        "operating expenses (excluding D&A) and scheduled debt principal amortization are",
        "disclosed in **EUR thousands (EUR '000)**; unit price is in **whole EUR per unit**.",
        "",
    ]
    for j, y in enumerate(range(2026, 2031)):
        price_eur = fmt_comma(D(series["unit_price"][j]) * D(1000000))
        cogs_p = fmt_plain(D(series["cogs_pct"][j]) * D(100))
        opex_k = fmt_comma(D(series["opex_fixed"][j]) * D(1000))
        capex_p = fmt_plain(D(series["capex_pct"][j]) * D(100))
        dso_d = fmt_plain(D(series["dso"][j]))
        dio_d = fmt_plain(D(series["dio"][j]))
        dpo_d = fmt_plain(D(series["dpo"][j]))
        repay_k = fmt_comma(D(series["repay"][j]) * D(1000))
        guidance_lines.extend([
            f"### FY{y} Approved Plan",
            f"- **Operating Drivers**: {d['driver_labels']['A']} (A) = {series['A'][j]}; "
            f"{d['driver_labels']['B']} (B) = {series['B'][j]}; "
            f"{d['driver_labels']['C']} (C) = {series['C'][j]}; "
            f"full annual unit price = EUR {price_eur} per revenue-equivalent unit.",
            f"- **Cost & Investment Budget**: cash COGS = {cogs_p}% of sales; "
            f"fixed cash operating expenses (ex-D&A) = EUR {opex_k} thousand; "
            f"capital expenditure = {capex_p}% of sales.",
            f"- **Working Capital & Debt Amortization**: collection days (DSO) = {dso_d} days; "
            f"inventory days (DIO) = {dio_d} days; payables days (DPO) = {dpo_d} days; "
            f"scheduled term-debt principal repayment = EUR {repay_k} thousand.",
            "",
        ])
    (p / "management_guidance_fy26_30.md").write_text("\n".join(guidance_lines) + "\n")

    # -------------------------------------------------------------------------
    # Exhibit 3: broker_comps_and_treasury_memo.md (Replaces peer CSV + notes)
    # -------------------------------------------------------------------------
    t = D(s["tax_rate"])
    dw = D(s["debt_weight"])
    asset_beta = D(s["beta"]) / (D(1) + (D(1) - t) * dw / (D(1) - dw))

    n_peers = rng.choice([3, 5])
    peer_names = rng.sample(PEER_POOL, n_peers)
    if n_peers == 3:
        deltas = [D(f"-0.{rng.randint(10, 18)}"), D("0"), D(f"0.{rng.randint(10, 19)}")]
    else:
        deltas = [
            D(f"-0.{rng.randint(14, 22)}"),
            D(f"-0.{rng.randint(5, 11):02d}"),
            D("0"),
            D(f"0.{rng.randint(5, 11):02d}"),
            D(f"0.{rng.randint(14, 22)}"),
        ]
    rng.shuffle(deltas)
    peer_entries = []
    for name, delta in zip(peer_names, deltas):
        lev = D(str(round(rng.uniform(0.18, 0.68), 2)))
        ptax = D(str(rng.randint(18, 29))) / D(100)
        obs_beta = (asset_beta + delta) * (D(1) + (D(1) - ptax) * lev)
        peer_entries.append((False, name, obs_beta, lev, ptax * D(100)))

    # Add 1 excluded distressed/non-comparable distractor peer (must be cleaned out!)
    ex_name = rng.choice(EXCLUDED_PEERS)
    ex_beta = D(str(round(rng.uniform(2.15, 2.85), 4)))
    ex_lev = D(str(round(rng.uniform(1.40, 2.20), 2)))
    ex_tax = D("25")
    peer_entries.append((True, ex_name, ex_beta, ex_lev, ex_tax))
    rng.shuffle(peer_entries)

    peer_bullets = []
    for is_excl, name, obs_beta, lev, ptax_pct in peer_entries:
        tag = "[EXCLUDED — DISTRESSED / NON-COMPARABLE]" if is_excl else "[APPROVED PEER]"
        peer_bullets.append(
            f"- {tag} **{name}**: observed equity beta = {fmt_plain(obs_beta)}, "
            f"net debt / equity = {fmt_plain(lev)}x, statutory tax rate = {fmt_plain(ptax_pct)}%."
        )

    memo_text = f"""# Investment Banking Comparable Companies & CFO Valuation Sign-Off

## 1. Capital Structure & Cost of Capital Parameters (FY2025 Close)
- Target capital structure: debt represents **{fmt_plain(dw * D(100))}%** of total invested capital (target D/E = debt_weight / (1 - debt_weight)).
- Risk-free rate: **{fmt_plain(D(s['risk_free']) * D(10000))} bp**; equity risk premium (ERP): **{fmt_plain(D(s['erp']) * D(10000))} bp**; pre-tax cost of debt: **{fmt_plain(D(s['debt_cost']) * D(10000))} bp**.
- Statutory corporate tax rate: **{fmt_plain(t * D(100))}%**.

## 2. Comparable Companies Beta Panel
Unlever each **[APPROVED PEER]** observed equity beta via the Hamada formula with zero debt beta (`beta_U = beta_L / (1 + (1 - tax_peer) * D/E_peer)`), exclude any peer tagged **[EXCLUDED]**, take the **median** unlevered asset beta, and relever using the target D/E and statutory corporate tax rate for CAPM.

{chr(10).join(peer_bullets)}

## 3. CFO Valuation & Accounting Policy Sign-Off
- Editable base-case forecast price multiplier: **{s['price_multiplier']}**; editable additive shift to budget collection days (DSO shift): **{s['dso_shift']}** days.
- Annual net PP&E depreciation rate: **{fmt_plain(D(s['dep_rate']) * D(100))}%** applied to opening net PP&E plus half of current-year capex.
- Discounting convention: **{d['timing']}** for the five annual forecast FCFFs (0.5–4.5 for midyear; 1–5 for year-end), and **five full years** for the terminal value at FY2030 close.
- Terminal value method: **{d['terminal']}** (going-concern perpetuity growth mandate = **{fmt_plain(D(s['g']) * D(100))}%**; exit EBITDA multiple assumption = **{s['exit_multiple']}x** — apply only the parameter for the assigned terminal method).
- No terminal premium, minority interest, or non-operating adjustments.
"""
    (p / "broker_comps_and_treasury_memo.md").write_text(memo_text)

    return float(asset_beta), float(increment)


def public_instruction(d, original, brownfield=False):
    out = original[original.index("## Delivery contract") :]
    policy = original[original.index("Cash COGS is") : original.index("## Valuation")]

    if brownfield:
        intro = (
            f"# {d['title']} | FY2025 Brownfield Legacy Model Takeover & Audit\n\n"
            "**MODE: BROWNFIELD TAKEOVER (15-SHEET LEGACY WORKBOOK AUDIT & REPAIR)**\n\n"
            "You are taking over an existing **15-sheet** corporate-finance Excel model at `/work/data/legacy_model.xlsx`, "
            "originally built from an outdated preliminary draft. Alongside it, `/work/data/` contains three raw, unstructured "
            "FY2025 statutory financial filings (`annual_report_fy2025.txt`, `management_guidance_fy26_30.md`, and "
            "`broker_comps_and_treasury_memo.md` — **no clean CSV tables are provided**).\n\n"
            "Your mandate:\n"
            "1. **Clean and reconcile raw filings**: Parse the three raw filings, exclude VOID / FY2024 comparative / superseded Q3 draft / excluded distressed peer lines, and normalize mixed units (`EUR`, `EUR thousands`, `EUR millions`, `bp`, `%`).\n"
            "2. **Audit and repair `/work/data/legacy_model.xlsx` WITHOUT breaking its 15-sheet structure**: The legacy workbook contains stale/conflicting assumptions in `Inputs` AND hidden financial-modeling formula bugs (e.g., discounting period, FCFF working-capital sign, EV-to-Equity bridge, peer beta aggregation, and/or TSM option filtering). "
            "You MUST preserve all 15 existing worksheet names (`" + "`, `".join(LEGACY_SHEETS) + "`), fix every formula bug and stale assumption in place, verify all accounting identities and audit checks, and save the repaired self-contained workbook to `/work/output.xlsx`.\n"
            "Deleting legacy sheets or rebuilding a stripped-down workbook from scratch violates the structural preservation requirement and will be penalized.\n\n"
        )
    else:
        intro = (
            f"# {d['title']} | FY2025 Valuation from Raw Financial Filings\n\n"
            "**MODE: GREENFIELD FROM RAW FILINGS (DATA CLEANING + FULL 3-STATEMENT DCF)**\n\n"
            "Start from a blank workbook. Read and clean the three raw unstructured financial filings in `/work/data/` "
            "(`annual_report_fy2025.txt`, `management_guidance_fy26_30.md`, and `broker_comps_and_treasury_memo.md` — "
            "**no pre-cleaned CSV tables are provided**). They are original synthetic filings, not a public company's filings. "
            "You must filter out VOID / FY2024 comparative / superseded Q3 draft / excluded distressed peer entries, normalize "
            "mixed reporting units (`EUR`, `EUR thousands`, `EUR millions`, `bp`, `%`), and deliver a self-contained, "
            "formula-driven `/work/output.xlsx`.\n\n"
        )

    return (
        intro
        + "Preserve full precision. Inputs and outputs are in EUR millions and millions of shares unless a source explicitly uses different units. "
        "Price per share is in EUR. The required price is DCF intrinsic value, not the market quote.\n\n"
        "Reconstruct FY2025 actuals (income statement and closing balance sheet; FY2025 cash flow statement is NOT required) and forecast FY2026–2030 IS, BS and CF. "
        "No other balances, tax deferrals, distributions, funding, issuance or transactions. "
        "Revenue-equivalent billable units express full-price equivalent annual volume: deduct expected warranty credits (returns), ADD immediate upfront license fees recognised in full (license), "
        "and apply minimum billing guarantees (royalty), strictly following `management_guidance_fy26_30.md`. "
        "Forecast revenue = those revenue-equivalent billable units times full annual unit price (converted to EUR millions) times the editable `price_multiplier`.\n\n"
        + policy
        + "CAPM/WACC use the signed treasury policy. Discount each annual FCFF at year-end (1–5) or midyear (0.5–4.5) as signed. "
        "Terminal at FY2030 close; perpetuity grows last FCFF by g, exit method uses final EBITDA. "
        "Equity value is EV plus FY2025 cash less FY2025 debt. Divide by TSM diluted shares.\n\n"
        + out
        + "\nAdditional required outputs (included in the 155 graded live-formula cells): "
        "DCF!B12 = relevered equity beta; DCF!B13 = diluted shares (millions); DCF!B14 = median unlevered peer beta; DCF!B15 = TSM incremental shares (millions). "
        "All four must resolve to live upstream calculation formulas. Their base values and formulas are graded as part of valuation.\n"
    )


def build(baseline: Path, out: Path):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    for src in sorted(baseline.glob("dcf-*")):
        dst = out / src.name
        d = json.loads((src / "environment/data/case.json").read_text())
        is_brownfield = src.name in BROWNFIELD_TASKS
        dst.mkdir(parents=True, exist_ok=True)
        asset, increment = sources(d, dst / "environment/data")
        shutil.copy(src / "environment/Dockerfile", dst / "environment/Dockerfile")
        if len(list((dst / "environment/data").iterdir())) != 3:
            raise ValueError(f"Expected 3 raw filing exhibits in {dst / 'environment/data'}")
        (dst / "instruction.md").write_text(
            public_instruction(d, (src / "instruction.md").read_text(), brownfield=is_brownfield)
        )
        toml_text = (src / "task.toml").read_text()
        if is_brownfield:
            toml_text = toml_text.replace(
                "From-blank integrated 3-statement forecast and FCFF valuation:",
                "Brownfield 15-sheet legacy Excel takeover & audit (raw filings):",
            )
        else:
            toml_text = toml_text.replace(
                "From-blank integrated 3-statement forecast and FCFF valuation:",
                "Greenfield raw-filing data cleaning & 3-statement FCFF valuation:",
            )
        (dst / "task.toml").write_text(toml_text)
        for sub in ("tests", "solution"):
            shutil.copytree(src / sub, dst / sub, dirs_exist_ok=True)
        d_meta = dict(d, task_mode="brownfield" if is_brownfield else "greenfield")
        (dst / "solution/canonical.json").write_text(json.dumps(d_meta, ensure_ascii=False, indent=2) + "\n")
        p = dst / "tests/answers.json"
        a = json.loads(p.read_text())
        s = d["scalar"]
        extra = {"B12": s["beta"], "B13": s["shares"], "B14": asset, "B15": increment}
        for y in [a["base"]] + [v["expected"] for v in a["shocks"].values()]:
            y["DCF"].update(extra)
        a["task_mode"] = "brownfield" if is_brownfield else "greenfield"
        if is_brownfield:
            a["required_sheets"] = list(LEGACY_SHEETS)
        p.write_text(json.dumps(a, indent=2) + "\n")


if __name__ == "__main__":
    build(
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("DCFEvalStructured"),
        Path(sys.argv[2]) if len(sys.argv) > 2 else Path("DCFEval"),
    )
