"""Supabase client for Life Hub web app.

Standalone version of db_client.py for deployment (no Keychain dependency).
Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from environment variables.
"""

import json
import os
from datetime import date, timedelta

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ktapphwujodloasauasm.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    raise RuntimeError("Set SUPABASE_SERVICE_ROLE_KEY env var")

_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
_REST = f"{SUPABASE_URL}/rest/v1"


# --- Read ---

def get_daily(target_date=None):
    if target_date is None or target_date == "today":
        target_date = date.today().isoformat()
    resp = httpx.get(f"{_REST}/daily_log", headers=_HEADERS,
                     params={"date": f"eq.{target_date}", "select": "*"})
    rows = resp.json()
    if not rows:
        return {"date": target_date, "_empty": True}
    return {k: v for k, v in rows[0].items() if v is not None}


def get_daily_range(days=7):
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    resp = httpx.get(f"{_REST}/daily_log", headers=_HEADERS,
                     params={"date": f"gte.{start}", "select": "*", "order": "date.desc"})
    return [{k: v for k, v in r.items() if v is not None} for r in resp.json()]


def get_plan():
    today = date.today().isoformat()
    resp = httpx.get(f"{_REST}/training_plans", headers=_HEADERS,
                     params={"effective_from": f"lte.{today}",
                             "or": f"(effective_until.is.null,effective_until.gte.{today})",
                             "select": "*", "order": "effective_from.desc", "limit": "1"})
    rows = resp.json()
    return rows[0] if rows else {"_empty": True}


def get_scoring():
    today = date.today().isoformat()
    resp = httpx.get(f"{_REST}/scoring_config", headers=_HEADERS,
                     params={"effective_from": f"lte.{today}",
                             "or": f"(effective_until.is.null,effective_until.gte.{today})",
                             "select": "*", "order": "domain"})
    return resp.json()


def get_current_location():
    resp = httpx.get(f"{_REST}/locations", headers=_HEADERS,
                     params={"departure_date": "is.null", "select": "*",
                             "order": "arrival_date.desc", "limit": "1"})
    rows = resp.json()
    return rows[0] if rows else {"_empty": True}


def get_goals(status="active"):
    params = {"select": "*", "order": "domain,created_at"}
    if status != "all":
        params["status"] = f"eq.{status}"
    resp = httpx.get(f"{_REST}/goals", headers=_HEADERS, params=params)
    goals = resp.json()
    for g in goals:
        g["progress_pct"] = _calc_progress(g)
    return goals


def _calc_progress(g):
    target = g.get("target_value")
    current = g.get("current_value")
    start = g.get("start_value")
    if target is None or current is None:
        return None
    if start is not None and start != target:
        return round(min(abs(start - current) / abs(start - target) * 100, 100), 1)
    if target != 0:
        return round(min(current / target * 100, 100), 1)
    return None


def get_streaks():
    resp = httpx.get(f"{_REST}/streaks", headers=_HEADERS,
                     params={"select": "*", "order": "domain,metric"})
    return resp.json()


def get_changelog(limit=30):
    resp = httpx.get(f"{_REST}/change_log", headers=_HEADERS,
                     params={"select": "*", "order": "created_at.desc", "limit": str(limit)})
    return resp.json()


def get_protein_avg(days=7):
    rows = get_daily_range(days)
    values = [r["protein_total"] for r in rows if "protein_total" in r]
    if not values:
        return {"days": days, "avg_protein": None, "data_points": 0}
    return {"days": days, "avg_protein": round(sum(values) / len(values), 1),
            "min": min(values), "max": max(values), "data_points": len(values)}


def get_score_avg(days=7):
    rows = get_daily_range(days)
    result = {"days": days, "data_points": len(rows)}
    for d in ["training", "nutrition", "finance", "youtube", "personal"]:
        key = f"score_{d}"
        vals = [r[key] for r in rows if key in r]
        result[f"avg_{d}"] = round(sum(vals) / len(vals), 1) if vals else None
    totals = [r["score_total"] for r in rows if "score_total" in r]
    result["avg_total"] = round(sum(totals) / len(totals), 1) if totals else None
    return result


def get_injuries(status="active"):
    params = {"select": "*", "order": "first_reported.desc"}
    if status != "all":
        params["status"] = f"in.({status},monitoring)"
    resp = httpx.get(f"{_REST}/injuries", headers=_HEADERS, params=params)
    return resp.json()


# --- Write ---

def _upsert(table, data):
    headers = {**_HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
    resp = httpx.post(f"{_REST}/{table}", headers=headers, json=data)
    if resp.status_code >= 400:
        return {"error": resp.text}
    result = resp.json()
    return result[0] if isinstance(result, list) and result else result


def _insert(table, data):
    headers = {**_HEADERS, "Prefer": "return=representation"}
    resp = httpx.post(f"{_REST}/{table}", headers=headers, json=data)
    if resp.status_code >= 400:
        return {"error": resp.text}
    result = resp.json()
    return result[0] if isinstance(result, list) and result else result


def log_daily(data):
    if "date" not in data:
        data["date"] = date.today().isoformat()
    return _upsert("daily_log", data)


def log_meal(meal_data):
    target_date = meal_data.pop("date", None) or date.today().isoformat()
    current = get_daily(target_date)
    current_meals = current.get("meals", []) if not current.get("_empty") else []
    current_meals.append(meal_data)
    row = {
        "date": target_date,
        "meals": current_meals,
        "calories_total": sum(m.get("calories", 0) or 0 for m in current_meals),
        "protein_total": sum(m.get("protein", 0) or 0 for m in current_meals),
        "fat_total": sum(m.get("fat", 0) or 0 for m in current_meals),
        "carbs_total": sum(m.get("carbs", 0) or 0 for m in current_meals),
    }
    return _upsert("daily_log", row)


def log_expense(data):
    if "date" not in data:
        data["date"] = date.today().isoformat()
    return _insert("expenses", data)
