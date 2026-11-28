"""Blind catalog/fetch runner. The outbound path only reads two public ZIP members per task."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from zipfile import ZipFile
from urllib.parse import urlsplit

BASE = os.environ.get("ENVMUX_BASE_URL", "").rstrip("/")
MODEL = "dashscope.deepseek-v4.1-flash-1017"
SYSTEM = """你是行业研究分析师。通过目录自行取证，可以心算。回复单个 JSON 对象：读取原文用 {"fetch":["文档ID",...]}，可一次取多份；交卷则直接返回题面要求的 {"cutoff":"...","findings":{...}}。最多三轮取文，第4次回复只能交卷。题面提到的本地命令及写文件由这个接口代替。不会得到评分反馈。"""
PACKS = {"main":"industry-research-harbor-v1.zip","extra":"industry-research-harbor-extra28.zip"}
ROOT=Path(__file__).resolve().parent


def write(path, obj):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n")
    tmp.replace(path)


class Transport(Exception):
    pass


def completion(msgs,key):
    payload=dict(model=MODEL,messages=msgs,stream=False,max_tokens=10000,temperature=0)
    with tempfile.NamedTemporaryFile(mode="w",suffix=".json") as f:
        json.dump(payload,f,ensure_ascii=False);f.flush()
        for i in range(3):
            r=subprocess.run(["curl","--disable","--silent","--show-error","--max-time","210","--connect-timeout","15","--proto","=https",
                              "--config","-","--header","Content-Type: application/json","--data-binary","@"+f.name,
                              "--write-out","\n%{http_code}",BASE+"/chat/completions"],
                             input=f'header = "Authorization: Bearer {key}"\n',capture_output=True,text=True)
            body,_,status=r.stdout.rpartition("\n")
            if not r.returncode and status=="200":
                try:
                    reply=json.loads(body); choice=reply["choices"][0]
                    return choice["message"].get("content") or "",dict(model=reply.get("model"),usage=reply.get("usage"),finish=choice.get("finish_reason"))
                except (ValueError,KeyError,IndexError,TypeError) as e:
                    raise Transport("invalid gateway response") from e
            err=f"curl={r.returncode} HTTP={status}"
            if i==2 or (not r.returncode and status not in {"429","502","503","504","500"}):
                raise Transport(err)
            time.sleep(2**(i+1))


def public_cases():
    cases=[]
    for pack,filename in PACKS.items():
        with ZipFile(ROOT.parent/"exports"/filename) as z:
            for t in sorted(n.split("/")[0] for n in z.namelist() if n.endswith("/instruction.md")):
                inst=z.read(t+"/instruction.md").decode()
                raw=z.read(t+"/environment/data/corpus.jsonl")
                docs=[json.loads(l) for l in raw.splitlines()]
                cases.append((pack,t,inst,docs,hashlib.sha256(raw).hexdigest()))
    return cases


def parse_response(raw,compatible):
    s=raw.strip(); fenced=re.fullmatch(r"```(?:json)?\s*\n(.*?)\s*```",s,re.S|re.I)
    s=fenced[1] if fenced else s
    try:return json.loads(s)
    except ValueError:
        if not compatible:raise
    dsml=re.fullmatch(r'<｜DSML｜ calls>\s*<｜DSML｜ invoke name="fetch">\s*<｜DSML｜ parameter name="\w+" string="(?:true|false)">(.*?)</｜DSML｜ parameter>\s*</｜DSML｜ invoke>\s*</｜DSML｜ calls>',s,re.S)
    if dsml:return {"fetch":json.loads(dsml[1])}
    obj,_=json.JSONDecoder().raw_decode(s)
    if isinstance(obj,dict) and set(obj)=={"fetch"}:return obj
    raise ValueError("invalid final response")


def evaluate(case,key,out,replay=None):
    pack,tid,instruction,docs,digest=case; file=out/(tid+".json")
    if file.exists():
        old=json.loads(file.read_text())
        if old["status"]!="infrastructure_error":return old["status"]
    directory=[{k:d[k] for k in ("id","title","date","edition","period","coverage","publisher")} for d in docs]
    byid={d["id"]:d for d in docs}
    msgs=[{"role":"system","content":SYSTEM},{"role":"user","content":instruction+"\n公开目录（原始顺序）：\n"+json.dumps(directory,ensure_ascii=False)}]
    rec=dict(task=tid,pack=pack,corpus_sha256=digest,requested_model=MODEL,started=datetime.now(timezone.utc).isoformat(),
             steps=[],answer=None,status="invalid_answer")
    start=time.monotonic()
    old=json.loads((replay/(tid+".json")).read_text()) if replay else None
    if old:
        assert old["corpus_sha256"]==digest and old["requested_model"]==MODEL
        rec["reused_steps"]=len(old["steps"])
    try:
        for step in range(4):
            if old and step<len(old["steps"]):
                meta=old["steps"][step].copy();raw=meta["response"]
            else:raw,meta=completion(msgs,key)
            meta["response"]=raw;rec["steps"].append(meta)
            if meta["model"]!=MODEL and meta["model"] not in (None,"") and MODEL.rsplit(".",1)[-1] not in str(meta["model"]):
                rec["reported_model_warning"]=meta["model"]
            try: obj=parse_response(raw,compatible=bool(replay))
            except ValueError:break
            if not isinstance(obj,dict):break
            if "fetch" not in obj:
                rec.update(status="submitted",answer=obj);break
            ids=obj["fetch"]
            if step==3 or not isinstance(ids,list) or not all(isinstance(k,str) for k in ids):break
            fetched=[byid[k] if k in byid else {"id":k,"error":"unknown document"} for k in dict.fromkeys(ids)]
            meta["fetched"]=[d["id"] for d in fetched if "error" not in d]
            msgs.extend([{"role":"assistant","content":raw},{"role":"user","content":"原文：\n"+json.dumps(fetched,ensure_ascii=False)
                         +("\n本轮请交卷。" if step==2 else "")}])
    except Transport as e:
        rec.update(status="infrastructure_error",error=str(e))
    rec["elapsed_s"]=round(time.monotonic()-start,2)
    write(file,rec)
    print(f"{tid}: {rec['status']} ({len(rec['steps'])} replies, {rec['elapsed_s']}s) {rec.get('error','')}",flush=True)
    return rec["status"]


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);p.add_argument("--workers",type=int,default=5)
    p.add_argument("--compat-replay",type=Path);args=p.parse_args()
    endpoint=urlsplit(BASE)
    if endpoint.scheme!="https" or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise SystemExit("Set ENVMUX_BASE_URL to an HTTPS API base URL.")
    cases=public_cases();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    protocol=dict(model=MODEL,endpoint_sha256=hashlib.sha256(BASE.encode()).hexdigest(),system=SYSTEM,temperature=0,max_tokens=10000,max_fetch_rounds=3,
                  pack_sizes={k:sum(c[0]==k for c in cases) for k in PACKS},workers=args.workers)
    if args.compat_replay:
        if json.loads((args.compat_replay/"protocol.json").read_text())!=protocol:raise SystemExit("source protocol differs")
        protocol["replay_from"]=args.compat_replay.name
        protocol["adapter"]="also accept single DSML fetch or leading JSON fetch with trailing text; final answers unchanged"
    if (out/"protocol.json").exists() and json.loads((out/"protocol.json").read_text())!=protocol: raise SystemExit("existing protocol differs")
    write(out/"protocol.json",protocol)
    key=os.getenv("ENVMUX_API_KEY") or getpass.getpass("ENVMUX key (hidden): ")
    if not re.fullmatch(r"[A-Za-z0-9._~+/=-]+",key):raise SystemExit("Invalid credential format")
    if evaluate(cases[0],key,out,args.compat_replay)=="infrastructure_error":raise SystemExit("Gateway smoke request failed; batch not sent.")
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs=[pool.submit(evaluate,c,key,out,args.compat_replay) for c in cases[1:]]
        for job in as_completed(jobs):job.result()
