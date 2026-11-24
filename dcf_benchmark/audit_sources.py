"""Reconstruct canonical inputs strictly from the 7 public exhibits and verify exact equivalence."""
import csv
import json
import math
import re
import sys
from pathlib import Path
from statistics import median

from model import calculate
from forward import forward


def reconstruct(p: Path):
    read = lambda f: (p / f).read_text()
    rows = lambda f: list(csv.DictReader(read(f).splitlines()))
    numbers = r"([\d.]+)"

    def get(pattern, text):
        return float(re.search(pattern, text).group(1).rstrip("."))

    ops = read("operations_memo.md")
    tr = read("treasury_note.md")
    vp = read("valuation_policy.md")

    s = dict(
        opening_units=get(r"FY2025 closing .+?: " + numbers, ops),
        price_multiplier=get("price multiplier " + numbers, vp),
        dso_shift=get("days " + numbers, vp),
        dep_rate=get("depreciation rate " + numbers + "%", vp) / 100,
        g=get("mandate is " + numbers + "%", vp) / 100,
        exit_multiple=get("assumption is " + numbers + "x", vp),
    )
    s.update(
        tax_rate=get("Corporate tax " + numbers + "%", tr) / 100,
        debt_weight=get("debt is " + numbers + "%", tr) / 100,
        debt_cost=get("debt rate " + numbers + " bp", tr) / 10000,
        risk_free=get("Risk-free rate " + numbers + " bp", tr) / 10000,
        erp=get("risk premium " + numbers + " bp", tr) / 10000,
    )

    asset = median(
        float(e["observed_equity_beta"]) / (1 + (1 - float(e["statutory_tax_pct"]) / 100) * float(e["net_debt_to_equity_x"]))
        for e in rows("peer_set.csv")
    )
    s["beta"] = asset * (1 + (1 - s["tax_rate"]) * s["debt_weight"] / (1 - s["debt_weight"]))

    quote = get("quote: EUR " + numbers, tr)
    options = re.findall(numbers + " options at EUR " + numbers, tr)
    dilution = sum(float(count) * max(0.0, 1.0 - float(strike.rstrip(".")) / quote) for count, strike in options) / 1e6
    s["shares"] = get("outstanding: " + numbers + " shares", tr) / 1e6 + dilution

    a = {key: [] for key in ("A", "B", "C", "unit_price", "cogs_pct", "opex_fixed", "capex_pct", "dso", "dio", "dpo", "repay")}
    for line in ops.splitlines():
        if not re.match(r"FY20\d\d:", line):
            continue
        for key in "ABC":
            a[key].append(get(r"\(" + key + r"\) = " + numbers, line))
        a["unit_price"].append(get(r"(?:is|=)\s*EUR\s*" + numbers, line) / 1e6)

    for e in sorted(rows("finance_budget.csv"), key=lambda x: x["fy"]):
        for k, n, f in [
            ("cogs_pct", "cash_cost_pct_of_sales", 100),
            ("opex_fixed", "fixed_expense_EUR_thousands", 1000),
            ("capex_pct", "investment_pct_of_sales", 100),
            ("dso", "collection_days", 1),
            ("dio", "stock_days", 1),
            ("dpo", "supplier_days", 1),
            ("repay", "debt_amort_EUR_thousands", 1000),
        ]:
            a[k].append(float(e[n]) / f)

    chart = dict(
        zip(
            "4100 5105 6202 6710 7102 7900 1210 1320 2315 1520 2112 2710 1015 3105".split(),
            "revenue cogs opex da interest tax ar inv ap ppe debt debt cash equity".split(),
        )
    )
    led = []
    for site in ["north", "south"]:
        for e in rows(site + "_close.csv"):
            if e["status"] != "POSTED":
                continue
            field = next(n for n in e if n.startswith("amount_"))
            scale = 1000 if field.endswith("_thousands") else 1e6
            led.append({"account": chart[e["account"]], "amount": float(e[field]) / scale})

    case = dict(
        slug=p.parent.parent.name.split("-", 2)[2],
        ledger=led,
        series=a,
        scalar=s,
        terminal=re.search("Terminal method is (.+?);", vp)[1],
        timing=re.search(r"Timing: (\S+)", vp)[1],
    )
    return case, asset, dilution


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
