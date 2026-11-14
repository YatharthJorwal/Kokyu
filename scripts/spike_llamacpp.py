"""K1-01 spike: a large MoE on llama.cpp with expert weights on the CPU.

Starts llama-server once per `--n-cpu-moe` value, waits for it, runs the same
generation, and prints load time, VRAM, the server's RAM and tokens/s (from the
server's own timings). Nothing is installed or downloaded; every path comes
from the command line.

    .venv\\Scripts\\python.exe scripts\\spike_llamacpp.py --server <llama-server.exe> --model <file.gguf> --ncmoe 40 30 24

Windows only (uses nvidia-smi and PowerShell for the measurements).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROMPT = (
    "Write a warm, detailed paragraph (about 200 words) describing an autumn evening "
    "walk through a quiet Japanese town, then list three things the walker notices."
)


def vram_used_mib() -> int:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=True,
    ).stdout
    return int(out.strip().splitlines()[0])


def process_ram_gib(pid: int) -> tuple[float, float]:
    """(working set, private bytes) of the server process, in GiB."""
    cmd = f"$p=Get-Process -Id {pid}; '{{0}} {{1}}' -f $p.WorkingSet64,$p.PrivateMemorySize64"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True).stdout.split()
    return (int(out[0]) / 2**30, int(out[1]) / 2**30) if len(out) == 2 else (0.0, 0.0)


def get(url: str, timeout: float = 2.0) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status
    except Exception:  # noqa: BLE001 -- polling
        return 0


FILLER = (
    "Background notes about the user, kept for context. They like tea, long walks, old films, "
    "and talking about their day in detail. They are building a desktop companion app. "
) * 60   # about 2,000 tokens, the size of a real persona + memory prompt


def chat(port: int, max_tokens: int, long_prompt: bool = False) -> dict:
    messages = [{"role": "user", "content": PROMPT}]
    if long_prompt:
        messages.insert(0, {"role": "system", "content": FILLER})
    body = json.dumps({
        "messages": messages,
        "cache_prompt": False,
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def run_one(args: argparse.Namespace, ncmoe: int, baseline_vram: int) -> dict:
    server = Path(args.server)
    env = dict(os.environ)
    cuda_dir = server.parent / "cuda_v12"
    if cuda_dir.is_dir():                     # Ollama's bundled server keeps CUDA in a subfolder
        env["PATH"] = f"{cuda_dir};{server.parent};{env.get('PATH', '')}"
        env.setdefault("GGML_BACKEND_PATH", str(cuda_dir / "ggml-cuda.dll"))
    cmd = [
        str(server), "-m", args.model, "--port", str(args.port), "--host", "127.0.0.1",
        "-ngl", "99", "--n-cpu-moe", str(ncmoe), "-c", str(args.ctx), "-fa", "on",
        "--jinja", "--threads", str(args.threads), "--no-webui",
    ]
    if args.threads_batch:
        cmd += ["--threads-batch", str(args.threads_batch)]
    log = open(Path(args.logdir) / f"llama-server-ncmoe{ncmoe}.log", "w", encoding="utf-8")
    started = time.monotonic()
    proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        while get(f"http://127.0.0.1:{args.port}/health") != 200:
            if proc.poll() is not None:
                return {"ncmoe": ncmoe, "error": f"server exited with {proc.returncode} (see log)"}
            if time.monotonic() - started > 600:
                return {"ncmoe": ncmoe, "error": "not healthy after 600 s"}
            time.sleep(1)
        load_s = time.monotonic() - started
        chat(args.port, 16)                    # warm-up
        result = chat(args.port, args.max_tokens, args.long_prompt)
        t = result.get("timings", {})
        ws, private = process_ram_gib(proc.pid)
        return {
            "ncmoe": ncmoe,
            "load_s": round(load_s, 1),
            "vram_mib": vram_used_mib() - baseline_vram,
            "ram_working_set_gib": round(ws, 1),
            "ram_private_gib": round(private, 1),
            "prompt_tokens": t.get("prompt_n"),
            "prompt_tok_s": round(t.get("prompt_per_second", 0.0), 1),
            "threads": args.threads,
            "threads_batch": args.threads_batch,
            "gen_tok_s": round(t.get("predicted_per_second", 0.0), 1),
            "gen_tokens": t.get("predicted_n"),
            "sample": result["choices"][0]["message"]["content"][:160].replace("\n", " "),
        }
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        time.sleep(3)                          # let the driver release VRAM


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--server", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--ncmoe", type=int, nargs="+", required=True)
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--ctx", type=int, default=8192)
    p.add_argument("--threads", type=int, default=6)
    p.add_argument("--threads-batch", type=int, default=0, help="threads for prompt reading (default: same as --threads)")
    p.add_argument("--max-tokens", type=int, default=256)
    p.add_argument("--logdir", default=".")
    p.add_argument("--long-prompt", action="store_true", help="add ~2,000 tokens of context, like a real turn")
    args = p.parse_args()
    baseline = vram_used_mib()
    print(f"baseline VRAM in use (desktop etc.): {baseline} MiB", flush=True)
    for n in args.ncmoe:
        print(json.dumps(run_one(args, n, baseline)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
