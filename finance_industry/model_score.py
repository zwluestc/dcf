"""Score saved model submissions offline with the released verifier and unchanged gold."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from grade import grade
from model_eval import PACKS,ROOT,write


def score(out,partial=False):
    protocol=json.loads((out/"protocol.json").read_text())
    rows=[];failure=[];tokens=Counter();models=Counter();calls=0
    for pack,filename in PACKS.items():
        with ZipFile(ROOT.parent/"exports"/filename) as z:
            for member in sorted(n for n in z.namelist() if n.endswith("/tests/gold.json")):
                tid=member.split("/")[0];file=out/(tid+".json")
                if not file.exists():
                    if partial:continue
                    raise ValueError(f"Missing {tid}")
                assert z.read(tid+"/tests/grade.py")==Path(__file__).with_name("grade.py").read_bytes()
                rec=json.loads(file.read_text());assert rec["pack"]==pack and rec["task"]==tid
                assert rec["corpus_sha256"]==hashlib.sha256(z.read(tid+"/environment/data/corpus.jsonl")).hexdigest()
                for s in rec["steps"]:
                    usage=s.get("usage") or {};models[s.get("model")]+=1;calls+=1
                    tokens.update({k:usage[k] for k in ("prompt_tokens","completion_tokens") if k in usage})
                if rec["status"]=="infrastructure_error":
                    failure.append({"task":tid,"error":rec.get("error")});continue
                gold=json.loads(z.read(member)); answer=rec["answer"]
                val,detail=grade(answer,gold)
                claims=[]
                for k,spec in gold["claims"].items():
                    raw=detail.get(k,{});ok=bool(raw.get("value_ok"));ref=bool(raw.get("evidence_ok"))
                    submission=((answer or {}).get("findings") or {})
                    obj=submission.get(k,{}) if isinstance(submission,dict) else {}
                    obj=obj if isinstance(obj,dict) else {}
                    claims.append(dict(key=k,value_ok=ok,refs_ok=ref,**({} if ok and ref else
                                {"expected":spec,"submitted":obj})))
                rows.append(dict(task=tid,pack=pack,family=tid.split("-")[0],score=val,claims=claims,
                                 status=rec["status"],docs_read=len({i for s in rec["steps"] for i in s.get("fetched",[])})))
    def agg(items):
        c=[v for r in items for v in r["claims"]]
        return dict(n=len(items),full=sum(r["score"]==1 for r in items),
                    avg_score=round(sum(r["score"] for r in items)/len(items),6) if items else None,
                    all_values=sum(all(v["value_ok"] for v in r["claims"]) for r in items),
                    claims=len(c),values_ok=sum(v["value_ok"] for v in c),refs_ok=sum(v["refs_ok"] for v in c),
                    joint_ok=sum(v["refs_ok"] and v["value_ok"] for v in c))
    counts=Counter()
    for r in rows:
        for v in r["claims"]:
            if not v["refs_ok"] or not v["value_ok"]:
                counts[(r["family"],v["key"],v["value_ok"],v["refs_ok"])]+=1
    result=dict(overall=agg(rows),by_pack={k:agg([r for r in rows if r["pack"]==k]) for k in PACKS},
                by_family={k:agg([r for r in rows if r["family"]==k]) for k in sorted({r["family"] for r in rows})},
                calls=calls,tokens=dict(tokens),models=dict(models),infrastructure_errors=failure,
                missed_items=[dict(family=f,key=k,value_ok=v,refs_ok=s,n=n) for (f,k,v,s),n in counts.most_common()])
    print(json.dumps(result["overall"],ensure_ascii=False))
    if partial:return
    write(out/"scores.json",dict(**result,rows=rows))
    a=result["overall"];n=a["n"];c=a["claims"]
    def frac(x,y):return f"{x}/{y} ({x/y:.1%})" if y else "无"
    md=["# DeepSeek Flash 1017 行业研究盲测","",f"网关指定模型：`{protocol['model']}`。42 个合成实例、7 种研究机制；"
        f"完成可评分 {n} 题，基础设施失败 {len(failure)} 题。每题新对话、一次交卷、无评分反馈。只给公开目录，模型可按 ID 分批取全文（最多 3 轮），"
        "未提供答案、搜索排序提示、Python 或联网浏览。使用已发布 Harbor grader 离线评分，没有在 Harbor 容器内调用模型。","",
        f"整题满分 {frac(a['full'],n)}；全题所有值正确 {frac(a['all_values'],n)}；子项值正确 {frac(a['values_ok'],c)}；"
        f"证据集合完全匹配 {frac(a['refs_ok'],c)}；值和证据同时正确 {frac(a['joint_ok'],c)}；逐题等权平均分 {a['avg_score']:.2%}。","",
        "| 分组 | 题数 | 整题满分 | 全部值正确 | 子项值正确 | 值与证据均对 | 平均分 |","|---|---:|---:|---:|---:|---:|---:|"]
    for k,b in {**result["by_pack"],**result["by_family"]}.items():
        if b["n"]:md.append(f"| {k} | {b['n']} | {b['full']} | {b['all_values']} | {b['values_ok']}/{b['claims']} | {b['joint_ok']}/{b['claims']} | {b['avg_score']:.1%} |")
    md+=["","## 失分项","","| 题型 | 子项 | 值正确 | 引用正确 | 次数 |","|---|---|---|---|---:|"]
    for e in result["missed_items"]:
        md.append(f"| {e['family']} | {e['key']} | {e['value_ok']} | {e['refs_ok']} | {e['n']} |")
    md+=["",f"模型回复数 {calls}；网关报告 token 数：{dict(tokens)}。未测多个采样种子。7 组题均为同机制变体，不能把分数外推为官方榜单成绩。",
         "","[逐题打分及失分时的原始答案对照](scores.json) · [请求设置](protocol.json)"]
    (out/"REPORT.md").write_text("\n".join(md)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("out",type=Path);p.add_argument("--partial",action="store_true");a=p.parse_args()
    score(a.out,a.partial)
