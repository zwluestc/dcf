"""Synthetic annual filings and signed source documents used by the v1 suite."""
import csv
import random
import re
from decimal import Decimal


# Captions are terms as reported by the subsidiaries. No standardized ledger is public.
LINES = {
    "4100": ("IS01", "Customer billings"),
    "5105": ("IS02", "Direct fulfilment costs"),
    "6202": ("IS03", "Selling and administration"),
    "6710": ("IS04", "Depreciation"),
    "7102": ("IS05", "Finance expense"),
    "7900": ("IS06", "Current tax expense"),
    "1210": ("BS01", "Customer receivables"),
    "1320": ("BS02", "Merchandise on hand"),
    "2315": ("BS03", "Trade creditors"),
    "1520": ("BS04", "Operating plant, net"),
    "1015": ("BS05", "Cash at bank"),
    "3105": ("BS06", "Closing book capital"),
    "2112": ("N04", "Facility payable within one year"),
    "2710": ("N03-N04", "Non-current facility"),
}
BUDGET_FIELDS = ("cash_cost_pct_of_sales", "fixed_expense_EUR_thousands", "investment_pct_of_sales",
                 "collection_days", "stock_days", "supplier_days", "debt_amort_EUR_thousands")
PEER_FIELDS = ("peer", "observed_equity_beta", "net_debt_to_equity_x", "statutory_tax_pct")


def overhaul(pub, company, seed):
    rng = random.Random(seed)
    evidence = {}
    for site in ("North", "South"):
        slug = site.lower()
        local = pub / (slug + "_close.csv")
        with local.open() as stream:
            rows = list(csv.DictReader(stream))
        field = next(f for f in rows[0] if f.startswith("amount_"))
        source = {r["account"]: Decimal(r[field]) for r in rows if r["status"]=="POSTED"}
        scale = 1000 if site=="North" else 1000000
        def show(n):
            v = format(abs(n), ",f")
            if "." in v:
                v = v.rstrip("0").rstrip(".")
            if site=="South":
                v = v.translate(str.maketrans({",":" ", ".":","}))
            return "(" + v + ")" if n < 0 else v

        filename = slug + "_annual_report.txt"
        lines = [f"{company} | {site} subsidiary | FY2025 annual financial report",
                 "Statement release dated 28 February 2026. Calendar-year accounts.",
                 ("Presentation currency: thousands of EUR. Commas group thousands; dot is decimal."
                  if site=="North" else "Presentation currency: EUR. Spaces group thousands; comma is decimal."),
                 "Profit or loss expenses are shown in parentheses. Cost schedules use expense magnitudes.",
                 "Each comparative is FY2024. Flows span twelve months. Balances are at 31 December.",
                 "Use the signed amendment in note N01 for billings. Debt in BS07 is the total facility.", ""]
        prev = {k:v*Decimal("0.91") for k,v in source.items()}
        bill_before = source["4100"] + Decimal(scale)*Decimal("0.37")
        for heading,prefix in (("Statement of profit or loss","IS"),("Statement of financial position","BS")):
            lines.append(heading)
            for k,(ref,caption) in LINES.items():
                if not ref.startswith(prefix): continue
                amount = bill_before if k=="4100" else source[k]
                sign = -1 if ref.startswith("IS") and k!="4100" else 1
                lines.append(f"[{ref}] {caption}. FY2024 comparative {show(sign*prev[k])}. FY2025 reported {show(sign*amount)}.")
            if prefix=="BS":
                lines.append(f"[BS07] Borrowings, current and non-current together. FY2025 reported {show(source['2112']+source['2710'])}.")
                clearing = sum(source[k] for k in ("1015","1210","1320","1520"))-sum(source[k] for k in ("2315","2112","2710","3105"))
                lines.append(f"[BS08] Interoffice clearing {'payable' if clearing>=0 else 'receivable'}: {show(abs(clearing))}. Eliminated on group consolidation.")
            lines.append("")
        lines += ["Notes and subsequent amendment",
                  f"[N01] Signed amendment, 14 March 2026. For FY2025, replace IS01 with {show(source['4100'])}. Do not add both releases.",
                  f"[N03] Audited facility principal outstanding at 31 December 2025 totals {show(source['2112']+source['2710'])}.",
                  f"[N04] Included in N03, the principal due within the next twelve months is {show(source['2112'])}.",
                  "The remainder of N03 is non-current. Both portions bear interest. Trade creditors exclude the facility.",
                  f"[M01] Prior unsigned credit proposal: projected new facility {show(source['2112']*2)}. It was never drawn."]
        (pub/filename).write_text("\n".join(lines)+"\n")
        local.unlink()
        for k,(ref,_) in LINES.items():
            cite=filename+"#"+("N01" if k=="4100" else ref)
            evidence[cite] = [float(source[k]), scale, float(source[k]/scale)]

    def convert_csv(name, dest, heading, render):
        file = pub/name
        with file.open() as stream: rows = list(csv.DictReader(stream))
        rng.shuffle(rows)
        (pub/dest).write_text(heading+"\n\n"+"\n".join(render(r) for r in rows)+"\n")
        file.unlink()
    convert_csv("finance_budget.csv","budget_approval.txt","Board minutes | Approved operating plan",
                lambda r: f"For FY{r['fy']} the approved expense is EUR {r['fixed_expense_EUR_thousands']} thousand. Cash costs absorb {r['cash_cost_pct_of_sales']}% of sales and investment absorbs {r['investment_pct_of_sales']}%. Collect in {r['collection_days']} days, hold stock for {r['stock_days']} days and pay suppliers in {r['supplier_days']} days. Scheduled principal is EUR {r['debt_amort_EUR_thousands']} thousand.")
    convert_csv("peer_set.csv","peer_research.txt","Treasury research | Market observations",
                lambda r: f"{r['peer']} reports an observed equity beta of {r['observed_equity_beta']}. Net debt/equity is {r['net_debt_to_equity_x']}x and the statutory tax rate is {r['statutory_tax_pct']}%.")
    return evidence


def read_ledger(pub, site):
    """Extract FY2025 values using filing hierarchy, units and maturity note."""
    name=site.lower()+"_annual_report.txt"
    if not (pub/name).exists():  # pre-v1 source packs
        with (pub/(site.lower()+"_close.csv")).open() as f:
            rows=[r for r in csv.DictReader(f) if r["status"]=="POSTED"]
        return [(r["account"],float(r[next(k for k in r if k.startswith("amount_"))]),
                 1000 if site=="North" else 1000000,"") for r in rows]
    text=(pub/name).read_text()
    scale=1000 if "currency: thousands of EUR" in text else 1000000
    notes=dict(re.findall(r'^\[([^\]]+)\] (.+)$',text,re.M))
    def amount(note, phrase):
        value=re.search(re.escape(phrase)+r' (\(?[\d,. ]+\)?)\.',notes[note])[1].strip("() ")
        value=value.replace(",","") if scale==1000 else value.replace(" ","").replace(",",".")
        return Decimal(value)
    result=[]
    for code,(ref,_) in LINES.items():
        if code=="4100":
            ref="N01"; v=amount(ref,"replace IS01 with")
        elif code in ("2112","2710"):
            current=amount("N04","next twelve months is")
            v=current if code=="2112" else amount("N03","2025 totals")-current
        else:
            v=amount(ref,"FY2025 reported")
        result.append((code,float(v),scale,name+"#"+ref))
    return result


def plan_and_peers(pub):
    if not (pub/"budget_approval.txt").exists():
        def csv_rows(file):
            with (pub/file).open() as stream: return list(csv.DictReader(stream))
        return csv_rows("finance_budget.csv"),csv_rows("peer_set.csv")
    plan=[]
    for line in (pub/"budget_approval.txt").read_text().splitlines():
        if not line.startswith("For FY"): continue
        year,expense,cost,investment,collection,stock,pay,repay=re.findall(r'\d+(?:\.\d+)?',line)
        plan.append(dict(fy=year,**dict(zip(BUDGET_FIELDS,(cost,expense,investment,collection,stock,pay,repay)))))
    market=[]
    for line in (pub/"peer_research.txt").read_text().splitlines():
        if "reports an observed" not in line: continue
        beta,lev,tax=re.findall(r'\d+(?:\.\d+)?',line)
        market.append(dict(zip(PEER_FIELDS,(line.split()[0],beta,lev,tax))))
    assert sorted(r["fy"] for r in plan)==list(map(str,range(2026,2031))) and len(market) in (3,5)
    return plan,market
