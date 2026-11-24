"""Compile canonical cases into realistic 7-exhibit public Harbor tasks with dynamic peers & TSM options."""
import csv
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


def writecsv(p, head, rows):
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)


def D(x):
    return Decimal(str(x))


def sources(d, p):
    p.mkdir(parents=True, exist_ok=True)
    s = d["scalar"]
    series = d["series"]
    rng = random.Random(int(d.get("seed", 1017)) + 9973)

    # Current vs noncurrent debt split ratio varies per task (always sums to 1.0 exactly)
    curr_frac = D(rng.choice(["0.20", "0.25", "0.30", "0.35"]))
    noncurr_frac = D("1") - curr_frac
    void_amt = D(rng.choice([2, 3, 4, 5]))

    for site in ["North", "South"]:
        factor = D(1000 if site == "North" else 1000000)
        rs = []
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
            for code, label, a in parts:
                rs.append([2025, "POSTED", code, label, side, a])
        rs.append([2025, "VOID", "4100", "Product and service billings", "Cr", void_amt * factor])
        writecsv(
            p / f"{site.lower()}_close.csv",
            ["year", "status", "account", "local_caption", "normal_side", "amount_EUR_" + ("thousands" if site == "North" else "units")],
            rs,
        )

    terms = [
        "# Operations committee | approved forecast",
        "",
        f"FY2025 closing {d['unit']}: {s['opening_units']}. Fractional activity is permitted. The following volumes, ratios and recognition policy supersede draft operational budgets.",
        d["rule"],
        "",
    ]
    for j, y in enumerate(range(2026, 2031)):
        price_eur = format((D(series["unit_price"][j]) * 1000000).normalize(), "f")
        terms.append(
            f"FY{y}: {d['driver_labels']['A']} (A) = {series['A'][j]}; "
            f"{d['driver_labels']['B']} (B) = {series['B'][j]}; "
            f"{d['driver_labels']['C']} (C) = {series['C'][j]}; "
            f"full annual price per revenue-equivalent unit = EUR {price_eur} per unit"
        )
    (p / "operations_memo.md").write_text("\n".join(terms) + "\n")

    keys = ("cogs_pct", "opex_fixed", "capex_pct", "dso", "dio", "dpo", "repay")
    writecsv(
        p / "finance_budget.csv",
        [
            "fy",
            "cash_cost_pct_of_sales",
            "fixed_expense_EUR_thousands",
            "investment_pct_of_sales",
            "collection_days",
            "stock_days",
            "supplier_days",
            "debt_amort_EUR_thousands",
        ],
        [
            [y, *[D(series[k][j]) * f for k, f in zip(keys, (100, 1000, 100, 1, 1, 1, 1000))]]
            for j, y in enumerate(range(2026, 2031))
        ],
    )

    # Dynamic peer set (3 or 5 peers, exact median asset beta == asset_beta)
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
    peers = []
    for name, delta in zip(peer_names, deltas):
        lev = D(str(round(rng.uniform(0.18, 0.68), 2)))
        ptax = D(str(rng.randint(18, 29))) / D(100)
        obs_beta = (asset_beta + delta) * (D(1) + (D(1) - ptax) * lev)
        peers.append([name, obs_beta, lev, ptax * 100])
    writecsv(p / "peer_set.csv", ["peer", "observed_equity_beta", "net_debt_to_equity_x", "statutory_tax_pct"], peers)

    # Dynamic TSM option tranches: exact decimal arithmetic, >=1 ITM and >=1 OTM tranche
    market = D(rng.choice([16, 20, 24, 25, 30, 32, 40]))
    n_itm = rng.choice([1, 2])
    tranches = []
    increment = D(0)
    used_strikes = set()
    for _ in range(n_itm):
        k_mult = rng.randint(1, 3)
        count_shares = int(market) * 10000 * k_mult  # guarantees exact count / market
        strike = rng.randint(int(market * D("0.40")), int(market * D("0.80")))
        while strike in used_strikes:
            strike += 1
        used_strikes.add(strike)
        tranches.append((count_shares, strike))
        increment += D(count_shares) * (D(1) - D(strike) / market) / D(1000000)

    # Always include 1 OTM tranche (strike > market) to test ITM filtering
    otm_count = rng.randrange(250000, 650000, 50000)
    otm_strike = int(market) + rng.randint(4, 12)
    tranches.append((otm_count, otm_strike))
    rng.shuffle(tranches)

    basic = D(s["shares"]) - increment
    assert basic > D(1), f"invalid basic shares {basic}"
    tranche_text = "; ".join(f"{cnt} options at EUR {stk}" for cnt, stk in tranches)

    basic_str = format((basic * D(1000000)).normalize(), "f")
    (p / "treasury_note.md").write_text(
        f"""# Treasury and equity note | FY2025 close
Capital structure target: debt is {format((dw * 100).normalize(), "f")}% of total invested capital. Risk-free rate {format((D(s['risk_free']) * 10000).normalize(), "f")} bp; equity risk premium {format((D(s['erp']) * 10000).normalize(), "f")} bp; pre-tax debt rate {format((D(s['debt_cost']) * 10000).normalize(), "f")} bp. Corporate tax {format((t * 100).normalize(), "f")}%. Peer-specific tax and D/E are in peer_set.csv. Unlever each observed beta using Hamada with zero debt beta, select the median asset beta, then relever with the target D/E and corporate tax. Use the result in CAPM.

Issued ordinary shares outstanding: {basic_str} shares. Reference market quote: EUR {market} per share, for the treasury stock method only. Outstanding tranches: {tranche_text}. Each option converts into one ordinary share. Include only in-the-money incremental shares under TSM, no other dilution. Do not add hypothetical exercise cash again in the EV bridge.

Both bank facility accounts are interest-bearing debt. The current portion is not supplier credit. The book-equity balance already includes FY2025 earnings; do not add the year's income again to the historical equity balance.
"""
    )

    (p / "valuation_policy.md").write_text(
        f"""# CFO sign-off
Use only POSTED year-end source rows; amounts are unsigned magnitudes and the normal side is shown. North reports in thousands of euros; South in euros. The two sites are additive with no intercompany transactions. Sales, direct costs, administration, depreciation, interest and tax are FY2025 full-year flows; the other posted accounts are closing balances.

Forecast price multiplier {s['price_multiplier']}; additive shift to budget collection days {s['dso_shift']}. Annual net PP&E depreciation rate {D(s['dep_rate']) * 100}%. Timing: {d['timing']} for the five annual FCFFs, five years for the terminal value. Terminal method is {d['terminal']}; the going-concern growth mandate is {D(s['g']) * 100}% and the exit EBITDA assumption is {s['exit_multiple']}x. Use only the parameter for the assigned terminal method. No terminal premium or minority interest.
"""
    )

    return float(asset_beta), float(increment)


def public_instruction(d, original):
    out = original[original.index("## Delivery contract") :]
    policy = original[original.index("Cash COGS is") : original.index("## Valuation")]
    return (
        f"# {d['title']} | FY2025 valuation\n\n"
        "Start from a blank workbook. Read the seven source exhibits in /work/data/. They are original synthetic records, not a public company's filings. "
        "Deliver a self-contained /work/output.xlsx. Use the operating memo, budget, two site extracts and treasury/peer and valuation notes to build your own schedules, "
        "including peer beta and option dilution. Preserve full precision. Inputs and outputs are in EUR millions and millions of shares unless a source explicitly uses different units. "
        "Price per share is in EUR. The required price is DCF intrinsic value, not the market quote.\n\n"
        "Reconstruct FY2025 actuals (income statement and closing balance sheet; FY2025 cash flow statement is NOT required) and forecast FY2026–2030 IS, BS and CF. "
        "No other balances, tax deferrals, distributions, funding, issuance or transactions. "
        "Revenue-equivalent billable units express full-price equivalent annual volume: deduct expected warranty credits (returns), ADD immediate upfront license fees recognised in full (license), "
        "and apply minimum billing guarantees (royalty), strictly following operations_memo.md. "
        "Forecast revenue = those revenue-equivalent billable units times full annual unit price (converted to EUR millions) times the editable price_multiplier. "
        "Budget rate fields suffixed pct are percentages (e.g., 45.0 = 45%), while operations memo ratios are decimal fractions (e.g., 0.08 = 8%).\n\n"
        + policy
        + "CAPM/WACC use the signed treasury policy. Discount each annual FCFF at year-end (1–5) or midyear (0.5–4.5) as signed. "
        "Terminal at FY2030 close; perpetuity grows last FCFF by g, exit method uses final EBITDA. "
        "Equity value is EV plus FY2025 cash less FY2025 debt. Divide by TSM diluted shares.\n\n"
        + out
        + "\nAdditional required outputs (included in the 155 graded live-formula cells): "
        "DCF!B12 = relevered equity beta; DCF!B13 = diluted shares (millions); DCF!B14 = median unlevered peer beta; DCF!B15 = TSM incremental shares (millions). "
        "All four must resolve to live upstream calculation formulas. Their base values and formulas are graded as part of valuation.\n"
    )


def build(baseline, out):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    for src in sorted(baseline.glob("dcf-*")):
        dst = out / src.name
        d = json.loads((src / "environment/data/case.json").read_text())
        dst.mkdir(parents=True, exist_ok=True)
        asset, increment = sources(d, dst / "environment/data")
        shutil.copy(src / "environment/Dockerfile", dst / "environment/Dockerfile")
        if len(list((dst / "environment/data").iterdir())) != 7:
            raise ValueError("unexpected public file(s)")
        (dst / "instruction.md").write_text(public_instruction(d, (src / "instruction.md").read_text()))
        (dst / "task.toml").write_text((src / "task.toml").read_text())
        for sub in ("tests", "solution"):
            shutil.copytree(src / sub, dst / sub, dirs_exist_ok=True)
        (dst / "solution/canonical.json").write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
        p = dst / "tests/answers.json"
        a = json.loads(p.read_text())
        s = d["scalar"]
        extra = {"B12": s["beta"], "B13": s["shares"], "B14": asset, "B15": increment}
        for y in [a["base"]] + [v["expected"] for v in a["shocks"].values()]:
            y["DCF"].update(extra)
        p.write_text(json.dumps(a, indent=2) + "\n")


if __name__ == "__main__":
    build(
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("DCFEvalStructured"),
        Path(sys.argv[2]) if len(sys.argv) > 2 else Path("DCFEval"),
    )
