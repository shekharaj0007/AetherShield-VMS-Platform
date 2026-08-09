"""Natural language event search + rule-based AI summary/chat (LLM optional)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models import Event, Camera


CLASS_ALIASES = {
    "person": ["person", "people", "human", "man", "woman", "intruder"],
    "car": ["car", "vehicle", "automobile", "sedan"],
    "truck": ["truck", "lorry"],
    "bus": ["bus"],
    "motorcycle": ["motorcycle", "bike", "motorbike"],
    "bicycle": ["bicycle", "cycle"],
    "dog": ["dog", "canine"],
    "fire": ["fire", "flame"],
    "smoke": ["smoke"],
    "intrusion": ["intrusion", "breach", "unauthorized"],
    "motion": ["motion", "movement"],
    "backpack": ["backpack", "bag"],
    "face": ["face", "faces", "known", "unknown", "blacklist", "employee"],
    "plate": ["plate", "license", "number plate", "vehicle number", "dl "],
}

COLOR_WORDS = ["red", "blue", "white", "black", "green", "yellow", "silver", "gray", "grey"]


def parse_nl_query(query: str) -> dict:
    """Parse natural language into structured filters."""
    q = query.lower().strip()
    filters: dict = {"event_types": [], "priorities": [], "text": q}

    now = datetime.now(timezone.utc)
    start = None
    end = now

    if "yesterday" in q:
        start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif "today" in q:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif "last hour" in q or "past hour" in q:
        start = now - timedelta(hours=1)
    elif "last 24" in q or "past 24" in q or "last day" in q:
        start = now - timedelta(hours=24)
    elif "this week" in q or "past week" in q:
        start = now - timedelta(days=7)
    elif "last week" in q:
        start = now - timedelta(days=14)
        end = now - timedelta(days=7)

    # time of day: after 9 PM, before 6 AM, etc.
    after_m = re.search(r"after\s+(\d{1,2})\s*(am|pm|:00)?", q)
    before_m = re.search(r"before\s+(\d{1,2})\s*(am|pm|:00)?", q)
    hour_filter = None
    if after_m:
        hour = int(after_m.group(1))
        ampm = (after_m.group(2) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        hour_filter = ("after", hour)
    if before_m:
        hour = int(before_m.group(1))
        ampm = (before_m.group(2) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        hour_filter = ("before", hour)

    for canonical, aliases in CLASS_ALIASES.items():
        if any(a in q for a in aliases):
            filters["event_types"].append(canonical)

    if "critical" in q:
        filters["priorities"].append("critical")
    if "high" in q and "high" not in filters["priorities"]:
        filters["priorities"].append("high")

    colors = [c for c in COLOR_WORDS if c in q]
    filters["colors"] = colors
    filters["start"] = start
    filters["end"] = end
    filters["hour_filter"] = hour_filter

    cam_m = re.search(r"camera\s*(\d+)", q)
    if cam_m:
        filters["camera_id"] = int(cam_m.group(1))

    return filters


def search_events(
    db: Session,
    query: str,
    camera_id: Optional[int] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 50,
) -> list[Event]:
    parsed = parse_nl_query(query)
    q = db.query(Event)

    cid = camera_id or parsed.get("camera_id")
    if cid:
        q = q.filter(Event.camera_id == cid)

    s = start or parsed.get("start")
    e = end or parsed.get("end")
    if s:
        q = q.filter(Event.timestamp >= s)
    if e:
        q = q.filter(Event.timestamp <= e)

    if parsed["event_types"]:
        types = parsed["event_types"]
        # also match intrusion metadata object
        clauses = [Event.event_type.in_(types)]
        for t in types:
            clauses.append(Event.label.ilike(f"%{t}%"))
        q = q.filter(or_(*clauses))

    if parsed["priorities"]:
        q = q.filter(Event.priority.in_(parsed["priorities"]))

    if parsed.get("colors"):
        # soft filter on metadata/label text
        color_clauses = [Event.label.ilike(f"%{c}%") for c in parsed["colors"]]
        color_clauses += [Event.metadata_json.isnot(None)]  # keep broad if no color in label
        # Prefer events mentioning color; if none, return unfiltered by color later
        colored = q.filter(or_(*[Event.label.ilike(f"%{c}%") for c in parsed["colors"]])).limit(limit).all()
        if colored:
            return _apply_hour_filter(colored, parsed.get("hour_filter"))

    results = q.order_by(Event.timestamp.desc()).limit(limit * 2).all()
    results = _apply_hour_filter(results, parsed.get("hour_filter"))
    return results[:limit]


def _apply_hour_filter(events: list[Event], hour_filter) -> list[Event]:
    if not hour_filter:
        return events
    kind, hour = hour_filter
    out = []
    for ev in events:
        h = ev.timestamp.hour if ev.timestamp.tzinfo else ev.timestamp.replace(tzinfo=timezone.utc).hour
        if kind == "after" and h >= hour:
            out.append(ev)
        elif kind == "before" and h < hour:
            out.append(ev)
    return out


def build_summary(db: Session, hours: int = 24) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    events = db.query(Event).filter(Event.timestamp >= since).all()
    by_type: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_camera: dict[int, int] = {}
    for e in events:
        by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
        by_priority[e.priority] = by_priority.get(e.priority, 0) + 1
        by_camera[e.camera_id] = by_camera.get(e.camera_id, 0) + 1

    most_active_cam = max(by_camera, key=by_camera.get) if by_camera else None
    cam_name = None
    if most_active_cam:
        c = db.query(Camera).filter(Camera.id == most_active_cam).first()
        cam_name = c.name if c else f"Camera {most_active_cam}"

    # Peak hour
    hour_counts: dict[int, int] = {}
    for e in events:
        hour_counts[e.timestamp.hour] = hour_counts.get(e.timestamp.hour, 0) + 1
    peak_hour = max(hour_counts, key=hour_counts.get) if hour_counts else None

    highlights = []
    if by_type.get("intrusion", 0):
        highlights.append(f"{by_type['intrusion']} intrusion alert(s)")
    if by_type.get("person", 0):
        highlights.append(f"{by_type['person']} person detection(s)")
    if by_type.get("car", 0) + by_type.get("truck", 0) + by_type.get("bus", 0):
        vehicles = by_type.get("car", 0) + by_type.get("truck", 0) + by_type.get("bus", 0)
        highlights.append(f"{vehicles} vehicle detection(s)")
    if by_priority.get("critical", 0):
        highlights.append(f"{by_priority['critical']} critical event(s)")
    if not highlights:
        highlights.append("No significant security events")

    lines = [
        f"Summary for the last {hours} hours:",
        f"- Total events: {len(events)}",
        f"- Persons: {by_type.get('person', 0)}",
        f"- Vehicles: {by_type.get('car', 0) + by_type.get('truck', 0) + by_type.get('bus', 0)}",
        f"- Intrusions: {by_type.get('intrusion', 0)}",
        f"- Fire/Smoke: {by_type.get('fire', 0) + by_type.get('smoke', 0)}",
        f"- Most active camera: {cam_name or 'N/A'}",
        f"- Peak activity hour: {f'{peak_hour}:00' if peak_hour is not None else 'N/A'}",
    ]

    return {
        "period": f"last_{hours}h",
        "summary_text": "\n".join(lines),
        "stats": {
            "total": len(events),
            "by_type": by_type,
            "by_priority": by_priority,
            "most_active_camera": cam_name,
            "peak_hour": peak_hour,
            "avg_per_hour": round(len(events) / max(hours, 1), 1),
        },
        "highlights": highlights,
    }


def chat_with_events(db: Session, message: str, camera_id: Optional[int] = None) -> dict:
    """RAG-lite over event metadata — no LLM required."""
    msg = message.lower().strip()

    if any(w in msg for w in ["summarize", "summary", "what happened", "overview"]):
        summary = build_summary(db, 24)
        return {
            "reply": summary["summary_text"],
            "events": [],
            "sources": ["events_last_24h"],
        }

    events = search_events(db, message, camera_id=camera_id, limit=20)
    if not events:
        return {
            "reply": "I couldn't find matching events. Try queries like \"show people after 9 PM\" or \"intrusions today\".",
            "events": [],
            "sources": [],
        }

    lines = [f"Found {len(events)} matching event(s):"]
    for e in events[:10]:
        cam = db.query(Camera).filter(Camera.id == e.camera_id).first()
        cam_name = cam.name if cam else f"Camera {e.camera_id}"
        ts = e.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"• {ts} — {e.label} on {cam_name} ({e.confidence:.0%} conf, {e.priority})")

    return {
        "reply": "\n".join(lines),
        "events": events,
        "sources": [f"event:{e.id}" for e in events[:10]],
    }
