"""Summarize completed Harbor Oracle and Frontier Model jobs into Markdown score tables."""
import json
import sys
from pathlib import Path
from statistics import mean


def read_json(path: Path):
    return json.loads(path.read_text())


def collect(job_dir: Path):
    meta = read_json(job_dir / "result.json")
    if not meta.get("finished_at"):
        raise RuntimeError(f"Unfinished job: {job_dir}")
    trials = {}
    for p in sorted(job_dir.glob("*/result.json")):
        t = read_json(p)
        detail = p.parent / "verifier/details.json"
        reward_file = p.parent / "verifier/reward.txt"
        name = p.parent.name.split("__")[0]
        err = (t.get("exception_info") or {}).get("exception_type")
        trials[name] = {
            "dir": p.parent,
            "error": err,
            "reward": float(reward_file.read_text().strip()) if reward_file.exists() and reward_file.read_text().strip() else 0.0,
            "detail": read_json(detail) if detail.exists() else None,
        }
    return trials


def render_table(trials):
    lines = [
        "| 任务 | Reward | Gate | 历史 | 预测三表 | FCFF | 估值 | 基准勾稽 | 扰动勾稽 | 价格Δ | 回款Δ | 折现Δ | 有效公式 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    rewards = []
    for name, t in sorted(trials.items()):
        d = t["detail"] or {}
        if t["error"] and not d:
            lines.append(f"| `{name}` | ERR ({t['error']}) | - | - | - | - | - | - | - | - | - | - | - |")
            continue
        rewards.append(t["reward"])
        gs = d.get("groups", {})
        gate = d.get("dynamic_gate")
        gate_s = f"{gate:.2f}" if isinstance(gate, (int, float)) else "-"
        fmt = lambda g: f"{gs[g][0]}/{gs[g][1]}" if g in gs else "-"
        cols = [
            fmt(g)
            for g in [
                "history",
                "forecast",
                "fcff",
                "valuation",
                "ties",
                "ties_shock",
                "shock_operations",
                "shock_collection",
                "shock_discount",
                "formulas",
            ]
        ]
        lines.append(f"| `{name}` | **{t['reward']:.4f}** | {gate_s} | " + " | ".join(cols) + " |")
    if rewards:
        lines.append("")
        lines.append(
            f"**汇总**：完成 {len(rewards)}/{len(trials)} 题，满分通过 {sum(r == 1.0 for r in rewards)}/{len(trials)}，"
            f"平均 Reward = **{mean(rewards):.4f}**。"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    job_dir = Path(sys.argv[1])
    trials = collect(job_dir)
    print(render_table(trials))
    print("\n### 逐题首项失败样例")
    for name, t in sorted(trials.items()):
        d = t["detail"] or {}
        notes = []
        for grp, exs in d.get("examples", {}).items():
            if exs:
                addr, got, exp = exs[0]
                notes.append(f"{grp}: `{addr}` 实际 `{got}` vs 期望 `{exp}`")
        summary = "；".join(notes[:4]) if notes else (t["error"] or d.get("reason") or "全部通过")
        print(f"- **{name}** (`{t['reward']:.4f}`): {summary}")
