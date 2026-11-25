"""Run the two-turn domestic-model protocol on the frozen v1 filings suite."""
import argparse
import concurrent.futures as futures
import contextlib
import fcntl
import getpass
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "dcf_benchmark/jobs/v1-domestic-thinking"
GATEWAY = os.environ.get("ENVMUX_BASE_URL", "").rstrip("/")
DEEP, KIMI, QWEN, GLM = MODELS = (
    "dashscope.deepseek-v4.1-flash-1017", "dashscope.kimi-k3.1-pro", "qwen4-max", "dashscope.glm-5.3",
)
WORKERS = {DEEP: 6, KIMI: 4, QWEN: 6, GLM: 6}
IMAGE = "dcfeval-calc:v1"
DOCKER = threading.BoundedSemaphore(3)
SYSTEM = ("You are a financial modeling agent. Return only a complete Python 3 program, optionally fenced "
          "in a single python block. It will run with openpyxl and the standard library in an offline Linux "
          "workspace. Read the case exhibits from /work/data and create /work/output.xlsx with live Excel "
          "formulas. Follow the assigned build or repair mode. You have one repair opportunity only upon "
          "program error or missing output.")


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trials():
    manifest = read(ROOT / "results/manifest.json")
    acceptance = read(ROOT / "results/acceptance.json")
    assert manifest["num_tasks"] == len(manifest["tasks"]) == 20
    for entry in manifest["tasks"]:
        task = ROOT / "DCFEval" / entry["task"]
        public = task / "environment/data"
        assert {p.name: digest(p) for p in public.iterdir()} == entry["public_files"]
        for key, rel in [("instruction","instruction.md"), ("answers","tests/answers.json"), ("grade","tests/grade.py")]:
            assert digest(task / rel) == entry["sha256"][key]
        assert acceptance[task.name]["oracle_local"]["reward"] == 1
        yield task


def exhibit(path):
    if path.suffix != ".xlsx":
        return path.read_text()
    wb = load_workbook(path, data_only=False)
    lines = ["Inherited workbook (also mounted intact in /work/data):"]
    for sheet in wb:
        lines.append(f"{sheet.title} [{sheet.sheet_state}]")
        for row in sheet.iter_rows():
            lines.append(" | ".join(f"{c.coordinate}={c.value}" for c in row if c.value is not None))
    names = wb.defined_names
    for name in (names.values() if hasattr(names, "values") else names.definedName):
        lines.append(f"Defined name: {name.name} -> {name.attr_text}")
    wb.close()
    return "\n".join(lines)


def prompt(task):
    files = [f"FILE /work/data/{p.name}\n{exhibit(p)}" for p in sorted((task/"environment/data").iterdir())]
    user = (task/"instruction.md").read_text().rstrip() + "\n\nPublic input file contents:\n" + "\n\n".join(files)
    return [dict(role="system",content=SYSTEM), dict(role="user",content=user)]


def unpack(body, model):
    if body.lstrip().startswith(b"{"):
        obj = json.loads(body)
        choice = obj["choices"][0]
        content = choice["message"].get("content") or ""
        thought = bool(choice["message"].get("reasoning_content"))
        finish, usage, returned = choice.get("finish_reason"), obj.get("usage"), obj.get("model")
        response_id = obj.get("id")
    else:
        chunks, thought, finish, usage, returned, response_id = [], False, None, None, None, None
        for line in body.splitlines():
            if not line.startswith(b"data:"):
                continue
            chunk = line[5:].strip()
            if not chunk or chunk == b"[DONE]":
                continue
            obj = json.loads(chunk)
            if obj.get("error"):
                raise ValueError(str(obj["error"])[:300])
            returned = obj.get("model") or returned
            response_id = obj.get("id") or response_id
            usage = obj.get("usage") or usage
            for choice in obj.get("choices") or []:
                if choice.get("index",0) == 0:
                    delta = choice.get("delta") or {}
                    chunks.append(delta.get("content") or "")
                    thought |= bool(delta.get("reasoning_content"))
                    finish = choice.get("finish_reason") or finish
        content = "".join(chunks)
    if not finish or returned not in (model, model.removeprefix("dashscope.")):
        raise ValueError(f"Incomplete response or unexpected model: {returned!r}, {finish!r}")
    return dict(content=content, reasoning_content_present=thought, model=returned,
                response_id=response_id, usage=usage or {}, finish_reason=finish)


def complete(key, model, messages, dest):
    dest.mkdir(exist_ok=True)
    settings = {"thinking":{"type":"enabled"}} if model == GLM else {"enable_thinking":True}
    if model == KIMI:
        settings["reasoning_effort"] = "max"
    limit = 200000
    request = dict(model=model, messages=messages, stream=True, stream_options={"include_usage":True}, **settings)
    cache = dest/"reply.json"
    message_hash = hashlib.sha256(json.dumps(request).encode()).hexdigest()
    if cache.exists():
        reply = read(cache)
        if reply["message_hash"] != message_hash:
            raise ValueError("Cannot replay a different prompt")
        return reply
    prior = sorted(dest.glob("http-*.json"))
    if model == GLM and any(read(p).get("cap_rejected") for p in prior):
        limit = 131072
    failures = 0
    while failures < 3:
        idx = 1 + max((int(p.stem.split("-")[-1]) for p in dest.glob("request-*.json")),default=0)
        payload = dest/f"request-{idx}.json"
        save(payload, dict(request,max_tokens=limit))
        start = time.time()
        # Never put a credential in argv, the container, or the trajectory.
        cmd = ["/usr/bin/curl","-q","-sS","--proto","=https","--max-time","2400","--connect-timeout","15",
               "--config","-","-H","Content-Type: application/json","--data-binary","@"+str(payload),
               "-w","\n%{http_code}",GATEWAY+"/chat/completions"]
        resp = subprocess.run(cmd,input=f'header = "Authorization: Bearer {key}"\n'.encode(),capture_output=True)
        body, _, status = resp.stdout.rpartition(b"\n")
        body = body.replace(key.encode(), b"[redacted]")
        (dest/f"response-{idx}.gz").write_bytes(gzip.compress(body,compresslevel=5,mtime=0))
        desc = (body[:900] or resp.stderr[:350]).decode(errors="replace")
        rejected = (model == GLM and limit == 200000 and status == b"400" and
                    "max_tokens" in desc and "131072" in desc)
        record = dict(status=status.decode(),curl_exit=resp.returncode,started_at=start,
                      elapsed_s=round(time.time()-start,3),max_tokens=limit,cap_rejected=rejected)
        save(dest/f"http-{idx}.json", record)
        if rejected:
            limit = 131072
            continue
        if not resp.returncode and status == b"200":
            try:
                reply = unpack(body,model)
                reply.update(message_hash=message_hash,max_tokens=limit)
                save(cache,reply)
                return reply
            except (ValueError, KeyError, IndexError) as exc:
                desc = str(exc)
        elif not resp.returncode and status not in (b"408",b"429",b"500",b"502",b"503",b"504"):
            raise RuntimeError(f"HTTP {status.decode()}: {desc[:350]}")
        failures += 1
        if failures < 3:
            time.sleep((20 if status == b"429" else 4)*failures)
    raise RuntimeError(f"Gateway attempts exhausted: HTTP {status.decode()}, curl {resp.returncode}, {desc[:350]}")


def container(mounts, args):
    cmd = ["docker","run","--rm","--pull=never","--network=none","--cpus=1","--memory=1536m",
           "--cap-drop=ALL","--security-opt=no-new-privileges","--pids-limit=128","-w","/work"]
    for path, target, mode in mounts:
        cmd.extend(["-v",f"{path}:{target}:{mode}"])
    with DOCKER:
        return subprocess.run(cmd+[IMAGE]+args,capture_output=True,text=True,errors="replace",timeout=300)


def execute(task, turn, reply, out):
    code_blocks = re.findall(r"```(?:python3?|py)?\s*\n(.*?)```",reply["content"],re.S|re.I)
    program = turn/"attempt.py"
    program.write_text(code_blocks[-1] if code_blocks else reply["content"])
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp).resolve()
        (work/"data").symlink_to("/dcf-public")
        (work/"create_model.py").symlink_to("/dcf-program.py")
        mounts = [(work,"/work","rw"),(task/"environment/data","/dcf-public","ro"),(program,"/dcf-program.py","ro")]
        start = time.monotonic()
        proc = container(mounts,["timeout","-k","3","65","sh","-c","python3 /dcf-program.py && test -s /work/output.xlsx"])
        if proc.returncode in (125,126,127):
            raise RuntimeError("Container infrastructure: " + proc.stderr[-400:])
        p = work/"output.xlsx"
        delivered = (proc.returncode == 0 and p.exists() and stat.S_ISREG(p.lstat().st_mode)
                     and 0 < p.stat().st_size <= 30_000_000)
        if delivered:
            shutil.copyfile(p,out/"output.xlsx")
        result = dict(exit_code=proc.returncode,stdout=proc.stdout,stderr=proc.stderr,
                      elapsed_s=round(time.monotonic()-start,3),delivered=delivered)
        save(turn/"execution.json",result)
        return result


def trial(key, model, task):
    dest = JOBS/model/task.name
    dest.mkdir(parents=True,exist_ok=True)
    with (dest/"run.lock").open("a") as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return
        state = dest/"status.json"
        if state.exists() and read(state).get("reward") is not None:
            return
        row = dict(task=task.name,model=model,reward=None,phase="solving")
        out = dest/"workbook"
        out.mkdir(exist_ok=True)
        save(state,row)
        try:
            messages = prompt(task)
            for number in (1,2):
                turn = dest/f"turn-{number}"
                reply = complete(key,model,messages,turn)
                result = read(turn/"execution.json") if (turn/"execution.json").exists() else execute(task,turn,reply,out)
                if result["delivered"]:
                    if not (out/"output.xlsx").is_file():
                        raise RuntimeError("Missing archived workbook")
                    break
                diag = "\n".join(x for x in (result["stdout"],result["stderr"]) if x)
                messages += [dict(role="assistant",content=reply["content"]), dict(role="user",
                    content="Execution failed or no file produced. Return a corrected complete program.\n"+diag[-2800:])]
            turns = sorted(dest.glob("turn-*"))
            http = [read(p) for turn in turns for p in turn.glob("http-*.json")]
            row.update(phase="grading",calls=number,delivered=result["delivered"],http_attempts=len(http),
                       cap_rejections=sum(a["cap_rejected"] for a in http),
                       solve_s=round(sum(a["elapsed_s"] for a in http) +
                           sum(read(t/"execution.json")["elapsed_s"] for t in turns),3))
            save(state,row)
            verifier = dest/"verifier"
            verifier.mkdir(exist_ok=True)
            score = container([(out,"/work","ro"),(task/"tests","/tests","ro"),(verifier,"/logs/verifier","rw")],
                              ["sh","/tests/test.sh"])
            if score.returncode:
                raise RuntimeError("Verifier: "+score.stderr[-450:])
            row.update(phase="scored",reward=read(verifier/"details.json")["reward"])
        except Exception as exc:
            row.update(phase="infrastructure_error", error=str(exc).replace(key,"[redacted]")[:600])
        save(state,row)
        print(model,task.name,row["phase"],row["reward"],flush=True)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--model", choices=MODELS,action="append")
    a.add_argument("--task", action="append")
    a.add_argument("--workers", type=int, help="Override per-model concurrency")
    args = a.parse_args()
    tasks = list(trials())
    if args.task:
        if not set(args.task) <= {t.name for t in tasks}:
            a.error("Unknown task")
        tasks = [t for t in tasks if t.name in args.task]
    endpoint = urlsplit(GATEWAY)
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password
            or endpoint.query or endpoint.fragment or endpoint.path != "/v1"):
        a.error("Set ENVMUX_BASE_URL to your HTTPS gateway with path /v1")
    key = os.environ.pop("ENVMUX_API_KEY",None) or getpass.getpass("ENVMUX key (hidden): ")
    if not re.fullmatch(r"[A-Za-z0-9._~+/=-]+",key):
        a.error("Invalid credential format")
    JOBS.mkdir(parents=True,exist_ok=True)
    with contextlib.ExitStack() as stack:
        jobs = []
        for model in args.model or MODELS:
            pool = stack.enter_context(futures.ThreadPoolExecutor(args.workers or WORKERS[model]))
            jobs.extend(pool.submit(trial,key,model,t) for t in tasks)
        for f in futures.as_completed(jobs):
            f.result()
    if any(read(JOBS/m/t.name/"status.json").get("reward") is None for m in args.model or MODELS for t in tasks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
