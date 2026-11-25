"""Pure-Python openpyxl dynamic formula reference workbook builder.

In raw Harbor mode, ALL numeric inputs, schedules, and assumptions are parsed strictly from the
7 public source exhibits in `environment/data/` — zero reliance on private `canonical.json` —
making `reference.xlsx` + LibreOffice a genuinely independent verification path against `model.py`.
"""
import csv
import json
import re
import sys
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from audit_sources import reconstruct
from filings import read_ledger, plan_and_peers

NF_NUM = '#,##0.00;(#,##0.00);"-"'
NF_PCT = "0.00%"
NF_MULT = '0.00"x"'
HEADER_FILL = PatternFill("solid", fgColor="20485E")
SUB_FILL = PatternFill("solid", fgColor="E4EEF1")
FONT_BODY = Font(name="Arial", size=10)
FONT_BOLD = Font(name="Arial", size=10, bold=True)
FONT_TITLE = Font(name="Arial", size=14, bold=True, color="20485E")
FONT_HEADER = Font(name="Arial", size=10, bold=True, color="FFFFFF")
FONT_INPUT = Font(name="Arial", size=10, color="1646A0")

SCALAR_ORDER = [
    "price_multiplier",
    "dso_shift",
    "risk_free",
    "beta",
    "erp",
    "debt_weight",
    "debt_cost",
    "tax_rate",
    "g",
    "exit_multiple",
    "shares",
    "opening_units",
    "dep_rate",
]

SERIES_ORDER = ["A", "B", "C", "unit_price", "cogs_pct", "opex_fixed", "capex_pct", "dso", "dio", "dpo", "repay"]

STATEMENT_LABELS = [
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
]

CHART_TO_KEY = {
    "4100": "revenue",
    "5105": "cogs",
    "6202": "opex",
    "6710": "da",
    "7102": "interest",
    "7900": "tax",
    "1210": "ar",
    "1320": "inv",
    "2315": "ap",
    "1520": "ppe",
    "2112": "debt",
    "2710": "debt",
    "1015": "cash",
    "3105": "equity",
}


def style_sheet(ws, max_row, max_col):
    ws.views.sheetView[0].showGridLines = False
    ws.column_dimensions["A"].width = 34
    for col_idx in range(2, max_col + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 16
    for r in range(1, max_row + 1):
        for c in range(1, max_col + 1):
            cell = ws.cell(row=r, column=c)
            cell.font = FONT_BODY
            if r >= 4 and c >= 2:
                cell.number_format = NF_NUM
    ws["A1"].font = FONT_TITLE
    for c in range(1, max_col + 1):
        cell = ws.cell(row=3, column=c)
        cell.fill = HEADER_FILL
        cell.font = FONT_HEADER


def build_task_workbook(root: Path):
    pub = root / "environment/data"
    raw = not (pub / "case.json").exists()
    if raw:
        # Strict public-only input path: reconstruct solely from the 7 public source exhibits
        d, _, _ = reconstruct(pub)
        driver_labels = {}
        ops_lines = (pub / "operations_memo.md").read_text().splitlines()
        first_fy = next(line for line in ops_lines if re.match(r"FY20\d\d:", line))
        for k in "ABC":
            m = re.search(r"[:;]\s*([^:;]+?)\s*\(" + k + r"\)\s*=", first_fy)
            if m:
                driver_labels[k] = m.group(1).strip()
        d["driver_labels"] = driver_labels
    else:
        d = json.loads((pub / "case.json").read_text())

    wb = Workbook()
    ws_dcf = wb.active
    ws_dcf.title = "DCF"
    ws_stmt = wb.create_sheet("Statements")
    ws_in = wb.create_sheet("Inputs")
    ws_led = wb.create_sheet("Ledger")

    style_sheet(ws_dcf, 16 if raw else 10, 2)
    style_sheet(ws_stmt, 34, 7)
    style_sheet(ws_in, 35, 7)
    style_sheet(ws_led, 40, 6 if raw else 3)

    ws_dcf["A1"] = "Enterprise valuation"
    ws_dcf["A3"], ws_dcf["B3"] = "As of FY2025 close", "EUR millions"

    ws_stmt["A1"] = "Operating and financial forecast"
    for j, val in enumerate(["EUR millions, except units", 2025, 2026, 2027, 2028, 2029, 2030], start=1):
        cell = ws_stmt.cell(row=3, column=j, value=val)
        if j >= 2:
            cell.number_format = "0"

    ws_in["A1"] = "Forecast assumptions"
    ws_in["A3"], ws_in["B3"] = ("Source: public exhibits only" if raw else "Source: synthetic case.json"), "Assumption"

    # Inputs scalar block: Inputs!B4:B6 MUST be price_multiplier, dso_shift, risk_free
    sc_keys = SCALAR_ORDER
    series_keys = SERIES_ORDER
    for idx, k in enumerate(sc_keys):
        r = 4 + idx
        ws_in.cell(row=r, column=1, value=k)
        c = ws_in.cell(row=r, column=2, value=d["scalar"][k])
        c.font = FONT_INPUT
        if r == 4:
            c.number_format = NF_MULT
        elif r in (6, 8, 9, 10, 11, 12, 16):
            c.number_format = NF_PCT

    def inp_ref(key):
        return f"Inputs!$B${4 + sc_keys.index(key)}"

    for j, val in enumerate(["Forecast driver", "Unit / basis", 2026, 2027, 2028, 2029, 2030], start=1):
        cell = ws_in.cell(row=20, column=j, value=val)
        cell.fill = HEADER_FILL
        cell.font = FONT_HEADER
        if j >= 3:
            cell.number_format = "0"
    ws_in.column_dimensions["B"].width = 25
    for idx, k in enumerate(series_keys):
        r = 21 + idx
        ws_in.cell(row=r, column=1, value=k)
        ws_in.cell(row=r, column=2, value=d["driver_labels"].get(k, ""))
        for j, val in enumerate(d["series"][k], start=3):
            ws_in.cell(row=r, column=j, value=val)

    # Ledger sheet parsed directly from public site close CSVs in raw mode
    account_cells = {}
    if raw:
        ws_led["A1"] = "Actual posted ledger"
        for j, h in enumerate(["Site", "Account", "Mapped key", "Native amount", "Scale", "EUR millions"], start=1):
            ws_led.cell(row=3, column=j, value=h)
        row_idx = 4
        for site in ("north", "south"):
            for acct, amount, scale, cite in read_ledger(pub,site.title()):
                key = CHART_TO_KEY[acct]
                for j, value in enumerate([site.title(),acct,key,amount,scale,f"=D{row_idx}/E{row_idx}",cite],1):
                    ws_led.cell(row_idx,j,value)
                account_cells.setdefault(key, []).append(f"Ledger!F{row_idx}")
                row_idx += 1
        ws_led["G3"]="Filing reference"
        ws_led.column_dimensions["G"].width=36
    else:
        ws_led["A1"] = "Actual ledger"
        for j, h in enumerate(["Site", "FY2025 account", "EUR millions"], start=1):
            ws_led.cell(row=3, column=j, value=h)
        for idx, rec in enumerate(d["ledger"]):
            row_idx = 4 + idx
            ws_led.cell(row=row_idx, column=1, value=rec["site"])
            ws_led.cell(row=row_idx, column=2, value=rec["account"])
            ws_led.cell(row=row_idx, column=3, value=rec["amount"])
            account_cells.setdefault(rec["account"], []).append(f"Ledger!C{row_idx}")

    # Capital & Dilution schedule for raw mode
    if raw:
        ws_cap = wb.create_sheet("Capital")
        _,peer_rows=plan_and_peers(pub)
        note_text = (pub / "treasury_note.md").read_text()
        basic_shares = float(re.search(r"outstanding:\s*([\d.]+)\s*shares", note_text).group(1))
        mkt_quote = float(re.search(r"quote:\s*EUR\s*([\d.]+)", note_text).group(1))
        opt_matches = re.findall(r"([\d.]+)\s*options at EUR\s*([\d.]+)", note_text)

        last_peer_row = 3 + len(peer_rows)
        basic_row = last_peer_row + 3
        quote_row = basic_row + 1
        opt_hdr_row = quote_row + 2
        opt_start = opt_hdr_row + 1
        opt_end = opt_start + len(opt_matches) - 1

        style_sheet(ws_cap, opt_end + 2, 5)
        ws_cap["A1"] = "Capital and dilution"
        for j, h in enumerate(["FY2025 peer", "Equity beta", "D/E", "Tax rate", "Asset beta"], start=1):
            ws_cap.cell(row=3, column=j, value=h)
        for idx, rec in enumerate(peer_rows):
            r = 4 + idx
            ws_cap.cell(row=r, column=1, value=rec["peer"])
            ws_cap.cell(row=r, column=2, value=float(rec["observed_equity_beta"]))
            ws_cap.cell(row=r, column=3, value=float(rec["net_debt_to_equity_x"]))
            tax_cell = ws_cap.cell(row=r, column=4, value=float(rec["statutory_tax_pct"]) / 100.0)
            tax_cell.number_format = NF_PCT
            ws_cap.cell(row=r, column=5, value=f"=B{r}/(1+(1-D{r})*C{r})")

        ws_cap.cell(row=basic_row, column=1, value="Basic shares (millions)")
        ws_cap.cell(row=basic_row, column=2, value=basic_shares / 1e6)
        ws_cap.cell(row=quote_row, column=1, value="Market quote (EUR)")
        ws_cap.cell(row=quote_row, column=2, value=mkt_quote)

        for j, h in enumerate(["Option tranche", "Count (millions)", "Strike (EUR)", "Incremental shares"], start=1):
            cell = ws_cap.cell(row=opt_hdr_row, column=j, value=h)
            cell.fill = HEADER_FILL
            cell.font = FONT_HEADER
        for idx, (cnt_str, stk_str) in enumerate(opt_matches):
            r = opt_start + idx
            ws_cap.cell(row=r, column=1, value=f"Tranche {idx + 1}")
            ws_cap.cell(row=r, column=2, value=float(cnt_str) / 1e6)
            ws_cap.cell(row=r, column=3, value=float(stk_str.rstrip(".")))
            ws_cap.cell(row=r, column=4, value=f"=MAX(0,1-C{r}/$B${quote_row})*B{r}")

        for j, label in enumerate(
            ["Relevered equity beta", "Diluted shares (millions)", "Median asset beta", "TSM incremental shares"]
        ):
            ws_dcf.cell(row=12 + j, column=1, value=label)

        ws_dcf["B14"] = f"=MEDIAN(Capital!E4:E{last_peer_row})"
        ws_dcf["B12"] = f"=B14*(1+(1-{inp_ref('tax_rate')})*{inp_ref('debt_weight')}/(1-{inp_ref('debt_weight')}))"
        ws_dcf["B15"] = f"=SUM(Capital!D{opt_start}:D{opt_end})"
        ws_dcf["B13"] = f"=Capital!B{basic_row}+B15"

        ws_in[f"B{4 + sc_keys.index('beta')}"] = "=DCF!B12"
        ws_in[f"B{4 + sc_keys.index('shares')}"] = "=DCF!B13"

    for idx, label in enumerate(STATEMENT_LABELS):
        ws_stmt.cell(row=4 + idx, column=1, value=label)

    hist_map = {
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
    }
    for row_num, key in hist_map.items():
        ws_stmt[f"B{row_num}"] = "=" + "+".join(account_cells[key])

    ws_stmt["B4"] = "=" + inp_ref("opening_units")
    ws_stmt["B10"] = "=B6-B7-B8-B9"
    ws_stmt["B13"] = "=B10-B11-B12"
    ws_stmt["B17"] = "=B14+B15-B16"
    ws_stmt["B24"] = "=B22+B14+B15+B19"
    ws_stmt["B25"] = "=B16+B20+B23"

    for t in range(5):
        col = "CDEFG"[t]
        prev = "BCDEF"[t]

        def q(r):
            return f"{col}{r}"

        def p(r):
            return f"{prev}{r}"

        def dr(k):
            return f"Inputs!{col}{21 + series_keys.index(k)}"

        a, b, c = dr("A"), dr("B"), dr("C")
        u = p(4)
        old = f"{u}*(1-{b})"
        end = q(4)

        op_formulas = {
            "saas": (f"{old}+{a}", f"({u}+{end})/2*(1+{c})"),
            "foundry": (f"{u}+{a}", f"MIN({end},{b})*{c}"),
            "orders": (f"{u}+{a}-{q(5)}", f"{u}*{b}+{a}*{c}"),
            "storage": (f"{old}+MIN({a},MAX(0,{c}-{old}))", f"{old}+({end}-{old})/2"),
            "fleet": (f"{old}+{a}", f"({old}+{a}/2)*{c}"),
            "license": (f"{u}*{b}+{a}", f"{u}*{b}+{a}/2+{a}*{c}"),
            "mine": (f"MAX(0,{u}+{a}-{b})", f"({u}+{a}-{end})*{c}"),
            "retail": (f"{old}+{a}", f"{old}+{a}*{c}"),
            "royalty": (f"{u}+{a}", f"MAX({u}*0.9,MIN({end},{b})+MAX(0,{end}-{b})*{c})"),
            "returns": (f"{old}+{a}", f"{old}+{a}/2-{c}*{u}*0.4"),
        }[d["slug"]]

        mid_adj = "-0.5" if d["timing"] == "midyear" else ""
        formulas = {
            4: op_formulas[0],
            5: op_formulas[1],
            6: f"{q(5)}*{dr('unit_price')}*{inp_ref('price_multiplier')}",
            7: f"{q(6)}*{dr('cogs_pct')}",
            8: dr("opex_fixed"),
            9: f"({p(19)}+{q(18)}/2)*{inp_ref('dep_rate')}",
            10: f"{q(6)}-SUM({q(7)}:{q(9)})",
            11: f"AVERAGE({p(20)},{q(20)})*{inp_ref('debt_cost')}",
            12: f"MAX(0,{q(10)}-{q(11)})*{inp_ref('tax_rate')}",
            13: f"{q(10)}-{q(11)}-{q(12)}",
            14: f"{q(6)}*({dr('dso')}+{inp_ref('dso_shift')})/365",
            15: f"{q(7)}*{dr('dio')}/365",
            16: f"{q(7)}*{dr('dpo')}/365",
            17: f"{q(14)}+{q(15)}-{q(16)}",
            18: f"{q(6)}*{dr('capex_pct')}",
            19: f"{p(19)}+{q(18)}-{q(9)}",
            20: f"{p(20)}-{q(21)}",
            21: f"MIN({p(20)},{dr('repay')})",
            22: f"{p(22)}+{q(29)}",
            23: f"{p(23)}+{q(13)}",
            24: f"{q(14)}+{q(15)}+{q(19)}+{q(22)}",
            25: f"{q(16)}+{q(20)}+{q(23)}",
            26: f"{q(13)}+{q(9)}-{q(31)}",
            27: f"-{q(18)}",
            28: f"-{q(21)}",
            29: f"SUM({q(26)}:{q(28)})",
            30: f"MAX(0,{q(10)})*{inp_ref('tax_rate')}",
            31: f"{q(17)}-{p(17)}",
            32: f"{q(10)}-{q(30)}+{q(9)}-{q(18)}-{q(31)}",
            33: f"{q(32)}/(1+DCF!$B$4)^({col}3-$B$3{mid_adj})",
        }
        for row_num, expr in formulas.items():
            ws_stmt[f"{col}{row_num}"] = "=" + expr

    dcf_labels = [
        "WACC",
        "Terminal value (FY2030 close)",
        "PV of terminal value",
        "Enterprise value",
        "Equity value",
        "Value per diluted share (EUR)",
    ]
    for idx, label in enumerate(dcf_labels):
        ws_dcf.cell(row=4 + idx, column=1, value=label)

    ke_expr = f"{inp_ref('risk_free')}+{inp_ref('beta')}*{inp_ref('erp')}"
    tv_expr = (
        f"Statements!G32*(1+{inp_ref('g')})/(B4-{inp_ref('g')})"
        if d["terminal"] == "perpetuity"
        else f"(Statements!G10+Statements!G9)*{inp_ref('exit_multiple')}"
    )
    dcf_formulas = [
        f"({ke_expr})*(1-{inp_ref('debt_weight')})+{inp_ref('debt_cost')}*(1-{inp_ref('tax_rate')})*{inp_ref('debt_weight')}",
        tv_expr,
        "B5/(1+B4)^5",
        "SUM(Statements!C33:G33)+B6",
        "B7+Statements!B22-Statements!B20",
        f"B8/{inp_ref('shares')}",
    ]
    for idx, expr in enumerate(dcf_formulas):
        ws_dcf[f"B{4 + idx}"] = "=" + expr
    ws_dcf["B4"].number_format = NF_PCT
    for r in (7, 8, 9):
        ws_dcf[f"A{r}"].font = FONT_BOLD
        ws_dcf[f"B{r}"].font = FONT_BOLD

    for rr in (6, 10, 13, 17, 24, 25, 29, 32, 33):
        for c_idx in range(1, 8):
            ws_stmt.cell(row=rr, column=c_idx).fill = SUB_FILL
    ws_stmt.freeze_panes = "A4"

    out_path = root / "solution/reference.xlsx"
    wb.save(out_path)
    print(f"built {root.name} (public-exhibits-only={raw}) -> {out_path}")


def main(target_dir: Path):
    for task in sorted(target_dir.glob("dcf-*")):
        if task.is_dir():
            build_task_workbook(task)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("DCFEval"))
