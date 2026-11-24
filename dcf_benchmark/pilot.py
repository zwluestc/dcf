"""Standard OpenAI-compatible Harbor agent adapter for running frontier model evaluations on DCFEval."""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from harbor.agents.base import BaseAgent


def completion(messages, model_name):
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    key = os.environ["OPENAI_API_KEY"]
    max_tokens = int(os.getenv("DCF_MAX_TOKENS", "16000"))
    payload = {"model": model_name, "messages": messages, "max_tokens": max_tokens, "stream": False}
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
        if r.returncode:
            raise RuntimeError(f"transport error: curl exit {r.returncode}: {r.stderr[:200]}")
        body, _, status = r.stdout.rpartition("\n")
        if status != "200":
            raise RuntimeError(f"HTTP {status}: {body.replace(key, '[redacted]')[:300]}")
        reply = json.loads(body)
    choice = reply["choices"][0]
    return choice["message"]["content"], reply.get("usage", {}), reply.get("model", model_name), choice.get("finish_reason")


class OpenAICompatAgent(BaseAgent):
    """Multi-turn code-execution agent inside the isolated Harbor container (up to 3 repair rounds)."""

    @staticmethod
    def name():
        return "dcf-openai-compat"

    def version(self):
        return "2"

    async def setup(self, environment):
        pass

    async def run(self, instruction, environment, context):
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
        for turn in range(1, max_turns + 1):
            msg, usage, resolved_model, finish = await asyncio.to_thread(completion, messages, model_name)
            context.n_input_tokens += usage.get("prompt_tokens", 0)
            context.n_output_tokens += usage.get("completion_tokens", 0)

            blocks = re.findall(r"```(?:python3?|py)?\s*\n(.*?)```", msg or "", re.S | re.I)
            code = blocks[-1] if blocks else (msg or "")
            script_path = self.logs_dir / f"attempt-{turn}.py"
            script_path.write_text(code)
            (self.logs_dir / f"usage-{turn}.json").write_text(
                json.dumps({"model": resolved_model, "finish_reason": finish, "usage": usage}, indent=2)
            )

            await environment.upload_file(script_path, "/work/create_model.py")
            result = await environment.exec("python3 /work/create_model.py && test -s /work/output.xlsx", cwd="/work", timeout_sec=90)
            (self.logs_dir / f"execution-{turn}.json").write_text(
                json.dumps(
                    {
                        "exit_code": result.return_code,
                        "stdout": (result.stdout or "")[-2000:],
                        "stderr": (result.stderr or "")[-3000:],
                    },
                    indent=2,
                )
            )
            if result.return_code == 0:
                return
            diag = "\n".join(x for x in (result.stdout, result.stderr) if x)
            messages += [
                {"role": "assistant", "content": msg or ""},
                {"role": "user", "content": "Execution failed or /work/output.xlsx not created. Return a fixed complete script.\n" + diag[-3000:]},
            ]


if __name__ == "__main__":
    # Convenience wrapper for running all 10 tasks via Harbor CLI
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
