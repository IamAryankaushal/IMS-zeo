#!/usr/bin/env python3
"""
simulate_failure.py — Simulates an RDBMS outage followed by an MCP failure.

Usage:
    python scripts/simulate_failure.py [--url http://localhost:8000] [--burst]
"""
import asyncio
import argparse
import json
import random
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE_URL = "http://localhost:8000"


def post(path: str, data: dict) -> dict:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.read().decode(), "status": e.code}


def get(path: str) -> dict:
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def separator(msg: str):
    print(f"\n{'─' * 60}")
    print(f"  {msg}")
    print('─' * 60)


def main(burst: bool = False):
    separator("Health check")
    try:
        health = get("/health")
        print(json.dumps(health, indent=2))
    except Exception as e:
        print(f"⚠️  Backend not reachable: {e}")
        print("Make sure the backend is running: docker compose up backend")
        return

    # ── Phase 1: RDBMS outage ────────────────────────────────────────────────
    separator("Phase 1 — Simulating RDBMS outage")
    n = 110 if burst else 5  # >100 triggers debounce
    print(f"Sending {n} signals for RDBMS_PRIMARY_01…")

    for i in range(n):
        resp = post("/signals/ingest", {
            "component_id": "RDBMS_PRIMARY_01",
            "component_type": "RDBMS",
            "error_type": random.choice([
                "CONNECTION_REFUSED", "DEADLOCK_DETECTED", "REPLICATION_LAG",
            ]),
            "message": f"[{i+1}/{n}] PostgreSQL primary unresponsive. "
                       f"Active connections: {random.randint(95, 100)}/100",
            "latency_ms": random.uniform(3000, 8000),
            "metadata": {
                "host": "db-primary-01.internal",
                "port": 5432,
                "simulation_run": True,
            },
        })
        if i == 0 or (i + 1) % 20 == 0 or i == n - 1:
            status = "✓" if resp.get("accepted") else "✗"
            print(f"  Signal {i+1}/{n}: {status} | queue={resp.get('queue_size', '?')}")
        time.sleep(0.02)  # 50 signals/sec

    print("⏳ Waiting 2s for processing…")
    time.sleep(2)

    # ── Phase 2: Cache degradation ───────────────────────────────────────────
    separator("Phase 2 — Simulating Cache degradation")
    for i in range(15):
        post("/signals/ingest", {
            "component_id": "CACHE_CLUSTER_01",
            "component_type": "CACHE",
            "error_type": "HIGH_EVICTION_RATE",
            "message": f"Redis cluster eviction rate: {random.randint(70, 95)}%",
            "latency_ms": random.uniform(50, 300),
        })
    print("  Sent 15 cache signals")
    time.sleep(1)

    # ── Phase 3: MCP host failure ────────────────────────────────────────────
    separator("Phase 3 — Simulating MCP host failure")
    for i in range(8):
        post("/signals/ingest", {
            "component_id": "MCP_HOST_PROD",
            "component_type": "MCP",
            "error_type": "HEALTH_CHECK_FAILED",
            "message": f"MCP host failed health check #{i+1}. Latency: {random.randint(1500, 5000)}ms",
            "latency_ms": random.uniform(1500, 5000),
        })
    print("  Sent 8 MCP host signals")
    time.sleep(1)

    # ── Phase 4: Queue backup ────────────────────────────────────────────────
    separator("Phase 4 — Simulating Kafka queue backup")
    post("/signals/ingest", {
        "component_id": "KAFKA_BROKER_01",
        "component_type": "QUEUE",
        "error_type": "CONSUMER_LAG_CRITICAL",
        "message": "Consumer group 'orders' lag: 2.4M messages. Throughput degraded by 80%.",
        "latency_ms": None,
        "metadata": {"consumer_group": "orders", "lag": 2_400_000},
    })
    print("  Sent Kafka lag signal")

    # ── Results ──────────────────────────────────────────────────────────────
    separator("Resulting work items")
    time.sleep(2)  # let worker process
    try:
        data = get("/workitems")
        items = data.get("items", [])
        print(f"Total work items: {data.get('total', 0)}\n")
        for item in items[:10]:
            print(f"  [{item['priority']}] {item['component_id']}")
            print(f"       Status: {item['status']} | Signals: {item['signal_count']}")
            print(f"       Title: {item['title']}")
            print()
    except Exception as e:
        print(f"Could not list work items: {e}")

    separator("Done")
    print("Open the dashboard at http://localhost:3000 to see the incidents.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--burst", action="store_true",
                        help="Send 110 signals to trigger debounce (100-signal threshold)")
    args = parser.parse_args()
    BASE_URL = args.url
    main(burst=args.burst)
