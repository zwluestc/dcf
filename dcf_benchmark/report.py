"""Multi-model Harbor evaluation aggregator, failure-case analyzer, and trajectory exporter for DCFEval.

Usage:
  # Single Harbor job or archived trajectory folder:
  python3 dcf_benchmark/report.py trajectories/oracle

  # Multi-model 20-task comparison table + failure taxonomy + sanitized trajectory export:
  python3 dcf_benchmark/report.py \\
      --models oracle=trajectories/oracle gpt-5=dcf_benchmark/jobs/eval-gpt5 claude-opus=dcf_benchmark/jobs/eval-claude \\
      --json-out results/leaderboard.json \\
      --export-trajectories trajectories
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

HOST_PATH_RE = re.compile(r"/(?:Users|home)/[^/\s\"']+")
SECRET_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sanitize_text(txt: str) -> str:
    txt = HOST_PATH_RE.sub("<HOST_HOME>", txt)
    txt = SECRET_RE.sub(r"\1<REDACTED>", txt)
    return txt


def parse_iso_duration(start_s, end_s):
    if not start_s or not end_s:
        return None
    try:
        t0 = datetime.fromisoformat(str(start_s).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(end_s).replace("Z", "+00:00"))
        dt = (t1 - t0).total_seconds()
        return round(dt, 3) if dt >= 0 else None
    except Exception:
        return None


def discover_task_dirs(root: Path):
    """Discover per-task directories inside either a Harbor job folder or an archived trajectories/<model> folder."""
    found = {}
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        if (p / "verifier").is_dir() or (p / "result.json").exists() or (p / "agent").is_dir():
            task_name = p.name.split("__")[0]
            if task_name.startswith("dcf-"):
                found[task_name] = p
    return found


def extract_trial(task_name: str, tdir: Path):
    res_file = tdir / "result.json"
    res = read_json(res_file) if res_file.exists() else {}
    traj_file = tdir / "agent/trajectory.json"
    traj = read_json(traj_file) if traj_file.exists() else {}
    det_file = tdir / "verifier/details.json"
    detail = read_json(det_file) if det_file.exists() else None
    rew_file = tdir / "verifier/reward.txt"

    if detail and isinstance(detail.get("reward"), (int, float)):
        reward = float(detail["reward"])
    elif rew_file.exists() and rew_file.read_text().strip():
        reward = float(rew_file.read_text().strip())
    else:
        reward = 0.0

    err = (res.get("exception_info") or {}).get("exception_type") or traj.get("last_error")
    delivered = bool(traj.get("delivered")) if "delivered" in traj else (detail is not None and not detail.get("reason"))

    # Elapsed time (seconds)
    elapsed = traj.get("total_elapsed_sec")
    if elapsed is None:
        agent_exec = res.get("agent_execution") or {}
        elapsed = parse_iso_duration(agent_exec.get("started_at"), agent_exec.get("finished_at"))
    if elapsed is None:
        elapsed = parse_iso_duration(res.get("started_at"), res.get("finished_at"))

    # Token usage
    agent_res = res.get("agent_result") or {}
    in_tok = traj.get("input_tokens")
    if in_tok is None:
        in_tok = agent_res.get("n_input_tokens")
    out_tok = traj.get("output_tokens")
    if out_tok is None:
        out_tok = agent_res.get("n_output_tokens")
    tot_tok = traj.get("total_tokens")
    if tot_tok is None and in_tok is not None and out_tok is not None:
        tot_tok = int(in_tok) + int(out_tok)

    # Turn count
    turns = traj.get("turns")
    if turns is None:
        usage_files = list((tdir / "agent").glob("usage-*.json")) if (tdir / "agent").is_dir() else []
        attempt_files = list((tdir / "agent").glob("attempt-*.py")) if (tdir / "agent").is_dir() else []
        if usage_files:
            turns = len(usage_files)
        elif attempt_files:
            turns = len(attempt_files)
        elif agent_res.get("n_turns") is not None:
            turns = int(agent_res["n_turns"])
        elif res.get("agent_execution") is not None or traj:
            turns = 1

    # Four-pillar decomposition (v3.0 rubric)
    pillars = {"three_stmt_fcff": 0.0, "valuation": 0.0, "accounting_ties": 0.0, "sensitivity": 0.0}
    gate = None
    formulas = None
    if detail:
        dp = detail.get("pillars") or {}
        gs = detail.get("groups") or {}

        def ratio(grp):
            pair = gs.get(grp)
            return (pair[0] / pair[1]) if (isinstance(pair, list) and len(pair) == 2 and pair[1]) else 0.0

        pillars["three_stmt_fcff"] = round(
            float(
                dp.get(
                    "statements_and_fcff_40",
                    7.0 * ratio("history") + 21.0 * ratio("forecast") + 12.0 * ratio("fcff"),
                )
            ),
            2,
        )
        pillars["valuation"] = round(float(dp.get("valuation_bridge_25", 25.0 * ratio("valuation"))), 2)
        pillars["accounting_ties"] = round(
            float(
                dp.get(
                    "accounting_integrity_15",
                    9.0 * ratio("ties") + 4.0 * ratio("ties_shock") + 2.0 * ratio("controls"),
                )
            ),
            2,
        )
        pillars["sensitivity"] = round(
            float(
                dp.get(
                    "sensitivity_delta_20",
                    7.0 * ratio("shock_operations") + 6.0 * ratio("shock_collection") + 7.0 * ratio("shock_discount"),
                )
            ),
            2,
        )
        gate = detail.get("dynamic_gate")
        formulas = gs.get("formulas")

    # Classify failure modes
    tags = []
    if reward < 1.0:
        if not delivered or (detail and detail.get("reason")):
            tags.append("未交付/执行崩溃")
        else:
            gs = (detail or {}).get("groups") or {}

            def missed(grp):
                pair = gs.get(grp)
                return isinstance(pair, list) and len(pair) == 2 and pair[0] < pair[1]

            if gate is not None and gate < 0.90:
                tags.append("静态贴死数/伪公式门控拦截")
            if missed("history"):
                tags.append("历史关账合并错误")
            if missed("forecast") or missed("fcff"):
                tags.append("经营递推/三表/FCFF错误")
            if missed("valuation"):
                tags.append("估值桥/WACC/Beta/TSM错误")
            if missed("ties") or missed("ties_shock") or missed("controls"):
                tags.append("会计勾稽未配平/表错误")
            if missed("shock_operations") or missed("shock_collection") or missed("shock_discount"):
                tags.append("敏感性增量联动异常")

    first_examples = []
    if detail:
        for grp, exs in (detail.get("examples") or {}).items():
            if exs:
                addr, got, exp = exs[0]
                first_examples.append(f"{grp}: `{addr}` 实际 `{got}` vs 期望 `{exp}`")

    return {
        "task": task_name,
        "dir": str(tdir),
        "reward": round(reward, 4),
        "pass_strict": reward >= 1.0 - 1e-12,
        "delivered": delivered,
        "elapsed_sec": elapsed,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": tot_tok,
        "turns": turns,
        "dynamic_gate": round(gate, 4) if isinstance(gate, (int, float)) else None,
        "formulas": formulas,
        "pillars": pillars,
        "failure_tags": tags,
        "first_examples": first_examples[:5],
        "error": sanitize_text(str(err))[:300] if err else None,
    }


def summarize_model(label: str, root: Path):
    tdirs = discover_task_dirs(root)
    trials = {k: extract_trial(k, v) for k, v in sorted(tdirs.items())}
    n = len(trials)
    if n == 0:
        raise RuntimeError(f"No dcf-* task trials found under {root}")

    vals = list(trials.values())
    mean_reward = mean(t["reward"] for t in vals)
    pass_cnt = sum(1 for t in vals if t["pass_strict"])
    deliv_cnt = sum(1 for t in vals if t["delivered"])
    times = [t["elapsed_sec"] for t in vals if isinstance(t["elapsed_sec"], (int, float))]
    in_toks = [t["input_tokens"] for t in vals if isinstance(t["input_tokens"], (int, float))]
    out_toks = [t["output_tokens"] for t in vals if isinstance(t["output_tokens"], (int, float))]
    tot_toks = [t["total_tokens"] for t in vals if isinstance(t["total_tokens"], (int, float))]
    turns_list = [t["turns"] for t in vals if isinstance(t["turns"], (int, float))]
    gates = [t["dynamic_gate"] for t in vals if isinstance(t["dynamic_gate"], (int, float))]

    tag_counts = {}
    for t in vals:
        for tg in t["failure_tags"]:
            tag_counts[tg] = tag_counts.get(tg, 0) + 1

    return {
        "model": label,
        "num_tasks": n,
        "mean_reward": round(mean_reward, 4),
        "pass_count": pass_cnt,
        "pass_rate": round(pass_cnt / n, 4),
        "delivered_count": deliv_cnt,
        "delivery_rate": round(deliv_cnt / n, 4),
        "avg_elapsed_sec": round(mean(times), 2) if times else None,
        "avg_input_tokens": round(mean(in_toks), 1) if in_toks else None,
        "avg_output_tokens": round(mean(out_toks), 1) if out_toks else None,
        "avg_total_tokens": round(mean(tot_toks), 1) if tot_toks else None,
        "avg_turns": round(mean(turns_list), 2) if turns_list else None,
        "avg_gate": round(mean(gates), 4) if gates else None,
        "avg_pillars": {
            "three_stmt_fcff": round(mean(t["pillars"]["three_stmt_fcff"] for t in vals), 2),
            "valuation": round(mean(t["pillars"]["valuation"] for t in vals), 2),
            "accounting_ties": round(mean(t["pillars"]["accounting_ties"] for t in vals), 2),
            "sensitivity": round(mean(t["pillars"]["sensitivity"] for t in vals), 2),
        },
        "failure_tag_counts": tag_counts,
        "trials": trials,
    }


def export_sanitized_trajectories(label: str, src_root: Path, export_base: Path):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_").lower()
    dst_model = export_base / slug
    if src_root.resolve() == dst_model.resolve():
        return dst_model
    if dst_model.exists():
        shutil.rmtree(dst_model)
    tdirs = discover_task_dirs(src_root)
    for task_name, tdir in sorted(tdirs.items()):
        out_task = dst_model / task_name
        (out_task / "agent").mkdir(parents=True, exist_ok=True)
        (out_task / "verifier").mkdir(parents=True, exist_ok=True)
        # Copy & sanitize text logs/scripts/json
        for sub, patterns in [
            ("agent", ["trajectory.json", "attempt-*.py", "execution-*.json", "usage-*.json"]),
            ("verifier", ["details.json", "reward.txt"]),
        ]:
            sdir = tdir / sub
            if not sdir.is_dir():
                continue
            for pat in patterns:
                for f in sorted(sdir.glob(pat)):
                    if f.is_file():
                        (out_task / sub / f.name).write_text(
                            sanitize_text(f.read_text(encoding="utf-8", errors="replace")),
                            encoding="utf-8",
                        )
    return dst_model


def fmt_opt(val, fmt_str):
    return "-" if val is None else fmt_str.format(val)


def render_markdown(summaries):
    lines = ["## 多模型 20 题综合评估总表", ""]
    lines.append(
        "| 模型 (Model) | 评测题数 | 平均得分 | 满分率 (1.0) | 交付率 | 平均时间 (s) | 平均输入 Token | 平均输出 Token | 平均总 Token | 平均调用轮次 |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in summaries:
        lines.append(
            f"| `{s['model']}` | {s['num_tasks']} | **{s['mean_reward']:.4f}** | "
            f"{s['pass_count']}/{s['num_tasks']} ({s['pass_rate']*100:.1f}%) | "
            f"{s['delivered_count']}/{s['num_tasks']} ({s['delivery_rate']*100:.1f}%) | "
            f"{fmt_opt(s['avg_elapsed_sec'], '{:.2f}')} | "
            f"{fmt_opt(s['avg_input_tokens'], '{:,.0f}')} | "
            f"{fmt_opt(s['avg_output_tokens'], '{:,.0f}')} | "
            f"{fmt_opt(s['avg_total_tokens'], '{:,.0f}')} | "
            f"{fmt_opt(s['avg_turns'], '{:.2f}')} |"
        )
    lines.append("")

    # Four-pillar breakdown table
    lines.append("### 四支柱分项均分与防贴死数门控")
    lines.append("")
    lines.append("| 模型 (Model) | 三表&FCFF (40) | 估值桥 (25) | 会计勾稽 (15) | 敏感性Δ (20) | 平均门控 Gate | 平均得分 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for s in summaries:
        ap = s["avg_pillars"]
        lines.append(
            f"| `{s['model']}` | {ap['three_stmt_fcff']:.2f} | {ap['valuation']:.2f} | "
            f"{ap['accounting_ties']:.2f} | {ap['sensitivity']:.2f} | "
            f"{fmt_opt(s['avg_gate'], '{:.4f}')} | **{s['mean_reward']:.4f}** |"
        )
    lines.append("")

    # Per-task matrix across all models
    all_tasks = sorted({t for s in summaries for t in s["trials"]})
    lines.append("### 逐题得分矩阵")
    lines.append("")
    lines.append("| 任务 ID | " + " | ".join(f"`{s['model']}`" for s in summaries) + " |")
    lines.append("|---|" + "|".join(["---:"] * len(summaries)) + "|")
    for tk in all_tasks:
        row = []
        for s in summaries:
            tr = s["trials"].get(tk)
            row.append(f"**{tr['reward']:.4f}**" if tr and tr["pass_strict"] else (f"{tr['reward']:.4f}" if tr else "-"))
        lines.append(f"| `{tk}` | " + " | ".join(row) + " |")
    lines.append("")

    # Per-model failure case synthesis
    lines.append("### 逐模型失败 Case 错误归类与诊断")
    lines.append("")
    for s in summaries:
        failed = [t for t in s["trials"].values() if not t["pass_strict"]]
        lines.append(f"#### 模型：`{s['model']}`（未满分 {len(failed)}/{s['num_tasks']} 题）")
        if not failed:
            lines.append("- 全部题目满分通过（`reward = 1.0000`），无失败 Case。")
            lines.append("")
            continue
        tag_str = "、".join(f"{k}（{v} 题）" for k, v in sorted(s["failure_tag_counts"].items(), key=lambda kv: -kv[1]))
        lines.append(f"- **错误类型分布**：{tag_str}")
        for t in failed:
            tags = " / ".join(t["failure_tags"]) or "其他偏差"
            diag = "；".join(t["first_examples"]) if t["first_examples"] else (t["error"] or "无详细诊断")
            lines.append(
                f"- **`{t['task']}`**（Reward=`{t['reward']:.4f}`, Gate=`{fmt_opt(t['dynamic_gate'], '{:.4f}')}`, "
                f"Turns=`{fmt_opt(t['turns'], '{}')}`）[{tags}]：{diag}"
            )
        lines.append("")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("job_dir", nargs="?", type=Path, help="Single Harbor job or trajectory folder (optional if --models used)")
    p.add_argument("--models", nargs="+", help="List of label=path pairs for multi-model comparison")
    p.add_argument("--json-out", type=Path, help="Write structured leaderboard JSON")
    p.add_argument("--export-trajectories", type=Path, help="Export sanitized trajectories into <dir>/<model>/<task>/")
    args = p.parse_args()

    pairs = []
    if args.models:
        for item in args.models:
            if "=" not in item:
                raise SystemExit(f"Invalid --models item (expected label=path): {item}")
            lbl, pth = item.split("=", 1)
            pairs.append((lbl, Path(pth)))
    elif args.job_dir:
        pairs.append((args.job_dir.name, args.job_dir))
    else:
        raise SystemExit("Provide either a single job_dir or --models label=path ...")

    summaries = []
    for lbl, pth in pairs:
        if args.export_trajectories:
            export_sanitized_trajectories(lbl, pth, args.export_trajectories)
        summaries.append(summarize_model(lbl, pth))

    print(render_markdown(summaries))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(
                {
                    "schema_version": "3.0",
                    "models": summaries,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
