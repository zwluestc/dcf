"""Deterministic numeric oracle for DCFEval. All amounts are EUR millions unless noted."""
from collections import defaultdict
from decimal import Decimal
import random

CASES = [
    (
        "saas",
        "订阅软件：流失、新签与平均计费",
        "subscribers",
        "new logos",
        "churn",
        "upsell",
        (0.21, 0.12, 0.07),
        "Opening subscribers lose B; add A at midyear. Activity is mean opening/closing subscribers times (1+C) expansion.",
    ),
    (
        "foundry",
        "晶圆代工：良率与产能上限",
        "capacity",
        "new capacity",
        "demand",
        "yield",
        (0.13, 1.38, 0.92),
        "Capacity adds A at year start. Process the lesser of closing capacity and B demand; C is good-output yield.",
    ),
    (
        "orders",
        "装备制造：在手订单与分期履约",
        "backlog",
        "bookings",
        "conversion",
        "same-year delivery",
        (0.87, 0.61, 0.22),
        "Fulfil B of opening backlog and C of new bookings A. Recognise fulfilled orders; carry both unfulfilled portions forward.",
    ),
    (
        "storage",
        "仓储：退租、可用库位与入住时点",
        "leased slots",
        "new demand",
        "attrition",
        "max slots",
        (0.20, 0.16, 1.03),
        "Opening slots suffer B attrition at year start. Admit at most A new leases up to C total capacity. Surviving slots earn a full year; new leases earn half.",
    ),
    (
        "fleet",
        "设备租赁：退役、投放与利用率",
        "fleet",
        "new units",
        "retirement",
        "utilization",
        (0.14, 0.08, 0.82),
        "Retire B of opening fleet at year start. Deliver A at midyear. Closing fleet includes deliveries; charge for surviving fleet plus half deliveries, at C utilization.",
    ),
    (
        "license",
        "许可合同：续签、签约费与持续费",
        "licenses",
        "new licenses",
        "renewal rate",
        "upfront multiple",
        (0.255, 0.82, 0.45),
        "Renew B of opening licenses and sign A at midyear. Recognise full-year service revenue on renewed licenses and half-year service revenue on new additions; in addition, each new addition pays an immediate upfront license fee equal to C times the full annual unit rate, recognised in full as revenue in the year signed.",
    ),
    (
        "mine",
        "矿业：储量、开采上限与回收率",
        "reserves",
        "discoveries",
        "extraction cap",
        "recovery",
        (0.24, 0.48, 0.87),
        "Discover A before extraction. Extract the lesser of B and opening reserves plus discoveries. Close reserves net of extraction. Sell C of extracted units. For the prescribed terminal scenario, assume annual resource replacement sustains terminal output and its cost is already included in terminal FCFF.",
    ),
    (
        "retail",
        "连锁零售：关店与新店爬坡",
        "stores",
        "openings",
        "closure rate",
        "new-store productivity",
        (0.16, 0.09, 0.40),
        "Close fraction B of opening stores at year start. Open A new stores; each new store earns fraction C of a mature store's annual sales in its first year. All surviving opening stores are mature.",
    ),
    (
        "royalty",
        "特许权：分档计费与最低保底",
        "installed units",
        "new placements",
        "threshold",
        "excess-rate multiple",
        (0.13, 0.88, 0.46),
        "Add A placements at year start. First B closing units earn full unit rate, excess earns C of rate. Minimum annual bill equals 0.90 times opening units at full rate; take higher bill.",
    ),
    (
        "returns",
        "售后服务：保修期、返修结算与新单",
        "covered units",
        "new covers",
        "expiry rate",
        "claim incidence",
        (0.165, 0.14, 0.17),
        "Expire B of opening covers; sell A new annual covers. Service revenue uses surviving opening covers plus half additions. Deduct expected credits equal to C times opening covers times 40% of unit rate.",
    ),
]

ROWS = dict(
    enumerate(
        (
            "Closing operating units",
            "Revenue-equivalent billable units",
            "Revenue",
            "Cash COGS",
            "Cash operating expense",
            "Depreciation",
            "EBIT",
            "Interest",
            "Income tax",
            "Net income",
            "Receivables",
            "Inventory",
            "Payables",
            "Net working capital",
            "Capital expenditure",
            "Net PP&E",
            "Term debt",
            "Principal repaid",
            "Cash",
            "Book equity",
            "Assets",
            "Liabilities and equity",
            "Operating cash flow",
            "Investing cash flow",
            "Financing cash flow",
            "Change in cash",
            "Unlevered cash tax",
            "Change in NWC",
            "FCFF",
            "PV of FCFF",
        ),
        4,
    )
)

VAL = dict(
    enumerate(
        (
            "WACC",
            "Terminal value at FY2030 end",
            "PV of terminal value",
            "Enterprise value",
            "Equity value",
            "Value per diluted share",
        ),
        4,
    )
)

HIST = [4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 19, 20, 22, 23, 24, 25]
VALUED = [4, 5, 6, 7, 8, 9]

# Indices of drivers (A, B, C) expressed in operating-unit scale (proportional to opening_units)
UNIT_SCALED_DRIVERS = {
    "saas": ("A",),
    "foundry": ("A", "B"),
    "orders": ("A",),
    "storage": ("A", "C"),
    "fleet": ("A",),
    "license": ("A",),
    "mine": ("A", "B"),
    "retail": ("A",),
    "royalty": ("A", "B"),
    "returns": ("A",),
}


COMPANY_NAMES = [
    [
        "SpruceCollab (云杉协作)",
        "Elmbridge Semi (榆桥微芯)",
        "Starport Machinery (星浦机床)",
        "Ninggang ColdChain (宁港冷仓)",
        "RiverRidge Fleet (川岭器租)",
        "ClearRiver CAD (晴川图软)",
        "StoneCourt Copper (石庭铜业)",
        "Platform Books (月台书铺)",
        "SeaChord Audio (海弦音频)",
        "SwiftBoat Care (凌舟维保)",
    ],
    [
        "BambooCloud Ops (竹序算务)",
        "HarborCreek Fab (泊川晶圆)",
        "Langstone Pumps (朗石泵业)",
        "ReedBay Thermal (芦湾恒温)",
        "Greenfield Equip (青浦工装)",
        "Shoreline Design (岸禾设计)",
        "RidgeSpring Zinc (岭泉锌业)",
        "EastIsle Home (东屿家居)",
        "SpringStone Media (泉石影像)",
        "SilverDock Service (银栈售服)",
    ],
]


def company_name(k, wave):
    if wave < len(COMPANY_NAMES):
        return COMPANY_NAMES[wave][k]
    return f"NovaCorp-W{wave + 1:02d}-{k + 1:02d}"


def generate(k, seed, wave=0):
    r = random.Random(seed)
    slug, title, unit, aa, bb, cc, driver_ratios, rule = CASES[k]
    cname = company_name(k, wave)

    opening_units = r.randrange(860, 1240)
    unit_scaled = set(UNIT_SCALED_DRIVERS[slug])

    def arr(base, spread=0.14):
        return [round(base * r.uniform(1.0 - spread, 1.0 + spread), 6) for _ in range(5)]

    inp = {}
    for key, ratio in zip("ABC", driver_ratios):
        base_val = opening_units * ratio if key in unit_scaled else ratio
        spread = 0.18 if (slug == "foundry" and key == "B") else 0.14
        if key not in unit_scaled and ratio >= 0.80:
            # Keep rate/yield ratios <= 0.98
            inp[key] = [round(min(0.98, max(0.05, base_val * r.uniform(0.90, 1.07))), 6) for _ in range(5)]
        else:
            inp[key] = arr(base_val, spread=spread)

    # Company-specific FY2025 historical scale and capital structure (distinct per task/seed)
    rev = round(r.uniform(95.0, 220.0), 1)
    cogs_ratio = r.uniform(0.39, 0.53)
    cogs = round(rev * cogs_ratio, 1)
    opex = round(rev * r.uniform(0.11, 0.18), 1)
    da = round(rev * r.uniform(0.05, 0.09), 1)
    interest = round(rev * r.uniform(0.010, 0.024), 1)
    tax_rate = round(r.uniform(0.19, 0.28), 4)
    ebt_h = max(4.0, rev - cogs - opex - da - interest)
    tax = round(max(1.0, ebt_h * tax_rate * r.uniform(0.88, 1.05)), 1)

    ar = round(rev * r.uniform(0.11, 0.18), 1)
    inv = round(cogs * r.uniform(0.12, 0.22), 1)
    ap = round(cogs * r.uniform(0.11, 0.20), 1)
    ppe = round(rev * r.uniform(0.45, 0.70), 1)
    debt = round(rev * r.uniform(0.14, 0.30), 1)
    cash = round(rev * r.uniform(0.10, 0.20), 1)
    equity = float(
        Decimal(str(ar))
        + Decimal(str(inv))
        + Decimal(str(ppe))
        + Decimal(str(cash))
        - Decimal(str(ap))
        - Decimal(str(debt))
    )

    # Scale forecast unit price coherently to Year-1 billable volume so FY25->FY26 revenue is realistic across all 10 mechanisms
    _, est_y1_billable = operating(slug, opening_units, inp["A"][0], inp["B"][0], inp["C"][0])
    base_unit_price = round((rev / max(1.0, est_y1_billable)) * r.uniform(0.96, 1.12), 6)
    base_dso = round(ar / rev * 365.0, 2)
    base_dio = round(inv / cogs * 365.0, 2)
    base_dpo = round(ap / cogs * 365.0, 2)

    inp.update(
        unit_price=arr(base_unit_price, 0.10),
        cogs_pct=arr(cogs_ratio, 0.09),
        opex_fixed=arr(opex * r.uniform(0.96, 1.08), 0.09),
        capex_pct=arr(r.uniform(0.055, 0.085), 0.10),
        dso=arr(base_dso, 0.10),
        dio=arr(base_dio, 0.10),
        dpo=arr(base_dpo, 0.10),
        repay=arr(debt * r.uniform(0.18, 0.26), 0.12),
    )

    draws = dict(
        price_multiplier=1.0,
        dso_shift=0.0,
        risk_free=round(r.uniform(0.025, 0.043), 4),
        beta=round(r.uniform(0.88, 1.38), 4),
        erp=round(r.uniform(0.048, 0.064), 4),
        debt_weight=round(r.uniform(0.18, 0.40), 4),
        debt_cost=round(r.uniform(0.044, 0.070), 4),
        tax_rate=tax_rate,
        g=round(r.uniform(0.016, 0.028), 4),
        exit_multiple=round(r.uniform(7.0, 10.6), 2),
        shares=round(r.uniform(8.5, 18.0), 3),
        opening_units=opening_units,
        dep_rate=round(r.uniform(0.10, 0.15), 4),
    )

    raw = dict(
        revenue=rev,
        cogs=cogs,
        opex=opex,
        da=da,
        interest=interest,
        tax=tax,
        ar=ar,
        inv=inv,
        ap=ap,
        ppe=ppe,
        debt=debt,
        cash=cash,
        equity=equity,
    )

    ledger = []
    for key, v in raw.items():
        vd = Decimal(str(v))
        a = Decimal(str(round(float(vd) * r.uniform(0.32, 0.68), 3)))
        b = vd - a
        for site, j in (("North", float(a)), ("South", float(b))):
            ledger.append(dict(site=site, account=key, amount=j))
    r.shuffle(ledger)

    return dict(
        seed=seed,
        wave=wave,
        company=cname,
        slug=slug,
        title=f"{cname} | {title}",
        rule=rule,
        driver_labels=dict(zip("ABC", (aa, bb, cc))),
        unit=unit,
        series=inp,
        scalar=draws,
        ledger=ledger,
        terminal=["perpetuity", "exit EBITDA"][(k + wave) % 2],
        timing=["midyear", "year-end"][(k // 2 + wave) % 2],
    )


def operating(slug, p, a, b, c):
    if slug == "saas":
        q = p * (1 - b) + a
        return q, (p + q) / 2 * (1 + c)
    if slug == "foundry":
        return p + a, min(p + a, b) * c
    if slug == "orders":
        v = p * b + a * c
        return p + a - v, v
    if slug == "storage":
        old = p * (1 - b)
        add = min(a, max(0, c - old))
        return old + add, old + add / 2
    if slug == "fleet":
        return p * (1 - b) + a, (p * (1 - b) + a / 2) * c
    if slug == "license":
        return p * b + a, p * b + a * (0.5 + c)
    if slug == "mine":
        v = min(p + a, b)
        return p + a - v, v * c
    if slug == "retail":
        return p * (1 - b) + a, p * (1 - b) + a * c
    if slug == "royalty":
        q = p + a
        return q, max(0.9 * p, min(q, b) + max(0, q - b) * c)
    if slug == "returns":
        return p * (1 - b) + a, p * (1 - b) + a / 2 - 0.4 * p * c
    raise ValueError(slug)


def branches_covered(d):
    """Verify nonlinear constraint cases hit both sides of MIN/MAX branches over FY2026-2030."""
    slug = d["slug"]
    series = d["series"]
    p = d["scalar"]["opening_units"]
    hits_a, hits_b = 0, 0
    for t in range(5):
        a, b, c = series["A"][t], series["B"][t], series["C"][t]
        if slug == "foundry":
            q = p + a
            hits_a += int(q < b)
            hits_b += int(q > b)
            p = q
        elif slug == "storage":
            old = p * (1 - b)
            cap_left = max(0, c - old)
            hits_a += int(a > cap_left)
            hits_b += int(a < cap_left)
            p = old + min(a, cap_left)
        elif slug == "mine":
            avail = p + a
            hits_a += int(avail > b)
            hits_b += int(avail < b)
            p = avail - min(avail, b)
        elif slug == "royalty":
            q = p + a
            tiered = min(q, b) + max(0, q - b) * c
            floor_bill = 0.9 * p
            hits_a += int(tiered > floor_bill and q > b)
            hits_b += int(floor_bill > tiered)
            p = q
        else:
            return True
    return hits_a >= 1 and hits_b >= 1


def calculate(d, override=None):
    s = d["scalar"] | (override or {})
    series = d["series"]
    h = defaultdict(float)
    for e in d["ledger"]:
        h[e["account"]] += e["amount"]
    hrow = {
        4: s["opening_units"],
        **{
            i: h[n]
            for i, n in {
                6: "revenue",
                7: "cogs",
                8: "opex",
                9: "da",
                11: "interest",
                12: "tax",
                14: "ar",
                15: "inv",
                16: "ap",
                19: "ppe",
                20: "debt",
                22: "cash",
                23: "equity",
            }.items()
        },
    }
    hrow[10] = hrow[6] - sum(hrow[i] for i in (7, 8, 9))
    hrow[13] = hrow[10] - hrow[11] - hrow[12]
    hrow[17] = hrow[14] + hrow[15] - hrow[16]
    hrow[24] = hrow[22] + hrow[14] + hrow[15] + hrow[19]
    hrow[25] = hrow[16] + hrow[20] + hrow[23]

    cols = [hrow]
    w = (s["risk_free"] + s["beta"] * s["erp"]) * (1 - s["debt_weight"]) + s["debt_cost"] * s["debt_weight"] * (
        1 - s["tax_rate"]
    )

    for t in range(5):
        p = cols[-1]
        i = {k: v[t] for k, v in series.items()}
        x = {}
        x[4], x[5] = operating(d["slug"], p[4], i["A"], i["B"], i["C"])
        x[6] = x[5] * i["unit_price"] * s["price_multiplier"]
        x[7] = x[6] * i["cogs_pct"]
        x[8] = i["opex_fixed"]
        x[18] = x[6] * i["capex_pct"]
        x[9] = (p[19] + x[18] / 2) * s["dep_rate"]
        x[10] = x[6] - x[7] - x[8] - x[9]
        x[21] = min(p[20], i["repay"])
        x[20] = p[20] - x[21]
        x[11] = (p[20] + x[20]) / 2 * s["debt_cost"]
        x[12] = max(0, x[10] - x[11]) * s["tax_rate"]
        x[13] = x[10] - x[11] - x[12]
        x[14] = x[6] * (i["dso"] + s["dso_shift"]) / 365
        x[15] = x[7] * i["dio"] / 365
        x[16] = x[7] * i["dpo"] / 365
        x[17] = x[14] + x[15] - x[16]
        x[31] = x[17] - p[17]
        x[19] = p[19] + x[18] - x[9]
        x[26] = x[13] + x[9] - x[31]
        x[27] = -x[18]
        x[28] = -x[21]
        x[29] = x[26] + x[27] + x[28]
        x[22] = p[22] + x[29]
        x[23] = p[23] + x[13]
        x[24] = x[22] + x[14] + x[15] + x[19]
        x[25] = x[16] + x[20] + x[23]
        x[30] = max(0, x[10]) * s["tax_rate"]
        x[32] = x[10] - x[30] + x[9] - x[18] - x[31]
        x[33] = x[32] / (1 + w) ** (t + 1 - (0.5 if d["timing"] == "midyear" else 0))
        cols.append(x)

    tv = x[32] * (1 + s["g"]) / (w - s["g"]) if d["terminal"] == "perpetuity" else (x[10] + x[9]) * s["exit_multiple"]
    pvt = tv / (1 + w) ** 5
    ev = pvt + sum(col[33] for col in cols[1:])
    eq = ev + h["cash"] - h["debt"]
    vals = [w, tv, pvt, ev, eq, eq / s["shares"]]

    assert s["g"] < w and all(abs(c[24] - c[25]) < 1e-8 for c in cols)
    return {
        "Statements": {f"{chr(66 + t)}{row}": v for t, c in enumerate(cols) for row, v in c.items()},
        "DCF": dict(zip(("B" + str(r) for r in VAL), vals)),
    }
