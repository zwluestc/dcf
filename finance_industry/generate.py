"""Emit self-contained Harbor tasks and a FinanceGym-shaped public question list."""
import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import re
import shutil

from scenarios import Case, KINDS

HERE=Path(__file__).resolve().parent
STYLE={"foundry":"Finance Agent Benchmark","retail":"Finance Agent Benchmark",
       "wind":"FrontierFinance (Samaya)","smelter":"FrontierFinance (Samaya)",
       "port":"FinSearchComp","insurer":"FinSearchComp","battery":"FrontierFinance (Samaya)"}


def dump(f,x):
    f.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n")


def lines(f,x):
    f.write_text("".join(json.dumps(v,ensure_ascii=False)+"\n" for v in x))


def decorate(c):
    scope=c.names[0]+" / "+c.kind; period=f"FY{c.year}"
    for d in c.docs: d.update(coverage=scope, period=period,edition="filed")
    real=[d for d in c.docs if d["date"]<=c.cutoff.isoformat()]
    # Plausible stale-period records and previews, with distinct values, not repeated answer keys.
    for orig in real:
        for old in (True,False):
            age=(c.cutoff-date.fromisoformat(orig["date"])).days
            body=re.sub(r"(\| )(-?\d+(?:\.\d+)?)( \|)",lambda m:f"| {round(float(m[2])*1.07+1,2)} |",orig["text"])
            if body==orig["text"]:
                # Do not claim to publish a different dated event with identical evidence.
                continue
            if old:
                body=re.sub(r"\b\d{4}-\d{2}-\d{2}\b",lambda m:str(date.fromisoformat(m[0])-timedelta(days=365)),body)
            else:
                body="Provisional planning assumptions, subject to change.\n"+body
            c.doc(orig["title"],body,age+(365 if old else 8),orig["publisher"])
            c.docs[-1].update(coverage=scope,period=f"FY{c.year-1}" if old else period,
                              edition="filed" if old else "preliminary")
    for i,name in enumerate(["Jade Fold","Birch Fen","Ash Harbour"]):
        for orig in real[:3]:
            title=orig["title"]; body=orig["text"]; pub=orig["publisher"]
            for j,n in enumerate(c.names):
                repl=name if j==0 else ["Linen Cut","Iron Cove","Chalk Run"][(i+j)%3]
                title=title.replace(n,repl);body=body.replace(n,repl);pub=pub.replace(n,repl)
            body=re.sub(r"(\| )(\d+(?:\.\d+)?)( \|)",lambda m:f"| {round(float(m[2])*(0.81+i*.04),2)} |",body)
            c.doc(title,body,12+i,pub)
            c.docs[-1].update(coverage=name+" / "+c.kind,period=period,edition="filed")
    c.r.shuffle(c.docs)
    return scope,period


def build(out,seed,variants):
    if out.exists() and any(out.iterdir()): raise ValueError("output directory must be new or empty")
    (out/"tasks").mkdir(parents=True);(out/"author").mkdir()
    manifest=[];qs=[]
    for family,fn in KINDS.items():
        for v in range(variants):
            c=Case(family,seed,v);fn(c);scope,period=decorate(c)
            cutoff=str(c.cutoff); visible=[d for d in c.docs if d["date"]<=cutoff]
            task=out/"tasks"/c.id
            for sub in ["environment/data","solution","tests"]: (task/sub).mkdir(parents=True)
            fields="\n".join(f"- `{k}`：{x['ask']}。" for k,x in c.claims.items())
            question=f"{c.title}\n\n{c.brief}\n\n覆盖组：{scope}；档期：{period}；研究截止日（含当日）：{cutoff}。同档期正式稿优先于预告；文件发布日期与其所述事项的发生日分开。\n\n请逐项回答：\n{fields}"
            req=dict(task_id=c.id,question=question,cutoff=cutoff)
            qs.append(req);data=task/"environment/data"
            dump(data/"request.json",dict(**req,coverage=scope,period=period))
            lines(data/"corpus.jsonl",visible)
            lines(out/"author"/(c.id+".future.jsonl"),[d for d in c.docs if d["date"]>cutoff])
            (task/"instruction.md").write_text(question+'''

这些是原创的虚构公司、机构和披露。所有作答依据均在 /work/data/corpus.jsonl；仅使用对应覆盖组、档期及适用口径的资料。检索示例：`python /work/archive.py search "settlement" -k 5`，按 ID 读全文：`python /work/archive.py fetch ID`。也可自行读取文件。档期是研究归档标签，历史对照和后续事件的具体期间以正文为准。

提交 /work/answer.json，顶层填写 cutoff 和 findings。每个问题键对应 {"value": 数字或约定文本, "sources": ["文档ID", ...]}。数值不带单位、百分数不写百分号，保留至少两位小数的精度。每项列出支持该结论的直接正式资料：派生结论覆盖每个输入、两家比较覆盖两家的原始材料、涉及片径换算包括行业口径；无需引用背景、重复或无关材料。引用不计顺序。每项等权，答案正确得本项 60%，此时引用集合也正确再得 40%；数值绝对误差不超过 0.01。截止日错误或缺少有效交付物时总分为零。
''')
            (task/"task.toml").write_text(f'''schema_version = "1.4"
artifacts = ["/work/answer.json"]
[task]
name = "industry-research/{c.id}"
description = "{c.title}"
[agent]
timeout_sec = 600
[environment]
cpus = 1
memory_mb = 512
storage_mb = 1024
network_mode = "no-network"
workdir = "/work"
[verifier]
timeout_sec = 60
environment_mode = "separate"
[verifier.environment]
cpus = 1
memory_mb = 512
network_mode = "no-network"
workdir = "/tests"
''')
            (task/"environment/Dockerfile").write_text("FROM python:3.12.8-slim-bookworm\nWORKDIR /work\nCOPY archive.py /work/archive.py\nCOPY data /work/data\n")
            shutil.copyfile(HERE/"retrieval.py",task/"environment/archive.py")
            shutil.copyfile(HERE/"reference.py",task/"solution/reference.py")
            shutil.copyfile(HERE/"grade.py",task/"tests/grade.py")
            (task/"solution/solve.sh").write_text("#!/bin/sh\nset -eu\npython3 /solution/reference.py /work/data /work/answer.json\n")
            (task/"tests/test.sh").write_text("#!/bin/sh\nset -eu\npython3 /tests/grade.py /work/answer.json /tests/gold.json /logs/verifier\n")
            for f in ["solution/solve.sh","tests/test.sh"]: (task/f).chmod(0o755)
            dump(task/"tests/gold.json",dict(cutoff=cutoff,claims={k:{"sources":s["sources"],"value":s["value"]} for k,s in c.claims.items()}))
            manifest.append(dict(task_id=c.id,family=family,title=c.title,aligned_to=STYLE[family],
                                 docs_visible=len(visible),docs_withheld=len(c.docs)-len(visible),
                                 corpus_sha256=hashlib.sha256((data/"corpus.jsonl").read_bytes()).hexdigest()))
    lines(out/"financegym_questions.jsonl",qs)
    dump(out/"manifest.json",dict(source="original synthetic disclosures",oracle_kind="derived_target",
                                  seed=seed,variants_per_family=variants,tasks=manifest))


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);p.add_argument("--seed",type=int,default=736041)
    p.add_argument("--variants",type=int,default=2);a=p.parse_args()
    if a.variants<1: p.error("variants must be positive")
    build(a.out,a.seed,a.variants)
