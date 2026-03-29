"""Life Hub — web dashboard.

Flask app with htmx for interactivity. Talks to Supabase via db_client.
"""

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, render_template, request, jsonify

# Use local supabase_client (standalone, env-var based) for deploy
# Falls back to db_client from mcp-server for local dev
try:
    import supabase_client as db_client
except Exception:
    sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-server"))
    import db_client

app = Flask(__name__)


# ============================================================
# PAGES
# ============================================================


@app.route("/")
def dashboard():
    """Main dashboard — daily overview."""
    today = date.today().isoformat()
    daily = db_client.get_daily(today)
    plan = db_client.get_plan()
    streaks = db_client.get_streaks()
    location = db_client.get_current_location()
    goals = db_client.get_goals("active")
    score_avg = db_client.get_score_avg(7)
    protein_avg = db_client.get_protein_avg(7)

    return render_template(
        "dashboard.html",
        daily=daily,
        plan=plan,
        streaks=streaks,
        location=location,
        goals=goals,
        score_avg=score_avg,
        protein_avg=protein_avg,
        today=today,
    )


@app.route("/log")
def log_page():
    """Quick input page."""
    today = date.today().isoformat()
    daily = db_client.get_daily(today)
    scoring = db_client.get_scoring()
    return render_template("log.html", daily=daily, scoring=scoring, today=today)


@app.route("/history")
def history_page():
    """History page — last 14 days."""
    days = db_client.get_daily_range(14)
    return render_template("history.html", days=days)


@app.route("/goals")
def goals_page():
    """Goals page."""
    goals = db_client.get_goals("all")
    return render_template("goals.html", goals=goals)


@app.route("/changelog")
def changelog_page():
    """Changelog page."""
    changes = db_client.get_changelog(30)
    return render_template("changelog.html", changes=changes)


# ============================================================
# HTMX API ENDPOINTS
# ============================================================


@app.route("/api/log-meal", methods=["POST"])
def api_log_meal():
    """Log a meal via htmx form."""
    data = {
        "time": request.form.get("time", ""),
        "description": request.form.get("description", ""),
        "calories": int(request.form.get("calories", 0) or 0),
        "protein": int(request.form.get("protein", 0) or 0),
        "fat": int(request.form.get("fat", 0) or 0),
        "carbs": int(request.form.get("carbs", 0) or 0),
    }
    result = db_client.log_meal(data)
    meals = result.get("meals", [])
    cal = result.get("calories_total", 0)
    prot = result.get("protein_total", 0)
    return f"""
    <div class="p-3 bg-green-900/30 border border-green-700 rounded-lg text-green-300 text-sm">
        Zapisane: {data['description']} ({data['calories']} kcal, {data['protein']}g B).
        Dzienny total: {cal} kcal, {prot}g białka, {len(meals)} posiłków.
    </div>
    """


@app.route("/api/log-expense", methods=["POST"])
def api_log_expense():
    """Log an expense via htmx form."""
    data = {
        "amount": float(request.form.get("amount", 0)),
        "currency": request.form.get("currency", "THB"),
        "category": request.form.get("category", "inne"),
        "description": request.form.get("description", ""),
    }
    db_client.log_expense(data)
    return f"""
    <div class="p-3 bg-green-900/30 border border-green-700 rounded-lg text-green-300 text-sm">
        Zapisane: {data['description']} — {data['amount']} {data['currency']} ({data['category']})
    </div>
    """


@app.route("/api/log-wellbeing", methods=["POST"])
def api_log_wellbeing():
    """Log wellbeing scores via htmx form."""
    data = {"date": date.today().isoformat()}
    for field in ["energy", "mental", "body", "sleep_quality", "sleep_hours", "work_mood"]:
        val = request.form.get(field)
        if val:
            data[field] = float(val) if field == "sleep_hours" else int(val)
    work_notes = request.form.get("work_notes")
    if work_notes:
        data["work_notes"] = work_notes
    day_notes = request.form.get("day_notes")
    if day_notes:
        data["day_notes"] = day_notes

    db_client.log_daily(data)
    return """
    <div class="p-3 bg-green-900/30 border border-green-700 rounded-lg text-green-300 text-sm">
        Samopoczucie zapisane.
    </div>
    """


@app.route("/api/log-training", methods=["POST"])
def api_log_training():
    """Log training data via htmx form."""
    data = {"date": date.today().isoformat()}
    training_type = request.form.get("training_type")
    if training_type:
        data["training_type"] = training_type
    data["training_completed"] = request.form.get("training_completed") == "on"
    data["stretching_done"] = request.form.get("stretching_done") == "on"
    data["balance_exercises"] = request.form.get("balance_exercises") == "on"
    notes = request.form.get("training_notes")
    if notes:
        data["training_notes"] = notes

    db_client.log_daily(data)
    return """
    <div class="p-3 bg-green-900/30 border border-green-700 rounded-lg text-green-300 text-sm">
        Trening zapisany.
    </div>
    """


@app.route("/api/daily-summary")
def api_daily_summary():
    """Get today's summary for htmx refresh."""
    daily = db_client.get_daily(date.today().isoformat())
    if daily.get("_empty"):
        return '<div class="text-zinc-500 text-sm">Brak danych na dziś.</div>'

    cal = daily.get("calories_total", 0) or 0
    prot = daily.get("protein_total", 0) or 0
    meals_count = len(daily.get("meals", []))
    energy = daily.get("energy", "—")
    score = daily.get("score_total", "—")

    return f"""
    <div class="grid grid-cols-2 gap-2 text-sm">
        <div class="bg-zinc-800 rounded p-2"><span class="text-zinc-400">Kalorie</span><br><span class="text-xl font-bold text-white">{cal}</span></div>
        <div class="bg-zinc-800 rounded p-2"><span class="text-zinc-400">Białko</span><br><span class="text-xl font-bold text-white">{prot}g</span></div>
        <div class="bg-zinc-800 rounded p-2"><span class="text-zinc-400">Posiłki</span><br><span class="text-xl font-bold text-white">{meals_count}</span></div>
        <div class="bg-zinc-800 rounded p-2"><span class="text-zinc-400">Energia</span><br><span class="text-xl font-bold text-white">{energy}/10</span></div>
    </div>
    """


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run(debug=True, port=5050)
