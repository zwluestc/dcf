"""Generate a functioning inherited analyst model, its previous version, and the repair contract."""
import json
from copy import copy
from openpyxl import load_workbook
from openpyxl.formula import Tokenizer
from openpyxl.workbook.defined_name import DefinedName

from grade import structure_fingerprint

# Three assignments per wave. Rotate industry mechanisms between successive waves.
SETS = ((2,5,9),(1,4,8))
BUGS = (
    ("WorkingCapital",14,"=Statements!{c}6*(Inputs!{c}28+Inputs!$B$5)/360"),
    ("Debt",11,"=Statements!{p}20*Inputs!$B$10"),
    ("FixedAssets",9,"=(Statements!{p}19+Statements!{c}18)*Inputs!$B$16"),
    ("CashFlow",26,"=Statements!{c}13+Statements!{c}9+Statements!{c}31"),
    ("Tax",30,"=MAX(0,Statements!{c}10-Statements!{c}11)*Inputs!$B$11"),
    ("Discounting",33,"=Statements!{c}32/(1+DCF!$B$4)^(Statements!{c}3-Statements!$B$3+0.5)"),
)
SCHEDULES = {"Operations":(4,5,6),"Margins":(7,8,10),"FixedAssets":(9,18,19),
             "Debt":(11,20,21),"Tax":(12,30),"WorkingCapital":(14,15,16,17,31),
             "CashFlow":(26,27,28,29,32),"BalanceSheet":(22,23,24,25),"Discounting":(33,)}
TASK_CONTRACT = """
## Inherited analyst model
Open prior_model.xlsx, update its previous close from the two signed filings, apply the latest approved assumptions in the CFO and treasury notes, diagnose internal calculation discrepancies, and save the repaired model as /work/output.xlsx. Preserve all 15 tabs, their order and visibility, named ranges, report labels and existing layout. Retain unaffected formulas, inputs and links. Correct the faulty formulas on their owning schedules. The existing Ledger rows specify the site and line item. Update their native amounts and source references from the current filings. The latest signed assumptions supersede the prior workbook. Deliver an editable model that also recalculates after subsequent input changes.
"""


def case_index(name):
    return int(name.split("-")[1])-1


def is_takeover(name):
    idx=case_index(name)
    return idx%10+1 in SETS[(idx//10)%2]


def qualify(formula):
    """Move a calculation out of Statements without changing any cell dependency."""
    tokens=Tokenizer(formula).items
    return "="+''.join("Statements!"+t.value if t.type=="OPERAND" and t.subtype=="RANGE" and "!" not in t.value else t.value for t in tokens)


def add_name(wb,name,dest):
    definition=DefinedName(name,attr_text=dest)
    if hasattr(wb.defined_names,"add"):
        wb.defined_names.add(definition)
    else:
        wb.defined_names.append(definition)


def install(task):
    if not is_takeover(task.name): return
    wb=load_workbook(task/"solution/reference.xlsx")
    st=wb["Statements"]
    for name,rows in SCHEDULES.items():
        ws=wb.create_sheet(name)
        ws["A1"]=name+" | analyst schedule"
        ws.column_dimensions["A"].width=37
        ws.freeze_panes="C4"
        for col in "BCDEFG":
            ws[col+"3"]=f"=Statements!{col}3"
            ws.column_dimensions[col].width=15
        for row in rows:
            ws[f"A{row}"]=st[f"A{row}"].value
            for col in "CDEFG":
                addr=col+str(row)
                ws[addr]=qualify(st[addr].value)
                ws[addr]._style=copy(st[addr]._style)
                st[addr]=f"={name}!{addr}"
    check=wb.create_sheet("Checks")
    check["A1"]="Forecast reconciliation | zero indicates agreement"
    check.merge_cells("A1:G1")
    check.column_dimensions["A"].width=38
    for row,label in enumerate(("Assets less liabilities and equity","Cash roll-forward difference","FCFF bridge difference"),4):
        check.cell(row,1,label)
    for c,p in zip("CDEFG","BCDEF"):
        check[c+"3"]=f"=Statements!{c}3"
        check[c+"4"]=f"=Statements!{c}24-Statements!{c}25"
        check[c+"5"]=f"=Statements!{c}22-Statements!{p}22-Statements!{c}29"
        check[c+"6"]=f"=Statements!{c}32-Statements!{c}10+Statements!{c}30-Statements!{c}9+Statements!{c}18+Statements!{c}31"
    wb["Discounting"].sheet_state="hidden"
    add_name(wb,"PriceMultiplier","'Inputs'!$B$4")
    add_name(wb,"EquityValue","'DCF'!$B$8")
    wb.save(task/"solution/reference.xlsx")
    idx=case_index(task.name)
    slots=SETS[(idx//10)%2]
    variant=(idx//10*3+slots.index(idx%10+1))%len(BUGS)
    sheet,row,wrong=BUGS[variant]
    col="CDEFG"[(idx//2)%5]; prev="BCDEF"[(idx//2)%5]
    address=col+str(row)
    wb[sheet][address]=wrong.format(c=col,p=prev)
    # A second internal error affects the valuation bridge, independent of the first.
    bridge="B6" if variant%2==0 else "B8"
    wb["DCF"][bridge]="=B5/(1+B4)^4.5" if bridge=="B6" else "=B7+Statements!B22-Statements!C20"
    for k,value in {"B4":0.97,"B5":-2,"B6":round(wb["Inputs"]["B6"].value-0.004,6)}.items():
        wb["Inputs"][k]=value
    editable={"Inputs":["B4","B5","B6"],"DCF":[bridge],sheet:[address],"Ledger":[]}
    for r in range(4,32):
        # Stale native amounts from the old close must be replaced using disclosures.
        # Do not provide the new numeric history or the amended references.
        wb["Ledger"][f"D{r}"]=round(wb["Ledger"][f"D{r}"].value*(0.88+((r*7+idx)%13)/100),3)
        wb["Ledger"][f"G{r}"]="Prior close"
        editable["Ledger"].extend([f"D{r}",f"G{r}"])
    starter=task/"environment/data/prior_model.xlsx"
    wb.save(starter)
    wb.close()
    with_spec=load_workbook(starter)
    contract={"editable":editable,"digest":structure_fingerprint(with_spec,editable)}
    with_spec.close()
    spec_path=task/"tests/answers.json"
    spec=json.loads(spec_path.read_text())
    spec["inherited"]=contract
    spec_path.write_text(json.dumps(spec,indent=2)+"\n")
