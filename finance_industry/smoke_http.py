"""Exercise a generated task's FinanceGym-style HTTP API over loopback."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen


def test(env):
    def port():
        with socket.socket() as sock:
            sock.bind(("127.0.0.1",0))
            return sock.getsockname()[1]
    emb,api=port(),port()
    proc=subprocess.Popen([sys.executable,str(env/"archive.py"),"serve","--embed-port",str(emb),"--search-port",str(api)])
    def post(p,path,obj):
        req=Request(f"http://127.0.0.1:{p}{path}",data=json.dumps(obj).encode(),headers={"Content-Type":"application/json"})
        with urlopen(req,timeout=2) as response: return json.load(response)
    try:
        for _ in range(100):
            if proc.poll() is not None: raise RuntimeError("server exited during startup")
            try:
                with socket.create_connection(("127.0.0.1",api),timeout=.2):break
            except OSError:time.sleep(.02)
        cutoff=json.loads((env/"data/request.json").read_text())["cutoff"]
        vec=post(emb,"/v1/embeddings",{"input":"qualification board separator"})["data"][0]["embedding"]
        hits=post(api,"/search",{"query_embedding":vec,"max_date":cutoff,"k":3})["results"]
        assert len(hits)==3 and all(h["date"]<=cutoff for h in hits)
        assert post(api,"/fetch",{"id":hits[0]["id"]})["text"]
        print("HTTP embedding -> dated search -> full-text fetch passed")
    finally:
        proc.terminate();proc.wait()


if __name__=="__main__":
    test(Path(sys.argv[1]))
