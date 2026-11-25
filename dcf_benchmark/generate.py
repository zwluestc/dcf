"""Generate structured Harbor baseline tasks with going-concern and branch-coverage screening."""
import argparse
import json
import random
import shutil
from pathlib import Path

from takeover import is_takeover
from model import CASES, ROWS, VAL, HIST, generate, calculate, branches_covered

HERE = Path(__file__).resolve().parent

INLINE_DOCKERFILE = """FROM debian:12-slim
RUN set -eu; \\
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \\
      cp /etc/apt/sources.list.d/debian.sources /tmp/debian.sources.bak; \\
      sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \\
      if ! apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=15 update; then \\
        mv /tmp/debian.sources.bak /etc/apt/sources.list.d/debian.sources; \\
        apt-get -o Acquire::Retries=2 update; \\
      fi; \\
      rm -f /tmp/debian.sources.bak; \\
    else \\
      apt-get -o Acquire::Retries=2 update; \\
    fi; \\
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\
      bash python3 python3-openpyxl libreoffice-calc ca-certificates && \\
    rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY data /work/data
"""


def save(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def instruction(d):
    return f"""# {d['title']} | CFO valuation assignment

Start from a new blank Excel workbook. Public source: /work/data/case.json (synthetic two-site FY2025 ledger, calendar-year drivers and scalar assumptions). Deliver a self-contained, formula-driven /work/output.xlsx, no external links or macros. Use Excel formulas in every required forecast and DCF output. Additional tabs and helper cells are welcome.

## Mandate
Build the FY2025 actuals, FY2026–2030 annual income statements, balance sheets, cash flows and an FCFF valuation at 31 Dec 2025. Currency EUR millions; shares in millions, values per share in EUR. Unit price is already millions EUR per unit. Rates are decimals; keep full precision and fractional operating units. Add the two sites by account; ledger expense, asset, equity and liability balances are positive magnitudes. All source records are final. No dividends, issuance, new borrowing, other accounts or transactions.

## Operating contract
Opening FY2026 operating units are scalar.opening_units. Series arrays run 2026 to 2030 in order. A/B/C stand for {d['driver_labels']}. {d['rule']} Billable units means the *revenue-equivalent* volume at full unit price (net of credits, including fees/minimums where relevant). Multiply it by that year's unit_price and the price_multiplier. Never round units for modelling.

Cash COGS is cogs_pct of sales; operating expenses are opex_fixed excluding D&A. Capex equals capex_pct of sales, capitalized in full. D&A uses dep_rate on opening net PP&E plus half current capex. Cap principal repayments at opening debt; interest uses average opening/closing debt at debt_cost. Tax on positive EBT only, no tax benefit or carryforward. Unlevered tax is on positive EBIT. Receivables use sales and dso plus dso_shift; inventory and payables use cash COGS and dio/dpo, on a 365-day basis. NWC = AR + inventory less AP. Equity accumulates net income, and cash accumulates the three cash flows. Operating cash flow is after interest and tax. Show COGS, opex, D&A, tax, interest, capex and principal as positive expenses/outlays; investing/financing cash flows use cash signs. Change in NWC is closing less opening.

## Valuation
CAPM cost of equity: risk_free + beta times erp. WACC uses target debt_weight and statutory tax shield on debt_cost. Discount each forecast FCFF using {d['timing']} timing (0.5–4.5 for midyear; 1–5 for year-end). Terminal method: {d['terminal']}. Perpetuity uses 2030 FCFF grown one year at g; exit uses 2030 EBITDA times exit_multiple. For BOTH conventions, terminal value is at end-2030 and discounted five years. Bridge EV using **actual FY2025 closing** cash and debt only; divide equity value by shares.

## Delivery contract
Inputs!B4:B6 must be editable numeric values stored in the exact underlying units below (display formatting is optional), and downstream formulas must respond dynamically to edits:
- Inputs!B4 (`price_multiplier`): dimensionless decimal multiplier (e.g., `1.0`).
- Inputs!B5 (`dso_shift`): additive shift in calendar days (e.g., `0.0`).
- Inputs!B6 (`risk_free`): annual decimal fraction (e.g., 320 bp MUST be stored as `0.032`, not `320` or `3.2`; display as `3.20%` is optional).
Other inputs and helper tabs may be laid out freely.

Formula scope: every required computed forecast cell in Statements!C4:G33 EXCEPT row 8 (exogenous Cash operating expense, which may either link to a budget sheet or hold the numeric EUR millions budget value), plus every required output in DCF!B4:B9 (and DCF!B12:B15 where requested), MUST be a live Excel formula referencing upstream computation cells (hardcoded numbers, constant-only formulas such as `=1.13`, or bare links to hardcoded helper cells are rejected).

Statements!B3:G3 must be the numeric years 2025–2030. Row numbers below denote outputs in that sheet. In B (actuals) only rows {', '.join(map(str, HIST))} are required. C:G require every row. Each row name below is also the requested metric definition. Balance-sheet assets are cash + receivables + inventory + net PP&E, liabilities and equity are AP + debt + equity.

{chr(10).join(f'- {n}: {v}' for n, v in ROWS.items())}

DCF sheet outputs (rates such as WACC in B4 must evaluate to annual decimal fractions, e.g., `0.0827` for 8.27%):
{chr(10).join(f'- B{n}: {v}' for n, v in VAL.items())}

Numeric tolerance: greater of EUR million (or native-unit) absolute 0.000001 and 0.0001% relative. Scoring follows a practitioner four-pillar rubric: three-statement & FCFF accuracy (40%), materiality-weighted valuation bridge & per-share value (25%), base & post-shock accounting reconciliation (15%), and assumption sensitivity delta linkage across the three editable assumptions (20%), multiplied by an anti-hardcoding dynamic formula gate.
"""


def build(out, seed, waves=2):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    for wave in range(waves):
        wave_seed = seed + wave * 100003
        offset = 10 * wave
        for k, (slug, *_) in enumerate(CASES):
            sd = wave_seed + 1009 * k
            for attempt in range(600):
                cand_seed = sd + attempt * 104729
                d = generate(k, cand_seed, wave=wave)
                if is_takeover(f"dcf-{offset+k+1:02}-{slug}"):
                    d["scalar"].update(price_multiplier=round(1.02+.003*k,4),dso_shift=2+k%5)
                baseline = calculate(d)
                w = baseline["DCF"]["B4"]
                ev = baseline["DCF"]["B7"]
                pvt = baseline["DCF"]["B6"]
                ebitda25 = baseline["Statements"]["B10"] + baseline["Statements"]["B9"]
                pv_share = pvt / ev if ev > 0 else 0.0
                ev_mult = ev / ebitda25 if ebitda25 > 0 else 0.0
                if (
                    w - d["scalar"]["g"] >= 0.025
                    and baseline["DCF"]["B5"] > 0
                    and baseline["DCF"]["B9"] > 0
                    and min(baseline["Statements"][c + "22"] for c in "CDEFG") >= 0
                    and min(baseline["Statements"][c + "19"] for c in "CDEFG") > 0
                    and 0.50 <= pv_share <= 0.85
                    and 4.5 <= ev_mult <= 22.0
                    and branches_covered(d)
                ):
                    break
            else:
                raise ValueError(f"No valid going-concern/branch-covered case for {slug}, wave={wave}, seed={seed}")

            task = out / f"dcf-{offset + k + 1:02}-{slug}"
            for sub in ("environment/data", "solution", "tests"):
                (task / sub).mkdir(parents=True, exist_ok=True)
            save(task / "environment/data/case.json", d)
            (task / "instruction.md").write_text(instruction(d))
            (task / "task.toml").write_text(
                f'''schema_version = "1.4"
artifacts = ["/work/output.xlsx"]
[task]
name = "dcfeval/{task.name}"
description = "From-blank integrated 3-statement forecast and FCFF valuation: {slug} (wave {wave + 1})"
[agent]
timeout_sec = 900
[environment]
build_timeout_sec = 1200
cpus = 1
memory_mb = 1536
storage_mb = 4096
network_mode = "no-network"
workdir = "/work"
[verifier]
timeout_sec = 180
environment_mode = "separate"
[verifier.environment]
build_timeout_sec = 1200
cpus = 1
memory_mb = 1536
network_mode = "no-network"
workdir = "/tests"
'''
            )
            (task / "environment/Dockerfile").write_text(INLINE_DOCKERFILE)
            (task / "solution/solve.sh").write_text("#!/bin/sh\nset -eu\ncp /solution/reference.xlsx /work/output.xlsx\n")
            (task / "tests/test.sh").write_text(
                "#!/bin/sh\nset -eu\npython3 /tests/grade.py /work/output.xlsx /tests/answers.json /logs/verifier/details.json\n"
            )
            for f in ("solution/solve.sh", "tests/test.sh"):
                (task / f).chmod(0o755)
            shutil.copyfile(HERE / "grade.py", task / "tests/grade.py")

            rng = random.Random(cand_seed + 18019)
            s = d["scalar"]
            keys = ["price_multiplier", "dso_shift", "risk_free"]
            vs = [
                round(rng.uniform(0.80, 0.94), 6),
                s["dso_shift"] + rng.randint(6, 15),
                round(s["risk_free"] + rng.uniform(0.006, 0.015), 6),
            ]
            tar = {"base": baseline, "controls": {f"B{i + 4}": s[key] for i, key in enumerate(keys)}, "shocks": {}}
            for i, (key, new, kind) in enumerate(zip(keys, vs, ["operations", "collection", "discount"])):
                tar["shocks"][kind] = {"changes": {f"B{i + 4}": new}, "expected": calculate(d, {key: new})}
            save(task / "tests/answers.json", tar)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=HERE.parent / "DCFEvalStructured")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--waves", type=int, default=2, help="Number of 10-case waves (default 2 -> 20 tasks)")
    a = p.parse_args()
    build(a.out, a.seed, waves=a.waves)
