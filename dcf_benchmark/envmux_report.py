"""Write the live v1 domestic leaderboard and archive scored trials with file hashes."""
import argparse
import gzip
import json
import re
import time
from statistics import mean
from zipfile import ZipFile, ZIP_DEFLATED

from envmux_eval import ROOT, JOBS, MODELS, digest, read, save

OUT = ROOT/"results/domestic-thinking"
ARCHIVES = ROOT/"trajectories/domestic-thinking"
LABELS = dict(zip(MODELS, ("DeepSeek V4.1 Flash", "Kimi K3.1 Pro", "Qwen4 Max", "GLM 5.3")))


def reasoning(usage):
    for v in ((usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
              (usage.get("output_tokens_details") or {}).get("reasoning_tokens"), usage.get("reasoning_tokens")):
        if isinstance(v, int) and v >= 0:
            return v


def collect(model, entry):
    case = JOBS/model/entry["task"]
    state = case/"status.json"
    row = read(state) if state.is_file() else dict(task=entry["task"],model=model,phase="queued",reward=None)
    replies = [read(p) for p in sorted(case.glob("turn-*/reply.json"))]
    attempts = [read(p) for p in sorted(case.glob("turn-*/http-*.json"))]
    row.update(mode=entry["mode"],http_attempts=len(attempts),cap_rejections=sum(a["cap_rejected"] for a in attempts),
               truncated_calls=sum(r["finish_reason"] == "length" for r in replies),
               responses_with_thinking=sum(r["reasoning_content_present"] for r in replies),
               resolved_limits=sorted({r["max_tokens"] for r in replies}))
    if row.get("reward") is not None:
        if row["calls"] != len(replies) or read(case/"verifier/details.json")["reward"] != row["reward"]:
            raise ValueError(f"Inconsistent saved evidence for {case}")
        numbers = [reasoning(r["usage"]) for r in replies]
        row["reasoning_tokens"] = sum(numbers) if all(n is not None for n in numbers) else None
        # First HTTP dispatch to final program exit, including backoffs, excluding grading and queue before launch.
        row["solve_s"] = round(max(p.stat().st_mtime for p in case.glob("turn-*/execution.json"))
                               - min(a["started_at"] for a in attempts),3)
    return row


def stats(rows):
    done = [r for r in rows if r["reward"] is not None]
    result = dict(scored=len(done), total=len(rows),
                  delivered=sum(r["delivered"] for r in done),
                  reasoning_coverage=sum(r.get("reasoning_tokens") is not None for r in done),
                  calls_with_reasoning_content=sum(r["responses_with_thinking"] for r in done),
                  calls=sum(r["calls"] for r in done),
                  truncated_calls=sum(r["truncated_calls"] for r in rows),
                  parameter_rejections=sum(r["cap_rejections"] for r in rows),
                  infra_errors=sum(r["phase"]=="infrastructure_error" for r in rows))
    for k in ["reward","calls","solve_s","reasoning_tokens"]:
        values = [r[k] for r in done if r.get(k) is not None]
        result["avg_"+k] = mean(values) if values else None
    for mode in ("build","repair"):
        scores = [r["reward"] for r in done if r["mode"]==mode]
        result["avg_"+mode] = mean(scores) if scores else None
    return result


def fmt(x, digits):
    return f"{x:,.{digits}f}" if x is not None else "—"


def archive(row):
    model, task = row["model"], row["task"]
    case = JOBS/model/task
    out = ARCHIVES/model/(task+".zip")
    out.parent.mkdir(parents=True,exist_ok=True)
    files = [case/"status.json", *case.glob("verifier/*"), *case.glob("workbook/*.xlsx")]
    files += [p for turn in case.glob("turn-*") for p in turn.iterdir()
              if re.fullmatch(r"(request-\d+\.json|http-\d+\.json|response-\d+\.gz|reply\.json|attempt\.py|execution\.json)",p.name)]
    if not out.exists():
        tmp = out.with_suffix(".tmp")
        with ZipFile(tmp,"w",ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(files):
                if p.is_symlink() or not p.is_file():
                    raise ValueError(f"Unexpected trace file: {p}")
                data = p.read_bytes()
                if p.suffix != ".xlsx":
                    plain = gzip.decompress(data) if p.suffix == ".gz" else data
                    if re.search(rb"(?:Bearer [a-zA-Z0-9._+/=-]{16,}|\bsk-[a-zA-Z0-9_-]{18,})",plain):
                        raise ValueError(f"Possible credential in {p.relative_to(case)}")
                z.writestr(str(p.relative_to(case)), data)
            z.writestr("metrics.json",json.dumps(row,ensure_ascii=False,indent=2))
        tmp.replace(out)
    return dict(model=model,task=task,path=str(out.relative_to(ROOT)),sha256=digest(out),bytes=out.stat().st_size)


def report(package=False):
    OUT.mkdir(parents=True,exist_ok=True)
    manifest = ROOT/"results/manifest.json"
    entries = read(manifest)["tasks"]
    rows = [collect(m,e) for m in MODELS for e in entries]
    summary = {m:stats([r for r in rows if r["model"]==m]) for m in MODELS}
    final = all(r["reward"] is not None for r in rows)
    info = dict(manifest_sha256=digest(manifest),suite="v1-filings-repair",complete=final,models=summary,trials=rows)
    save(OUT/"summary.json",info)
    lines = ["# 国产模型开启推理的 DCF 测评","",
             f"已评分 {sum(s['scored'] for s in summary.values())}/{len(rows)}。使用 20 道 v1 财报题（14 道新建和 6 道存量 Excel 修复）。",
             "", "| 模型 | 已评分 | 平均得分（0–1） | 平均调用/题 | 平均解题秒数 | 平均推理 token/题（有计数题数） | 已交付/已评分 | 截断调用 | 上限拒绝 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for m,s in summary.items():
        lines.append(f"| {LABELS[m]} | {s['scored']}/20 | {fmt(s['avg_reward'],4)} | {fmt(s['avg_calls'],2)} | "
                     f"{fmt(s['avg_solve_s'],1)} | {fmt(s['avg_reasoning_tokens'],1)} ({s['reasoning_coverage']}) | "
                     f"{s['delivered']}/{s['scored']} | {s['truncated_calls']} | {s['parameter_rejections']} |")
    lines += ["","每个有效模型回复算一次调用。首次 HTTP 请求到最后一次工作簿执行结束为解题用时，含网络重试和执行等待。"
              "均值按已评分题计算。每题推理 token 取服务端各轮计数之和，仅在该题所有轮次都有计数时纳入均值。"
              "基础设施失败保留空分；有效作答用尽修正机会仍未交付，按当前评分器得 0。",
              "", "四个模型均请求开启推理，每题最多两轮，初始上限 200,000。Kimi 另设 reasoning_effort=max。"
              "GLM 仅在服务端明确拒绝 200,000 并指明 131,072 后按该上限重试。",
              "", f"题集清单 SHA-256 为 `{info['manifest_sha256']}`。[逐题明细与设置](summary.json)"]
    if package:
        index = [archive(r) for r in rows if r["reward"] is not None]
        ARCHIVES.mkdir(parents=True,exist_ok=True)
        save(ARCHIVES/"index.json",dict(manifest_sha256=info["manifest_sha256"],archives=index))
        lines += ["","[带 SHA-256 的逐题轨迹包索引](../../trajectories/domestic-thinking/index.json)"]
    tmp = OUT/"report.tmp"
    tmp.write_text("\n".join(lines)+"\n")
    tmp.replace(OUT/"report.md")
    return final


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--archive", action="store_true")
    cli.add_argument("--watch", action="store_true",help="Refresh every 30 seconds; archive all traces at completion")
    a = cli.parse_args()
    while True:
        done = report(a.archive)
        if done or not a.watch:
            if done and a.watch and not a.archive:
                report(True)
            break
        time.sleep(30)
