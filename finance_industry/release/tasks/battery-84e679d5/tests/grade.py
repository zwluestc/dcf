"""Grade only a candidate artifact; deterministic local partial credit."""
import json
import math
from pathlib import Path
import sys


def grade(answer, gold):
    if not isinstance(answer,dict) or answer.get("cutoff")!=gold["cutoff"] or not isinstance(answer.get("findings"),dict):
        return 0, {"error":"invalid or missing cutoff/findings"}
    detail={}
    for key,spec in gold["claims"].items():
        row=answer["findings"].get(key)
        row=row if isinstance(row,dict) else {}
        v=row.get("value");correct=spec["value"]
        if isinstance(correct,str):
            ok=isinstance(v,str) and v.strip().casefold()==correct.casefold()
        else:
            ok=type(v) in (int,float) and abs(v-correct)<=0.010000001
        refs=row.get("sources")
        cited=(isinstance(refs,list) and all(isinstance(s,str) for s in refs) and
               len(set(refs))==len(refs) and set(refs)==set(spec["sources"]))
        detail[key]={"value_ok":ok,"evidence_ok":cited,"points":(0.6+0.4*cited) if ok else 0}
    return round(sum(d["points"] for d in detail.values())/len(detail),6),detail


if __name__=="__main__":
    path,gold_path,logs=map(Path,sys.argv[1:])
    gold=json.loads(gold_path.read_text())
    try:
        if path.stat().st_size>1_000_000: raise ValueError("artifact exceeds 1 MB")
        score,detail=grade(json.loads(path.read_text()),gold)
    except (OSError,ValueError,OverflowError,RecursionError) as e:
        score,detail=0,{"error":str(e)}
    logs.mkdir(parents=True,exist_ok=True)
    (logs/"details.json").write_text(json.dumps(detail,indent=2)+"\n")
    (logs/"reward.txt").write_text(f"{score}\n")
