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
# DETAIL ENDPOINTS (htmx drill-down)
# ============================================================


@app.route("/api/detail/scores")
def detail_scores():
    """Breakdown of today's scores per domain."""
    daily = db_client.get_daily(date.today().isoformat())
    scoring = db_client.get_scoring()

    rows = ""
    domains = [
        ("TRAINING", "score_training", daily.get("score_training")),
        ("NUTRITION", "score_nutrition", daily.get("score_nutrition")),
        ("FINANCE", "score_finance", daily.get("score_finance")),
        ("YOUTUBE", "score_youtube", daily.get("score_youtube")),
        ("PERSONAL", "score_personal", daily.get("score_personal")),
    ]
    for name, key, val in domains:
        rules_html = ""
        for sc in scoring:
            if sc.get("domain") == name.lower():
                for rule in sc.get("rules", []):
                    desc = rule.get("how_to_score", rule.get("description", ""))
                    rules_html += f'<div class="text-[10px] text-muted mt-1">— {desc}</div>'
        score_display = f"{val:.1f}" if val is not None else "—"
        color = "text-accent" if val else "text-muted"
        rows += f"""
        <div class="flex justify-between items-start py-2 border-b border-brd">
            <div>
                <span class="text-xs font-bold tracking-wider">{name}</span>
                {rules_html}
            </div>
            <span class="text-lg font-black {color}">{score_display}</span>
        </div>"""

    total = daily.get("score_total")
    total_display = f"{total:.1f}" if total is not None else "—"
    return f"""
    <div class="border-t-2 border-brand pt-3">
        {rows}
        <div class="flex justify-between items-center pt-3 mt-1">
            <span class="text-xs font-black tracking-wider text-accent">TOTAL</span>
            <span class="text-2xl font-black text-accent">{total_display}</span>
        </div>
    </div>"""


@app.route("/api/detail/nutrition")
def detail_nutrition():
    """Full meal list with macros."""
    daily = db_client.get_daily(date.today().isoformat())
    meals = daily.get("meals", [])

    if not meals:
        return '<div class="border-t-2 border-brand pt-3 text-muted text-sm">Brak posilkow.</div>'

    rows = ""
    for m in meals:
        cal = m.get("calories", 0)
        prot = m.get("protein", 0)
        fat = m.get("fat", 0)
        carbs = m.get("carbs", 0)
        time = f'<span class="text-muted font-mono">{m["time"]}</span> ' if m.get("time") else ""
        rows += f"""
        <div class="py-2 border-b border-brd">
            <div class="flex justify-between">
                <span class="text-sm">{time}{m.get('description', '')}</span>
                <span class="text-sm font-bold text-accent">{cal}</span>
            </div>
            <div class="flex gap-3 text-[10px] text-muted mt-1">
                <span>B:{prot}g</span><span>T:{fat}g</span><span>W:{carbs}g</span>
            </div>
        </div>"""

    cal_total = daily.get("calories_total", 0) or 0
    prot_total = daily.get("protein_total", 0) or 0
    fat_total = daily.get("fat_total", 0) or 0
    carbs_total = daily.get("carbs_total", 0) or 0

    return f"""
    <div class="border-t-2 border-brand pt-3">
        {rows}
        <div class="flex justify-between items-center pt-3 mt-1 border-t-2 border-brd">
            <span class="text-xs font-black tracking-wider">TOTAL</span>
            <div class="flex gap-3 text-xs font-bold">
                <span class="text-accent">{cal_total} kcal</span>
                <span>B:{prot_total}g</span>
                <span>T:{fat_total}g</span>
                <span>W:{carbs_total}g</span>
            </div>
        </div>
    </div>"""


@app.route("/api/detail/training")
def detail_training():
    """Full training details."""
    daily = db_client.get_daily(date.today().isoformat())
    plan = db_client.get_plan()
    injuries = db_client.get_injuries("active")

    parts = ['<div class="border-t-2 border-brand pt-3">']

    if daily.get("training_notes"):
        parts.append(f'<div class="text-sm mb-3">{daily["training_notes"]}</div>')

    if plan and not plan.get("_empty"):
        schedule = plan.get("schedule", [])
        parts.append('<div class="text-[10px] font-bold text-muted tracking-wider mb-2">PLAN TYGODNIA</div>')
        for day in schedule:
            dow = day.get("day_of_week", "")[:3].upper()
            tt = day.get("training_type", "").upper()
            det = day.get("details", "")
            parts.append(f'<div class="flex gap-2 text-xs py-1 border-b border-brd"><span class="font-bold w-8 text-muted">{dow}</span><span class="font-bold text-accent w-16">{tt}</span><span class="text-mid">{det[:50]}</span></div>')

    if injuries:
        parts.append('<div class="text-[10px] font-bold text-muted tracking-wider mt-3 mb-2">KONTUZJE AKTYWNE</div>')
        for inj in injuries:
            loc = inj.get("location", "").replace("_", " ").upper()
            status = inj.get("status", "").upper()
            parts.append(f'<div class="flex justify-between text-xs py-1 border-b border-brd"><span class="font-bold">{loc}</span><span class="text-brand-light">{status}</span></div>')

    parts.append('</div>')
    return "\n".join(parts)


@app.route("/api/detail/wellbeing")
def detail_wellbeing():
    """7-day wellbeing history."""
    days = db_client.get_daily_range(7)

    header = '<div class="border-t-2 border-brand pt-3">'
    header += '<div class="grid grid-cols-5 gap-1 text-[10px] font-bold text-muted tracking-wider mb-2"><span>DATA</span><span>ENRG</span><span>HEAD</span><span>BODY</span><span>SLEEP</span></div>'

    rows = ""
    for d in days:
        dt = d.get("date", "")[-5:]
        e = d.get("energy", "—")
        m = d.get("mental", "—")
        b = d.get("body", "—")
        s = d.get("sleep_quality", "—")
        rows += f'<div class="grid grid-cols-5 gap-1 text-xs py-1 border-b border-brd font-mono"><span class="text-muted">{dt}</span><span>{e}</span><span>{m}</span><span>{b}</span><span>{s}</span></div>'

    return f"{header}{rows}</div>"


@app.route("/api/detail/streaks")
def detail_streaks():
    """Streak details."""
    streaks = db_client.get_streaks()
    if not streaks:
        return '<div class="border-t-2 border-brand pt-3 text-muted text-sm">Brak streakow.</div>'

    rows = ""
    for s in streaks:
        metric = s.get("metric", "").replace("_", " ").upper()
        current = s.get("current_streak", 0)
        longest = s.get("longest_streak", 0)
        last = s.get("last_completed", "—")
        bar_pct = min(current / max(longest, 1) * 100, 100) if longest else 0
        rows += f"""
        <div class="py-2 border-b border-brd">
            <div class="flex justify-between text-xs">
                <span class="font-bold tracking-wider">{metric}</span>
                <span class="text-muted">BEST {longest}</span>
            </div>
            <div class="flex items-center gap-2 mt-1">
                <span class="text-lg font-black {'text-accent' if current >= 5 else ''}">{current}</span>
                <div class="bar flex-1"><div class="bar-fill bg-accent" style="width:{bar_pct}%"></div></div>
            </div>
            <div class="text-[10px] text-muted mt-0.5">LAST: {last}</div>
        </div>"""

    return f'<div class="border-t-2 border-brand pt-3">{rows}</div>'


@app.route("/api/detail/averages")
def detail_averages():
    """7-day daily breakdown."""
    days = db_client.get_daily_range(7)

    header = '<div class="border-t-2 border-brand pt-3">'
    header += '<div class="grid grid-cols-4 gap-1 text-[10px] font-bold text-muted tracking-wider mb-2"><span>DATA</span><span>KCAL</span><span>BIAL</span><span>SCORE</span></div>'

    rows = ""
    for d in days:
        dt = d.get("date", "")[-5:]
        cal = d.get("calories_total", "—")
        prot = d.get("protein_total", "—")
        score = f"{d['score_total']:.1f}" if d.get("score_total") else "—"
        rows += f'<div class="grid grid-cols-4 gap-1 text-xs py-1 border-b border-brd font-mono"><span class="text-muted">{dt}</span><span>{cal}</span><span>{prot}</span><span class="text-accent font-bold">{score}</span></div>'

    return f"{header}{rows}</div>"


@app.route("/api/detail/day/<day_date>")
def detail_day(day_date):
    """Full day details for history view."""
    d = db_client.get_daily(day_date)
    if d.get("_empty"):
        return '<div class="text-muted text-sm p-2">Brak danych.</div>'

    parts = ['<div class="border-t-2 border-brand pt-3 mt-2">']

    # Training
    if d.get("training_type"):
        tt = d["training_type"].upper()
        done = "+" if d.get("training_completed") else "-"
        parts.append(f'<div class="text-xs font-bold mb-2"><span class="text-accent">{done}</span> {tt}</div>')
        if d.get("training_notes"):
            parts.append(f'<div class="text-xs text-mid mb-2">{d["training_notes"][:200]}</div>')

    # Meals
    meals = d.get("meals", [])
    if meals:
        parts.append('<div class="text-[10px] font-bold text-muted tracking-wider mb-1">POSILKI</div>')
        for m in meals:
            parts.append(f'<div class="flex justify-between text-xs py-0.5"><span class="text-mid">{m.get("description","")[:40]}</span><span class="text-accent">{m.get("calories","")} kcal / {m.get("protein","")}g B</span></div>')

    # Wellbeing
    if d.get("energy"):
        parts.append(f'<div class="text-[10px] font-bold text-muted tracking-wider mt-2 mb-1">SAMOPOCZUCIE</div>')
        parts.append(f'<div class="text-xs">E:{d.get("energy","—")} G:{d.get("mental","—")} C:{d.get("body","—")} S:{d.get("sleep_quality","—")}</div>')

    # Notes
    if d.get("day_notes"):
        parts.append(f'<div class="text-[10px] font-bold text-muted tracking-wider mt-2 mb-1">NOTATKI</div>')
        parts.append(f'<div class="text-xs text-mid">{d["day_notes"][:300]}</div>')

    parts.append('</div>')
    return "\n".join(parts)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    app.run(debug=True, port=5050)
