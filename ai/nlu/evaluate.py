"""Field-by-field evaluation of a query parser against a labeled eval set.

Usage (from repo root):
    python -m ai.nlu.evaluate --parser rules  --file ai/nlu/eval_set.jsonl
    python -m ai.nlu.evaluate --parser hybrid --file ai/nlu/eval_set.jsonl
    python -m ai.nlu.evaluate --compare rules model hybrid

Eval rows: {"query": ..., "expected": {<the 7 model-output fields>}, "tag": ...}
where prices in "expected" are {"amount", "unit"} objects, exactly like the
model's output (see ai/nlu/LABELING_RULES.md). "tag" is optional.

Each run writes ai/docs/nlu-eval-<name>.md (for the report) and a .json
sidecar that --compare reads.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from ai.nlu.schema import ParsedQuery, validate_model_output

DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
SCALAR_FIELDS = ("is_property_query", "bhk", "locality", "property_type", "price_min", "price_max")
ALL_FIELDS = (*SCALAR_FIELDS, "keywords")


def _load_parser(name: str) -> Callable[[str], ParsedQuery]:
    if name == "rules":
        from ai.nlu.rules import parse_with_rules
        return parse_with_rules
    os.environ["NLU_BACKEND"] = name
    try:
        from ai.nlu.query_parser import parse_query
    except ImportError as exc:
        print(f"[ERROR] --parser {name} needs ai.nlu.query_parser.parse_query, which "
              f"isn't available yet ({exc}). Build it (playbook Prompt D.2) first.")
        sys.exit(2)
    if hasattr(parse_query, "cache_clear"):
        parse_query.cache_clear()
    return parse_query


def _price_eq(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=1e-6)


def compare(expected: ParsedQuery, got: ParsedQuery) -> dict[str, bool]:
    """Per-field correctness for one row (keywords as exact-set match)."""
    result = {}
    for f in SCALAR_FIELDS:
        e, g = getattr(expected, f), getattr(got, f)
        result[f] = _price_eq(e, g) if f.startswith("price") else e == g
    result["keywords"] = set(expected.keywords) == set(got.keywords)
    return result


def _pctl(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[idx]


def _summary(pq: ParsedQuery) -> dict[str, Any]:
    return {f: (list(getattr(pq, f)) if f == "keywords" else getattr(pq, f)) for f in ALL_FIELDS}


def run_eval(parser_name: str, eval_file: Path) -> dict[str, Any]:
    parse = _load_parser(parser_name)
    rows = [json.loads(line) for line in eval_file.read_text(encoding="utf-8").splitlines()
            if line.strip()]

    field_hits: dict[str, int] = defaultdict(int)
    tag_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    kw_tp = kw_fp = kw_fn = 0
    exact = 0
    model_ok = 0
    latencies: list[float] = []
    failures: list[dict[str, Any]] = []
    bad_rows: list[int] = []
    evaluated = 0

    for i, row in enumerate(rows, 1):
        expected = validate_model_output(row.get("expected"))
        if expected is None or "query" not in row:
            bad_rows.append(i)
            continue
        evaluated += 1
        t0 = time.perf_counter()
        got = parse(row["query"])
        latencies.append((time.perf_counter() - t0) * 1000)
        if got.source in ("model", "hybrid"):
            model_ok += 1

        fields = compare(expected, got)
        for f, ok in fields.items():
            field_hits[f] += ok
        all_ok = all(fields.values())
        exact += all_ok

        e_kw, g_kw = set(expected.keywords), set(got.keywords)
        kw_tp += len(e_kw & g_kw)
        kw_fp += len(g_kw - e_kw)
        kw_fn += len(e_kw - g_kw)

        tag = row.get("tag") or "untagged"
        tag_stats[tag]["n"] += 1
        tag_stats[tag]["exact"] += all_ok
        for f, ok in fields.items():
            tag_stats[tag][f] += ok

        if not all_ok:
            failures.append({
                "line": i, "query": row["query"], "tag": tag,
                "wrong": [f for f, ok in fields.items() if not ok],
                "expected": _summary(expected), "predicted": _summary(got),
                "source": got.source,
            })

    precision = kw_tp / (kw_tp + kw_fp) if kw_tp + kw_fp else 1.0
    recall = kw_tp / (kw_tp + kw_fn) if kw_tp + kw_fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    n = evaluated or 1

    report = {
        "name": parser_name,
        "eval_file": str(eval_file),
        "n_rows": len(rows),
        "n_evaluated": evaluated,
        "bad_rows": bad_rows,
        "field_accuracy": {f: field_hits[f] / n for f in ALL_FIELDS},
        "keywords_f1": f1,
        "exact_match": exact / n,
        "model_output_valid_rate": (model_ok / n) if parser_name != "rules" else None,
        "latency_ms": {"mean": statistics.fmean(latencies) if latencies else float("nan"),
                       "median": statistics.median(latencies) if latencies else float("nan"),
                       "p95": _pctl(latencies, 0.95)},
        "by_tag": {tag: {"n": s["n"], "exact_match": s["exact"] / s["n"],
                         **{f: s[f] / s["n"] for f in ALL_FIELDS}}
                   for tag, s in sorted(tag_stats.items())},
        "worst_failures": sorted(failures, key=lambda f: -len(f["wrong"]))[:15],
    }
    return report


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def to_markdown(r: dict[str, Any]) -> str:
    lines = [
        f"# NLU evaluation — `{r['name']}` parser",
        "",
        f"Eval file: `{r['eval_file']}` · rows evaluated: {r['n_evaluated']} of {r['n_rows']}"
        + (f" · skipped invalid rows (line numbers): {r['bad_rows']}" if r["bad_rows"] else ""),
        "",
        "## Overall",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Exact match (all 7 fields) | {_pct(r['exact_match'])} |",
        *[f"| {f} accuracy | {_pct(v)} |" for f, v in r["field_accuracy"].items()],
        f"| keywords F1 (micro) | {_pct(r['keywords_f1'])} |",
        f"| Valid model output (no fallback) | {_pct(r['model_output_valid_rate'])} |",
        f"| Latency mean / median / p95 (ms) | {r['latency_ms']['mean']:.1f} / "
        f"{r['latency_ms']['median']:.1f} / {r['latency_ms']['p95']:.1f} |",
        "",
        "## By tag",
        "",
        "| Tag | n | Exact | is_prop | bhk | locality | type | price_min | price_max | keywords |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for tag, s in r["by_tag"].items():
        lines.append(
            f"| {tag} | {s['n']} | {_pct(s['exact_match'])} | {_pct(s['is_property_query'])} | "
            f"{_pct(s['bhk'])} | {_pct(s['locality'])} | {_pct(s['property_type'])} | "
            f"{_pct(s['price_min'])} | {_pct(s['price_max'])} | {_pct(s['keywords'])} |"
        )
    lines += ["", f"## Worst failures (up to 15)", ""]
    for f in r["worst_failures"]:
        diffs = ", ".join(f"{k}: expected `{f['expected'][k]}` got `{f['predicted'][k]}`"
                          for k in f["wrong"])
        lines.append(f"- line {f['line']} [{f['tag']}, source={f['source']}] "
                     f"`{f['query']}` — {diffs}")
    return "\n".join(lines) + "\n"


def print_report(r: dict[str, Any]) -> None:
    print(f"\n=== {r['name']} parser on {r['n_evaluated']} rows ===")
    if r["bad_rows"]:
        print(f"  [WARN] skipped {len(r['bad_rows'])} invalid eval rows: lines {r['bad_rows']}")
    print(f"  exact match          : {_pct(r['exact_match'])}")
    for f, v in r["field_accuracy"].items():
        print(f"  {f:<20} : {_pct(v)}")
    print(f"  keywords F1          : {_pct(r['keywords_f1'])}")
    if r["model_output_valid_rate"] is not None:
        print(f"  valid model output   : {_pct(r['model_output_valid_rate'])}")
        if r["model_output_valid_rate"] == 0:
            print("  [WARN] every query fell back to rules — is the model/adapter available?")
    lat = r["latency_ms"]
    print(f"  latency ms           : mean {lat['mean']:.1f} · median {lat['median']:.1f} · p95 {lat['p95']:.1f}")
    print("  by tag (exact match) : " + ", ".join(
        f"{t}={_pct(s['exact_match'])} (n={s['n']})" for t, s in r["by_tag"].items()))
    print(f"\n  worst failures:")
    for f in r["worst_failures"]:
        print(f"   line {f['line']:>3} [{f['tag']}] {f['query']!r}")
        for k in f["wrong"]:
            print(f"       {k}: expected {f['expected'][k]!r}, got {f['predicted'][k]!r}")


def compare_reports(names: list[str]) -> None:
    reports = []
    for name in names:
        path = DOCS_DIR / f"nlu-eval-{name}.json"
        if not path.exists():
            print(f"[ERROR] {path} not found — run --parser {name} first.")
            sys.exit(2)
        reports.append(json.loads(path.read_text(encoding="utf-8")))
    metrics = [("exact match", lambda r: _pct(r["exact_match"]))]
    metrics += [(f, (lambda f: lambda r: _pct(r["field_accuracy"][f]))(f)) for f in ALL_FIELDS]
    metrics += [("keywords F1", lambda r: _pct(r["keywords_f1"])),
                ("valid model output", lambda r: _pct(r["model_output_valid_rate"])),
                ("latency median ms", lambda r: f"{r['latency_ms']['median']:.1f}"),
                ("latency p95 ms", lambda r: f"{r['latency_ms']['p95']:.1f}")]
    tags = sorted({t for r in reports for t in r["by_tag"]})
    metrics += [(f"exact [{t}]", (lambda t: lambda r: _pct(r["by_tag"][t]["exact_match"])
                                  if t in r["by_tag"] else "-")(t)) for t in tags]

    header = "| Metric | " + " | ".join(r["name"] for r in reports) + " |"
    print(header)
    print("|---|" + "---|" * len(reports))
    for label, fn in metrics:
        print(f"| {label} | " + " | ".join(fn(r) for r in reports) + " |")


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate an NLU parser on a labeled eval set.")
    ap.add_argument("--parser", choices=["rules", "model", "hybrid"])
    ap.add_argument("--file", type=Path, default=Path("ai/nlu/eval_set.jsonl"))
    ap.add_argument("--name", help="report name (default: the parser name)")
    ap.add_argument("--compare", nargs="+", metavar="NAME", help="side-by-side table of saved reports")
    args = ap.parse_args()

    if args.compare:
        compare_reports(args.compare)
        return
    if not args.parser:
        ap.error("--parser or --compare is required")
    if not args.file.exists():
        print(f"[ERROR] eval file {args.file} not found. Write it by hand per "
              "ai/nlu/LABELING_RULES.md (see eval_set.example.jsonl for the format).")
        sys.exit(2)

    report = run_eval(args.parser, args.file)
    report["name"] = args.name or args.parser
    print_report(report)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    md_path = DOCS_DIR / f"nlu-eval-{report['name']}.md"
    md_path.write_text(to_markdown(report), encoding="utf-8")
    (DOCS_DIR / f"nlu-eval-{report['name']}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] report written to {md_path}")


if __name__ == "__main__":
    main()
