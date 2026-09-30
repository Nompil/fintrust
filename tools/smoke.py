"""Read-only HTTP checks against the running local practice server."""
import json
import statistics
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:5000"


def fetch(path, method="GET"):
    start = perf_counter()
    try:
        response = urlopen(Request(BASE + path, method=method), timeout=10)
    except HTTPError as error:
        response = error
    with response:
        body = response.read()
        return response.status, json.loads(body), (perf_counter() - start) * 1000


def main():
    checks = []
    for path, method, expected in [
        ("/v1/health", "GET", 200), ("/v1/accounts", "GET", 200),
        ("/v1/overview", "GET", 200), ("/v1/transactions", "GET", 400),
        ("/v1/insights", "GET", 400), ("/v1/missing", "GET", 404),
        ("/v1/health", "POST", 405),
    ]:
        status, _, elapsed = fetch(path, method)
        checks.append({"method": method, "path": path, "status": status,
                       "expected": expected, "milliseconds": round(elapsed, 2)})
        print(f"{method} {path}: {status} (expected {expected})")
    _, accounts, _ = fetch("/v1/accounts")
    if not accounts["data"]:
        raise RuntimeError("No accounts available; complete local setup first")
    account = accounts["data"][0]["account_id"]
    timings = []
    for _ in range(10):
        status, _, elapsed = fetch(f"/v1/transactions?account_id={account}&limit=10")
        if status != 200:
            raise RuntimeError(f"Transaction request returned {status}")
        timings.append(elapsed)
    result = {"checks": checks, "transaction_samples": 10,
              "median_ms": round(statistics.median(timings), 2),
              "max_ms": round(max(timings), 2),
              "scope": "Loopback HTTP, local PostgreSQL, serial requests; not a cloud load test."}
    target = Path(__file__).resolve().parents[1] / "output/local/smoke.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if any(c["status"] != c["expected"] for c in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
