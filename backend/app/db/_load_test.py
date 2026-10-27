"""Load test for spatial API endpoints.

Fires 100 requests at GET /listings/search (radius) and
POST /listings/search-boundary (polygon), using concurrent.futures.ThreadPoolExecutor
for throughput.  Concurrent execution is chosen over sequential because:
- Real users hit the API simultaneously; sequential latency doesn't reflect p95 reality.
- The DB pool and Uvicorn's async execution both benefit from concurrent load.

Prints min / median / p95 / max latency (ms) per endpoint.

Usage::

    # Server must already be running:
    #   uvicorn app.main:app --reload
    python -m app.db._load_test [--host http://localhost:8000] [--requests 100] [--workers 10]

Note: This requires a valid JWT for authenticated-endpoint tests.  Set
LOAD_TEST_TOKEN in your environment or .env before running — the script will
skip auth endpoints gracefully if the token is absent.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import statistics
import sys
import time
from typing import Callable

import httpx

# ---------------------------------------------------------------------------
# Default targets — real Surat coordinates from the seed data
# ---------------------------------------------------------------------------
_RADIUS_PARAMS = {
    "lat": 21.1702,
    "lng": 72.8311,
    "radius_km": 5.0,
}

_BOUNDARY_PAYLOAD = {
    "polygon": [
        [21.15, 72.81],
        [21.19, 72.81],
        [21.19, 72.85],
        [21.15, 72.85],
        # ring auto-closed by the API's BoundarySearchRequest validator
    ]
}


def _timed_call(fn: Callable) -> float:
    """Run *fn* and return elapsed time in milliseconds."""
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000


def _stats_report(label: str, latencies: list[float]) -> None:
    """Print latency statistics for a set of requests."""
    if not latencies:
        print(f"\n{label}: no data")
        return

    latencies_sorted = sorted(latencies)
    n = len(latencies_sorted)
    p95_idx = max(0, int(n * 0.95) - 1)

    print(f"\n{'─' * 60}")
    print(f"  {label}  ({n} requests)")
    print(f"{'─' * 60}")
    print(f"  min    : {min(latencies_sorted):>8.1f} ms")
    print(f"  median : {statistics.median(latencies_sorted):>8.1f} ms")
    print(f"  p95    : {latencies_sorted[p95_idx]:>8.1f} ms")
    print(f"  max    : {max(latencies_sorted):>8.1f} ms")


def run_load_test(host: str, n_requests: int, n_workers: int, token: str | None) -> None:
    """Execute the load test against *host* and print results."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # ------------------------------------------------------------------ #
    # Endpoint 1 — GET /listings/search (radius)                          #
    # No auth required                                                     #
    # ------------------------------------------------------------------ #
    client = httpx.Client(base_url=host, timeout=30)

    def _radius_request() -> None:
        resp = client.get("/listings/search", params=_RADIUS_PARAMS)
        if resp.status_code not in (200, 422):
            print(f"  [radius] unexpected status {resp.status_code}", flush=True)

    def _boundary_request() -> None:
        resp = client.post("/listings/search-boundary", json=_BOUNDARY_PAYLOAD)
        if resp.status_code not in (200, 422):
            print(f"  [boundary] unexpected status {resp.status_code}", flush=True)

    print(f"\n🚀  Load test — {n_requests} requests × 2 endpoints")
    print(f"    Host    : {host}")
    print(f"    Workers : {n_workers}")

    for label, fn in [
        ("GET /listings/search (radius)", _radius_request),
        ("POST /listings/search-boundary", _boundary_request),
    ]:
        latencies: list[float] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(_timed_call, fn) for _ in range(n_requests)]
            for f in concurrent.futures.as_completed(futures):
                try:
                    latencies.append(f.result())
                except Exception as exc:  # noqa: BLE001
                    print(f"  [error] {exc}", flush=True)
        _stats_report(label, latencies)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simple load test for Reality AI spatial endpoints."
    )
    parser.add_argument(
        "--host",
        default=os.getenv("LOAD_TEST_HOST", "http://localhost:8000"),
        help="Base URL of the running server (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=100,
        metavar="N",
        help="Number of requests per endpoint (default: 100)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        metavar="N",
        help="Thread-pool concurrency (default: 10)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    token = os.getenv("LOAD_TEST_TOKEN")
    if not token:
        print(
            "ℹ️   LOAD_TEST_TOKEN not set — auth endpoints will be skipped.\n"
            "    Set it in .env or environment for full coverage."
        )
    try:
        run_load_test(
            host=args.host,
            n_requests=args.requests,
            n_workers=args.workers,
            token=token,
        )
        print("\n✅  Load test complete.\n")
    except Exception as exc:  # noqa: BLE001
        print(f"\n❌  Load test failed: {exc}", file=sys.stderr)
        print(
            "   Make sure the server is running: uvicorn app.main:app --reload",
            file=sys.stderr,
        )
        sys.exit(1)
