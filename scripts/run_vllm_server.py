#!/usr/bin/env python
"""
Запуск vLLM сервера для инференса.
Пример использования:
    python scripts/run_vllm_server.py --model Qwen/Qwen2.5-7B-Instruct --port 8000
"""

import argparse
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--tensor-parallel-size", type=int, default=1)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.8)
    args = parser.parse_args()

    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", args.model,
        "--port", str(args.port),
        "--tensor-parallel-size", str(args.tensor_parallel_size),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
        "--max-model-len", "8192",
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
