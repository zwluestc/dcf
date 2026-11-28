"""Read only a published snapshot. Never import author code or the verifier."""
from datetime import date
from pathlib import Path
import argparse
import json


def solve(folder, mistake=False):
    request=json.loads((folder/"request.json").read_text())
    docs=[json.loads(s) for s in (folder/"corpus.jsonl").read_text().splitlines()]
    current=[d for d in docs if d["coverage"]==request["coverage"] and d["period"]==request["period"]
             and d["date"]<=request["cutoff"] and d["edition"]=="filed"]
    def document(suffix):
        d,=[d for d in current if d["title"].endswith(suffix)]
        rows={}
        for line in d["text"].splitlines():
            if line.startswith("|"):
                key,value=line.strip("|").split("|")
                try: value=float(value)
                except ValueError: value=value.strip()
                rows[key.strip()]=value
        return d["id"],rows
    fields={}
    def put(key,value,*ids):
        fields[key]={"value":value,"sources":list(ids)}
    family=request["task_id"].split("-")[0]
    if family=="foundry":
        a,x=document("annual operating supplement"); b,y=document("audited fab statistics"); m,_=document("comparability bulletin")
        first=x["Dispatches"]-x["Captive transfers"]; second=(y["Dispatches"]-y["Group warehouse"])*(1 if mistake else (200/300)**2)
        names=[next(d["publisher"] for d in current if d["id"]==k) for k in (a,b)]
        put("a_external",first,a); put("b_external",second,b,m)
        put("a_share_pct",100/(1+second/first),a,b,m)
        put("leader",names[int(second>first)],a,b,m);put("physical_count_bias",names[1],a,b,m)
    elif family=="retail":
        a,x=document("prior year store accounts");b,y=document("consolidated annual accounts");m,z=document("perimeter reconciliation")
        old=x["Net sales"];now=y["Net sales"]; drop=z["Closures prior"]/1000; add=z["Openings current"]/1000
        reported=(now-old)/old*100
        organic=reported if mistake else ((now-add)/(old-drop)-1)*100
        put("reported_pct",reported,a,b);put("comparable_pct",organic,a,b,m);put("gap_pp",reported-organic,a,b,m)
        put("perimeter_net",add-drop,m);put("readthrough","masked_contraction" if organic<0 else "comparable_growth",a,b,m)
    elif family=="wind":
        a,x=document("final awards");b,y=document("JV interests");m,z=document("binding instruments register")
        ok=[lot for lot in x if z[lot]=="executed" or mistake]
        equity={k:v*y[k]/100 for k,v in x.items()}
        bank=sum(equity[k] for k in ok);pending=sum(equity.values())-bank
        put("awarded_gross",sum(x.values()),a);put("bankable_equity",bank,a,b,m);put("watch_equity",pending,a,b,m)
        put("conversion_pct",100*bank/sum(equity.values()),a,b,m)
        put("next_catalyst",next((k.split()[-1] for k in x if k not in ok),"none"),m)
    elif family=="smelter":
        a,x=document("feed contract register");b,y=document("settlement circular");m,z=document("lender sensitivity sheet")
        exposed=x["Dry feed tonnes"]*(1 if mistake else x["Indexed share pct"]/100)
        loss=exposed/1e6*(y["Previous rate"]-y["Reset rate"]);post=z["Base EBITDA"]-loss*z["FX"]
        put("exposed_tonnes",exposed,a);put("loss_usd_m",loss,a,b);put("post_cny_m",post,a,b,m)
        buffer=post-z["Minimum EBITDA"];put("headroom_cny_m",buffer,a,b,m);put("test","clear" if buffer>=0 else "breach",a,b,m)
    elif family=="port":
        a,x=document("port authority annual abstract");b,y=document("customs transshipment series");m,z=document("signed customs corrigendum")
        if not mistake: y["Q2"]=z["Q2 replacement"]/1000
        ytd=[x[k]-y[k] for k in ("Q1","Q2","Q3","Q4")]
        quarters=[v-u for u,v in zip([0]+ytd,ytd)]
        put("q2_local",quarters[1],a,b,m);put("q3_local",quarters[2],a,b,m)
        put("peak_quarter",f"Q{1+quarters.index(max(quarters))}",a,b,m);put("peak_local",max(quarters),a,b,m)
        put("annual_local",ytd[-1],a,b)
    elif family=="insurer":
        a,x=document("definitive bid notice");b,y=document("exchange closing tape");m,z=document("clearance order");s,v=document("settlement register")
        offer=x["Cash cents"]/100; p=y[x["Unaffected date"]+" close"]
        put("cash_per_share",offer,a);put("premium_pct",(offer-p)*100/p,a,b);put("approval_date",z["Approval"],m)
        done=mistake or v["State"]=="completed"; end=z["Approval"] if mistake else v["Title transfer"]
        put("completion_date",end if done else "unconfirmed",s)
        age=(date.fromisoformat(end)-date.fromisoformat(x["Announcement"])).days if done else "unconfirmed"
        put("elapsed_days",age,*([a,s] if done else [s]))
    elif family=="battery":
        d,loads=document("cell load outlook"); u,bom=document("separator bill of materials")
        s,base=document("incumbent supply census"); l,x=document("commissioning ledger")
        q,approvals=document("customer release docket")
        demand=(loads["Funded base"]+loads["Subsidy increment"])*bom["Intensity"]
        effective={k:x[k+" nameplate"]*x[k+" ramp pct"]/100 for k in ("A","B")}
        supply=base["Incumbent shipments"]/1000+sum(v for k,v in effective.items() if approvals[k]=="accepted" or mistake)
        released=base["Incumbent shipments"]/1000+sum(effective.values())-demand
        put("demand_m",demand,d,u);put("supply_m",supply,s,l,q)
        put("base_balance_m",supply-demand,d,u,s,l,q)
        put("no_subsidy_balance_m",supply-loads["Funded base"]*bom["Intensity"],d,u,s,l,q)
        put("release_balance_m",released,d,u,s,l,q)
        put("catalyst_readthrough","closes_gap" if released>=0 else "residual_shortage",d,u,s,l,q)
    else: raise ValueError(family)
    return {"cutoff":request["cutoff"],"findings":fields}


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("folder",type=Path);p.add_argument("out",type=Path)
    args=p.parse_args(); args.out.write_text(json.dumps(solve(args.folder),ensure_ascii=False,indent=2)+"\n")
