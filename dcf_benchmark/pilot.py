"""Standard OpenAI-compatible Harbor agent adapter for running frontier model evaluations on DCFEval.

Records complete per-turn solving trajectories (code, execution stdout/stderr, elapsed wall-clock time,
prompt/completion/total token usage, and turn counts) into `agent/trajectory.json` for downstream
leaderboard aggregation (`report.py`) and sanitized archival under `trajectories/`.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from harbor.agents.base import BaseAgent


def completion(messages, model_name):
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    key = os.environ["OPENAI_API_KEY"]
    max_tokens = int(os.getenv("DCF_MAX_TOKENS", "16000"))
    payload = {"model": model_name, "messages": messages, "max_tokens": max_tokens, "stream": False}
    t0 = time.monotonic()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
        json.dump(payload, f)
        f.flush()
        r = subprocess.run(
            [
                "curl",
                "--disable",
                "--silent",
                "--show-error",
                "--max-time",
                "300",
                "--connect-timeout",
                "20",
                "--config",
                "-",
                "--header",
                "Content-Type: application/json",
                "--data-binary",
                "@" + f.name,
                "--write-out",
                "\n%{http_code}",
                base + "/chat/completions",
            ],
            input=f'header = "Authorization: Bearer {key}"\n',
            capture_output=True,
            text=True,
        )
        llm_sec = round(time.monotonic() - t0, 3)
        if r.returncode:
            raise RuntimeError(f"transport error: curl exit {r.returncode}: {r.stderr[:200]}")
        body, _, status = r.stdout.rpartition("\n")
        if status != "200":
            raise RuntimeError(f"HTTP {status}: {body.replace(key, '[redacted]')[:300]}")
        reply = json.loads(body)
    choice = reply["choices"][0]
    return (
        choice["message"]["content"],
        reply.get("usage", {}),
        reply.get("model", model_name),
        choice.get("finish_reason"),
        llm_sec,
    )


class OpenAICompatAgent(BaseAgent):
    """Multi-turn code-execution agent inside the isolated Harbor container (up to DCF_MAX_TURNS rounds)."""

    @staticmethod
    def name():
        return "dcf-openai-compat"

    def version(self):
        return "3"

    async def setup(self, environment):
        pass

    async def run(self, instruction, environment, context):
        task_t0 = time.monotonic()
        model_name = self.model_name or os.getenv("DCF_MODEL", "gpt-4o")
        data = await environment.exec("for f in /work/data/*; do printf '\\nFILE %s\\n' \"$f\"; cat \"$f\"; done")
        if data.return_code:
            raise RuntimeError("public input data missing in /work/data")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert financial modeling agent. Return a complete Python 3 script inside a single "
                    "```python``` block. It runs in an offline Linux container with openpyxl and LibreOffice Calc. "
                    "Read the raw exhibits in /work/data/ and generate /work/output.xlsx from a blank workbook using "
                    "live Excel formulas for every required forecast and DCF output. You may run LibreOffice inside "
                    "your script to verify formula recalculation before finishing."
                ),
            },
            {"role": "user", "content": instruction + "\n\nPublic input file contents:\n" + data.stdout},
        ]
        context.n_input_tokens = 0
        context.n_output_tokens = 0
        self.logs_dir.mkdir(exist_ok=True, parents=True)

        max_turns = int(os.getenv("DCF_MAX_TURNS", "3"))
        turns_log = []
        llm_total_sec = 0.0
        exec_total_sec = 0.0
        delivered = False
        last_error = None
        resolved_model = model_name

        try:
            for turn in range(1, max_turns + 1):
                msg, usage, resolved_model, finish, llm_sec = await asyncio.to_thread(completion, messages, model_name)
                prompt_tok = int(usage.get("prompt_tokens", 0) or 0)
                comp_tok = int(usage.get("completion_tokens", 0) or 0)
                total_tok = int(usage.get("total_tokens", prompt_tok + comp_tok) or (prompt_tok + comp_tok))
                context.n_input_tokens += prompt_tok
                context.n_output_tokens += comp_tok
                llm_total_sec += llm_sec

                blocks = re.findall(r"```(?:python3?|py)?\s*\n(.*?)```", msg or "", re.S | re.I)
                code = blocks[-1] if blocks else (msg or "")
                script_name = f"attempt-{turn}.py"
                script_path = self.logs_dir / script_name
                script_path.write_text(code)
                (self.logs_dir / f"usage-{turn}.json").write_text(
                    json.dumps(
                        {
                            "turn": turn,
                            "model": resolved_model,
                            "finish_reason": finish,
                            "llm_elapsed_sec": llm_sec,
                            "usage": usage,
                        },
                        indent=2,
                    )
                )

                exec_t0 = time.monotonic()
                await environment.upload_file(script_path, "/work/create_model.py")
                result = await environment.exec(
                    "python3 /work/create_model.py && test -s /work/output.xlsx",
                    cwd="/work",
                    timeout_sec=90,
                )
                exec_sec = round(time.monotonic() - exec_t0, 3)
                exec_total_sec += exec_sec

                diag = "\n".join(x for x in (result.stdout, result.stderr) if x)
                (self.logs_dir / f"execution-{turn}.json").write_text(
                    json.dumps(
                        {
                            "turn": turn,
                            "exit_code": result.return_code,
                            "exec_elapsed_sec": exec_sec,
                            "stdout": (result.stdout or "")[-2000:],
                            "stderr": (result.stderr or "")[-3000:],
                        },
                        indent=2,
                    )
                )

                turns_log.append(
                    {
                        "turn": turn,
                        "script": script_name,
                        "llm_elapsed_sec": llm_sec,
                        "exec_elapsed_sec": exec_sec,
                        "prompt_tokens": prompt_tok,
                        "completion_tokens": comp_tok,
                        "total_tokens": total_tok,
                        "finish_reason": finish,
                        "exit_code": result.return_code,
                        "error_excerpt": "" if result.return_code == 0 else diag.strip()[-500:],
                    }
                )
                if result.return_code == 0:
                    delivered = True
                    last_error = None
                    break
                last_error = diag.strip()[-500:] or f"exit_code={result.return_code}"
                messages += [
                    {"role": "assistant", "content": msg or ""},
                    {
                        "role": "user",
                        "content": "Execution failed or /work/output.xlsx not created. Return a fixed complete script.\n"
                        + diag[-3000:],
                    },
                ]
        finally:
            total_sec = round(time.monotonic() - task_t0, 3)
            trajectory = {
                "model": resolved_model,
                "agent": f"{self.name()}@v{self.version()}",
                "delivered": delivered,
                "turns": len(turns_log),
                "max_turns": max_turns,
                "total_elapsed_sec": total_sec,
                "llm_elapsed_sec": round(llm_total_sec, 3),
                "exec_elapsed_sec": round(exec_total_sec, 3),
                "input_tokens": int(context.n_input_tokens),
                "output_tokens": int(context.n_output_tokens),
                "total_tokens": int(context.n_input_tokens + context.n_output_tokens),
                "last_error": last_error,
                "turns_log": turns_log,
            }
            (self.logs_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    # Convenience wrapper for running all tasks in DCFEval via Harbor CLI
    dataset = sys.argv[1] if len(sys.argv) > 1 else "DCFEval"
    model = sys.argv[2] if len(sys.argv) > 2 else os.getenv("DCF_MODEL", "gpt-4o")
    job_name = sys.argv[3] if len(sys.argv) > 3 else "frontier-eval"
    harbor_bin = str(Path(sys.executable).parent / "harbor")
    os.environ["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent) + os.pathsep + os.getenv("PYTHONPATH", "")
    cmd = [
        harbor_bin,
        "run",
        "-p",
        dataset,
        "-a",
        "dcf_benchmark.pilot:OpenAICompatAgent",
        "-m",
        model,
        "-n",
        os.getenv("DCF_CONCURRENCY", "4"),
        "--jobs-dir",
        str(Path(__file__).resolve().parent / "jobs"),
        "--job-name",
        job_name,
    ]
    os.execv(cmd[0], cmd)
