"""Public Python interface: canonical scenario -> named 3-statement forecasts and DCF valuation."""
import argparse
import json
from pathlib import Path

if __package__:
    from .model import calculate, ROWS, VAL
else:
    from model import calculate, ROWS, VAL


def forward(case, overrides=None):
    cells = calculate(case, overrides)
    stat = cells["Statements"]
    groups = {
        "operations": [4, 5],
        "income_statement": [6, 7, 8, 9, 10, 11, 12, 13],
        "balance_sheet": [14, 15, 16, 17, 19, 20, 22, 23, 24, 25],
        "cash_flow_statement": [26, 27, 28, 29],
        "supporting_schedules": [18, 21, 30, 31, 32, 33],
    }
    years = {}
    for col, year in zip("BCDEFG", range(2025, 2031)):
        years[str(year)] = {
            name: {ROWS[row]: stat[col + str(row)] for row in rows if col + str(row) in stat}
            for name, rows in groups.items()
        }
        if year == 2025:
            years[str(year)].pop("cash_flow_statement")
            years[str(year)].pop("supporting_schedules")
        else:
            prev = chr(ord(col) - 1)
            years[str(year)]["cash_flow_statement"].update(
                {"Opening cash": stat[prev + "22"], "Closing cash": stat[col + "22"]}
            )
    return {
        "case": case["slug"],
        "currency": "EUR",
        "amount_scale": "millions",
        "valuation_date": "2025-12-31",
        "years": years,
        "valuation": {name: cells["DCF"]["B" + str(row)] for row, name in VAL.items()},
        "equity_bridge": {
            "FY2025 cash": stat["B22"],
            "FY2025 debt": stat["B20"],
            "diluted shares (millions)": (case["scalar"] | (overrides or {}))["shares"],
        },
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("canonical", type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    payload = json.dumps(forward(json.loads(a.canonical.read_text())), ensure_ascii=False, indent=2) + "\n"
    if a.out:
        a.out.write_text(payload)
    else:
        print(payload, end="")
