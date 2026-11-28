"""Author-side acceptance: independent public solution, negative controls and PIT checks."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from grade import grade
from reference import solve
from retrieval import Archive

ERRORS={"battery":"book unqualified line in the base case","foundry":"compare physical wafer counts",
        "retail":"use consolidated growth as same-store growth","wind":"count an unsigned reservation",
        "smelter":"reset the entire feedbook","port":"ignore customs correction",
        "insurer":"equate regulatory approval with completion"}


def check(root):
    manifest=json.loads((root/"manifest.json").read_text());results=[]
    for item in manifest["tasks"]:
        task=root/"tasks"/item["task_id"];data=task/"environment/data"
        raw=(data/"corpus.jsonl").read_bytes()
        assert hashlib.sha256(raw).hexdigest()==item["corpus_sha256"]
        assert {f.relative_to(task/"environment").as_posix() for f in (task/"environment").rglob("*") if f.is_file()}=={
            "Dockerfile","archive.py","data/corpus.jsonl","data/request.json"}
        gold=json.loads((task/"tests/gold.json").read_text())
        ref=solve(data);score=lambda answer:grade(answer,gold)[0]
        assert score(ref)==1 and score({})==0
        negative=score(solve(data,True));assert negative<1
        nocites=copy.deepcopy(ref)
        for finding in nocites["findings"].values(): finding["sources"]=[]
        assert score(nocites)==0.6
        wrongdate={**ref,"cutoff":"2099-01-01"};assert score(wrongdate)==0
        with tempfile.TemporaryDirectory() as tmp:
            rev=Path(tmp);(rev/"request.json").write_bytes((data/"request.json").read_bytes())
            (rev/"corpus.jsonl").write_bytes(b"\n".join(reversed(raw.splitlines()))+b"\n")
            assert solve(rev)==ref
        idx=Archive(data);q=idx.route("/v1/embeddings",{"input":item["family"]})["data"][0]["embedding"]
        query={"query_embedding":q,"max_date":ref["cutoff"],"k":100}
        hits=idx.route("/search",query)["results"]
        assert len(idx.docs)==len(raw.splitlines())==len(hits)==item["docs_visible"]
        for row in ref["findings"].values():
            assert all(idx.route("/fetch",{"id":k})["date"]<=ref["cutoff"] for k in row["sources"])
        future=[json.loads(s) for s in (root/"author"/(task.name+".future.jsonl")).read_text().splitlines()]
        assert future and all(x["date"]>ref["cutoff"] and x["id"] not in idx.docs for x in future)
        for x in future:
            try:idx.route("/fetch",{"id":x["id"]})
            except KeyError:pass
            else:raise AssertionError("future document retrievable")
        for stamp in ("2099-01-01",None):
            try:idx.route("/search",{k:v for k,v in {**query,"max_date":stamp}.items() if v is not None})
            except (KeyError,ValueError):pass
            else:raise AssertionError("missing or too-late cutoff accepted")
        earliest=min(d["date"] for d in idx.docs.values())
        assert all(h["date"]<=earliest for h in idx.route("/search",{**query,"max_date":earliest})["results"])
        results.append(dict(task=task.name,oracle=1,domain_error=ERRORS[item["family"]],
                            domain_error_score=negative,correct_without_sources=0.6,empty=0,wrong_cutoff=0,
                            shuffled_corpus="pass",cutoff_and_fetch="pass",docs=len(hits)))
    return results


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("release",type=Path);p.add_argument("--save",type=Path)
    args=p.parse_args();report=check(args.release)
    if args.save:args.save.write_text(json.dumps(report,indent=2)+"\n")
    print(f"{len(report)} cases passed; {sum(r['docs'] for r in report)} public documents across snapshots.")
