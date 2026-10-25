"""Run the NLU evaluation for rules, model and hybrid, then print the comparison.

Usage (from repo root):
    python -m ai.nlu.run_all_evals
    python -m ai.nlu.run_all_evals --backends rules          # no GPU needed

Each backend's report is saved exactly as ``python -m ai.nlu.evaluate`` saves
it (ai/docs/nlu-eval-<name>.md + .json). For the model backends this also
measures, on this machine, the model load time and GPU memory, and writes
them to ai/docs/nlu-eval-runtime.json. Nothing is estimated: a backend that
can't run is skipped with the reason printed.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any

from ai.nlu.evaluate import DOCS_DIR, compare_reports, print_report, run_eval, to_markdown

BACKENDS = ("rules", "model", "hybrid")


def _save(report: dict[str, Any]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / f"nlu-eval-{report['name']}.md").write_text(to_markdown(report), encoding="utf-8")
    (DOCS_DIR / f"nlu-eval-{report['name']}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_model_measured() -> dict[str, Any] | None:
    """Load the NLU model once and measure it; None (reason printed) if it can't load."""
    from ai.inference import load_model

    reason = load_model._unavailable_reason(load_model.ADAPTER_DIR)
    if reason:
        print(f"[SKIP] model and hybrid backends: {reason}")
        return None

    import torch

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    t0 = time.perf_counter()
    try:
        load_model.get_model()
    except load_model.ModelUnavailableError as exc:
        print(f"[SKIP] model and hybrid backends: {exc}")
        return None
    runtime: dict[str, Any] = {
        "base_model": load_model.BASE_MODEL,
        "load_seconds": round(time.perf_counter() - t0, 1),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "platform": platform.platform(),
    }
    if torch.cuda.is_available():
        runtime["gpu_memory_after_load_gb"] = round(torch.cuda.memory_allocated() / 1024**3, 2)
        runtime["gpu_total_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
    return runtime


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate rules, model and hybrid NLU backends.")
    ap.add_argument("--file", type=Path, default=Path("ai/nlu/eval_set.jsonl"))
    ap.add_argument("--backends", nargs="+", choices=BACKENDS, default=list(BACKENDS))
    ap.add_argument("--prefix", default="qwen3-4b-",
                    help="report-name prefix for the model backends (rules is always 'rules')")
    args = ap.parse_args()

    if not args.file.exists():
        print(f"[ERROR] eval file {args.file} not found.")
        sys.exit(2)

    runtime = None
    if {"model", "hybrid"} & set(args.backends):
        runtime = _load_model_measured()

    names: list[str] = []
    for backend in args.backends:
        if backend != "rules" and runtime is None:
            continue
        name = backend if backend == "rules" else f"{args.prefix}{backend}"
        report = run_eval(backend, args.file)
        report["name"] = name
        print_report(report)
        _save(report)
        names.append(name)
        if runtime is not None and backend != "rules":
            runtime[f"{backend}_latency_ms"] = report["latency_ms"]

    if runtime is not None:
        try:
            import torch

            if torch.cuda.is_available():
                runtime["gpu_peak_memory_gb"] = round(torch.cuda.max_memory_allocated() / 1024**3, 2)
        except ImportError:
            pass
        (DOCS_DIR / "nlu-eval-runtime.json").write_text(json.dumps(runtime, indent=2), encoding="utf-8")
        print("\n=== runtime on this machine ===")
        for key, value in runtime.items():
            print(f"  {key:26}: {value}")

    if names:
        print("\n=== comparison ===")
        compare_reports(names)


if __name__ == "__main__":
    main()
