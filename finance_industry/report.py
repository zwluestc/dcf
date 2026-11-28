"""Render a candidate's Harbor output as a cited FinanceGym-shaped report record."""
import argparse
import json
from pathlib import Path
import re


def render(data, answer):
    request=json.loads((data/"request.json").read_text())
    corpus={d["id"]:d for s in (data/"corpus.jsonl").read_text().splitlines() if (d:=json.loads(s))}
    if answer["cutoff"]!=request["cutoff"]: raise ValueError("cutoff mismatch")
    labels=dict(re.findall(r"^- `([^\x60]+)`：(.*)$",request["question"],re.M))
    rows=[f"# {request['question'].splitlines()[0]}",f"研究截止日：{request['cutoff']}",""]
    for key,title in labels.items():
        f=answer["findings"][key];v=f["value"]
        value=f"{v:,.2f}" if type(v) in (int,float) else str(v)
        refs=" ".join(f"[{s}]({corpus[s]['url']})" for s in f["sources"])
        rows.append(f"- {title.rstrip('。')}：**{value}**。{refs}")
    rows.extend(["","来源（本地模拟披露；链接为文档标识）：",""])
    for s in sorted({s for k in labels for s in answer["findings"][k]["sources"]}):
        d=corpus[s];rows.append(f"- `{s}` · {d['date']} · {d['title']}")
    return dict(question=request["question"],cutoff=request["cutoff"],report="\n".join(rows))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("data",type=Path);p.add_argument("answer",type=Path)
    p.add_argument("--markdown",action="store_true");args=p.parse_args()
    out=render(args.data,json.loads(args.answer.read_text()))
    print(out["report"] if args.markdown else json.dumps(out,ensure_ascii=False))
