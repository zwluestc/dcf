"""Small offline retriever with the FinanceGym reference client's three POST routes."""
import argparse
from collections import Counter
from datetime import date
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
from threading import Thread

DIM = 512


def embed(text):
    vec=[0.0]*DIM
    for word, n in Counter(re.findall(r"[a-z0-9]+|[\u3400-\u9fff]",text.lower())).items():
        ix=int.from_bytes(hashlib.blake2s(word.encode(),digest_size=2).digest(),"big")%DIM
        vec[ix]+=1+math.log(n)
    norm=math.sqrt(sum(x*x for x in vec)) or 1
    return [x/norm for x in vec]


class Archive:
    def __init__(self, folder):
        self.cutoff=json.loads((folder/"request.json").read_text())["cutoff"]
        self.docs={d["id"]:d for s in (folder/"corpus.jsonl").read_text().splitlines()
                   if (d:=json.loads(s))["date"]<=self.cutoff}
        self.vec={k:embed(" ".join([d["title"]]*3+[d["publisher"], d["coverage"],d["text"]])) for k,d in self.docs.items()}

    def route(self, path, body):
        if path=="/v1/embeddings":
            return {"data":[{"embedding":embed(body["input"]),"index":0}]}
        if path=="/fetch":
            return self.docs[body["id"]]
        if path!="/search": raise KeyError(path)
        stamp=date.fromisoformat(body["max_date"]).isoformat()
        if stamp>self.cutoff: raise ValueError("max_date exceeds task cutoff")
        query=body["query_embedding"]
        if not isinstance(query,list) or len(query)!=DIM or not all(type(x) in (int,float) and math.isfinite(x) for x in query):
            raise ValueError("use this archive's embedding endpoint")
        k=body.get("k",5)
        if type(k)!=int or not 1<=k<=100: raise ValueError("k must be in [1,100]")
        hits=[]
        for key,d in self.docs.items():
            if d["date"]<=stamp:
                score=sum(x*y for x,y in zip(query,self.vec[key]))
                hits.append({**{f:d[f] for f in ("id","title","date","url","publisher","period","coverage","edition")},"score":score})
        return {"results":sorted(hits,key=lambda h:(-h["score"],h["id"]))[:k]}


def serve(archive, ports):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            try:
                n=int(self.headers.get("Content-Length","0"))
                if not 0<n<=100000: raise ValueError("invalid request length")
                out=archive.route(self.path,json.loads(self.rfile.read(n)));code=200
            except KeyError as e: out,code={"error":str(e)},404
            except (ValueError,TypeError,AttributeError) as e: out,code={"error":str(e)},400
            data=json.dumps(out,ensure_ascii=False).encode()
            self.send_response(code);self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(data)));self.end_headers();self.wfile.write(data)
    servers=[ThreadingHTTPServer(("127.0.0.1",p),Handler) for p in dict.fromkeys(ports)]
    for s in servers[1:]: Thread(target=s.serve_forever,daemon=True).start()
    servers[0].serve_forever()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--data",type=Path,default=Path(__file__).parent/"data")
    subs=p.add_subparsers(dest="cmd",required=True)
    s=subs.add_parser("search");s.add_argument("query");s.add_argument("--max-date");s.add_argument("-k",type=int,default=5)
    subs.add_parser("fetch").add_argument("id")
    v=subs.add_parser("serve");v.add_argument("--embed-port",type=int,default=8888);v.add_argument("--search-port",type=int,default=8889)
    args=p.parse_args();index=Archive(args.data)
    if args.cmd=="serve": serve(index,[args.embed_port,args.search_port])
    else:
        result=index.route("/fetch",{"id":args.id}) if args.cmd=="fetch" else index.route("/search",{"max_date":args.max_date or index.cutoff,"query_embedding":embed(args.query),"k":args.k})
        print(json.dumps(result,ensure_ascii=False,indent=2))
