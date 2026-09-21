"""
Local integration test script for Promo Simulator Core Service.

Usage:
  1. Start the server: run_local.bat
  2. In a separate terminal:  python test_local.py

Tests all endpoints and validates response shapes.
"""

import sys
import time
import requests

BASE = "http://localhost:9000/itaap-digitalit-promosimulator-coreservice"

PASS = 0
FAIL = 0


def report(name, ok, detail=""):
    global PASS, FAIL
    icon = "PASS" if ok else "FAIL"
    PASS += ok
    FAIL += (not ok)
    msg = f"  [{icon}] {name}"
    if detail:
        msg += f"  -- {detail}"
    print(msg)


def test_health():
    print("\n--- Health Check ---")
    try:
        r = requests.get(f"{BASE}/api/health", timeout=30)
        data = r.json()
        report("GET /api/health returns 200", r.status_code == 200)
        report("status is 'ok'", data.get("status") == "ok", f"got: {data.get('status')}")
        report("skus_in_data > 0", data.get("skus_in_data", 0) > 0, f"got: {data.get('skus_in_data')}")
        report("data_years present", bool(data.get("data_years")), f"got: {data.get('data_years')}")
        return True
    except requests.ConnectionError:
        report("Server reachable", False, "Cannot connect — is the server running?")
        return False
    except Exception as e:
        report("Health check", False, str(e))
        return False


def test_skus():
    print("\n--- SKU Listing ---")
    r = requests.get(f"{BASE}/api/skus", timeout=30)
    data = r.json()
    report("GET /api/skus returns 200", r.status_code == 200)
    report("skus is a list", isinstance(data.get("skus"), list))
    report("at least 1 SKU returned", len(data.get("skus", [])) > 0, f"got: {len(data.get('skus', []))}")

    if data.get("skus"):
        first = data["skus"][0]
        report("SKU has 'sku' field", "sku" in first)
        report("SKU has 'band' field", "band" in first)
        report("ref_spend present", "ref_spend" in data)
    return data.get("skus", [])


def test_retro(skus):
    print("\n--- Retro Simulation ---")
    test_skus_list = [s["sku"] for s in skus[:3]]
    payload = {
        "skus": test_skus_list,
        "year": 2025,
        "period": "Full year",
        "objective": "profit",
        "max_discount": 0.30,
        "budget_multiplier": 1.0,
        "unconstrained": True,
    }
    print(f"  Running with SKUs: {test_skus_list}")
    start = time.time()
    r = requests.post(f"{BASE}/api/run_retro", json=payload, timeout=300)
    elapsed = time.time() - start
    print(f"  Response time: {elapsed:.1f}s")

    report("POST /api/run_retro returns 200", r.status_code == 200, f"got: {r.status_code}")
    if r.status_code != 200:
        print(f"  Response body: {r.text[:500]}")
        return

    data = r.json()
    report("status is 'ok'", data.get("status") == "ok")
    report("hero section present", "hero" in data)
    report("hero.value present", bool(data.get("hero", {}).get("value")))
    report("hero.verdict present", bool(data.get("hero", {}).get("verdict")))
    report("tiers present", "tiers" in data)
    report("tiers.definitely_do present", "definitely_do" in data.get("tiers", {}))
    report("compare section present", "compare" in data)
    report("compare.current present", "current" in data.get("compare", {}))
    report("compare.recommended present", "recommended" in data.get("compare", {}))
    report("timeline present", "timeline" in data)
    report("weekly_chart present", "weekly_chart" in data)
    report("weekly_chart has weeks", len(data.get("weekly_chart", {}).get("weeks", [])) > 0)
    report("why_reasons present", "why_reasons" in data)
    report("deep_dive.sku_table present", "sku_table" in data.get("deep_dive", {}))
    report("elasticity present", "elasticity" in data)
    report("roi present", "roi" in data)
    report("response time < 120s", elapsed < 120, f"{elapsed:.1f}s")


def test_plan(skus):
    print("\n--- Plan Simulation ---")
    test_skus_list = [s["sku"] for s in skus[:3]]
    payload = {
        "skus": test_skus_list,
        "plan_year": 2026,
        "base_year": 2025,
        "use_trend": True,
        "objective": "profit",
        "max_discount": 0.30,
        "budget_multiplier": 1.0,
        "ref_year": 2025,
        "unconstrained": True,
    }
    print(f"  Running with SKUs: {test_skus_list}")
    start = time.time()
    r = requests.post(f"{BASE}/api/run_plan", json=payload, timeout=300)
    elapsed = time.time() - start
    print(f"  Response time: {elapsed:.1f}s")

    report("POST /api/run_plan returns 200", r.status_code == 200, f"got: {r.status_code}")
    if r.status_code != 200:
        print(f"  Response body: {r.text[:500]}")
        return

    data = r.json()
    report("status is 'ok'", data.get("status") == "ok")
    report("hero section present", "hero" in data)
    report("compare_vs_base is True", data.get("compare_vs_base") is True)
    report("tiers present", "tiers" in data)
    report("weekly_chart present", "weekly_chart" in data)
    report("elasticity present", "elasticity" in data)
    report("response time < 120s", elapsed < 120, f"{elapsed:.1f}s")


def test_retro_constrained(skus):
    print("\n--- Retro (Constrained Budget) ---")
    test_skus_list = [s["sku"] for s in skus[:3]]
    payload = {
        "skus": test_skus_list,
        "year": 2025,
        "period": "Q4",
        "objective": "profit",
        "max_discount": 0.25,
        "budget_multiplier": 0.8,
        "unconstrained": False,
    }
    print(f"  Running with SKUs: {test_skus_list}, period=Q4, budget=0.8x")
    start = time.time()
    r = requests.post(f"{BASE}/api/run_retro", json=payload, timeout=300)
    elapsed = time.time() - start
    print(f"  Response time: {elapsed:.1f}s")

    report("POST /api/run_retro (constrained) returns 200", r.status_code == 200, f"got: {r.status_code}")
    if r.status_code != 200:
        print(f"  Response body: {r.text[:500]}")
        return

    data = r.json()
    report("status is 'ok'", data.get("status") == "ok")
    report("quarterly_allocation present", "quarterly_allocation" in data)
    report("response time < 120s", elapsed < 120, f"{elapsed:.1f}s")


def test_retro_turnover(skus):
    print("\n--- Retro (Turnover Objective) ---")
    test_skus_list = [s["sku"] for s in skus[:3]]
    payload = {
        "skus": test_skus_list,
        "year": 2025,
        "period": "Full year",
        "objective": "turnover",
        "max_discount": 0.30,
        "budget_multiplier": 1.0,
        "unconstrained": True,
        "alpha": 0.0,
    }
    start = time.time()
    r = requests.post(f"{BASE}/api/run_retro", json=payload, timeout=300)
    elapsed = time.time() - start
    print(f"  Response time: {elapsed:.1f}s")

    report("Turnover mode returns 200", r.status_code == 200, f"got: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        report("objective is 'turnover'", data.get("objective") == "turnover")


if __name__ == "__main__":
    print("=" * 60)
    print("  PROMO SIMULATOR CORE SERVICE — LOCAL TEST")
    print("=" * 60)

    if not test_health():
        print("\n  Server not reachable. Start it first with: run_local.bat")
        sys.exit(1)

    skus = test_skus()
    if not skus:
        print("\n  No SKUs returned — check that the pickle file is in place.")
        sys.exit(1)

    test_retro(skus)
    test_plan(skus)
    test_retro_constrained(skus)
    test_retro_turnover(skus)

    print("\n" + "=" * 60)
    print(f"  RESULTS:  {PASS} passed,  {FAIL} failed")
    print("=" * 60)
    sys.exit(0 if FAIL == 0 else 1)
