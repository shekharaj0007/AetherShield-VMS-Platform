"""Shifts and watchlist. Camera heartbeats live on the cameras router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models import Shift, ShiftNote, Site, User, WatchlistEntry, WatchlistHit, Event
from app.schemas import (
    OperatorOption,
    ShiftCreate,
    ShiftNoteCreate,
    ShiftNoteOut,
    ShiftOut,
    WatchlistCreate,
    WatchlistHitOut,
    WatchlistOut,
)
from app.services.floor import add_shift_note, evaluate_all_watchlist
from app.services.operations import as_utc, write_audit

router = APIRouter(tags=["floor"])


def _note_out(note: ShiftNote) -> ShiftNoteOut:
    author = note.author
    return ShiftNoteOut(
        id=note.id,
        author_id=note.author_id,
        author_name=author.full_name if author else None,
        body=note.body,
        created_at=note.created_at,
    )


def _shift_out(shift: Shift, now: datetime | None = None) -> ShiftOut:
    now = now or datetime.now(timezone.utc)
    site = shift.site
    operator = shift.operator
    notes = sorted(shift.notes, key=lambda n: n.created_at)
    return ShiftOut(
        id=shift.id,
        site_id=shift.site_id,
        site_name=site.name if site else None,
        operator_id=shift.operator_id,
        operator_name=operator.full_name if operator else None,
        operator_email=operator.email if operator else None,
        starts_at=shift.starts_at,
        ends_at=shift.ends_at,
        current=as_utc(shift.starts_at) <= as_utc(now) <= as_utc(shift.ends_at),
        notes=[_note_out(n) for n in notes],
    )


@router.get("/api/shifts/operators", response_model=list[OperatorOption])
def list_shift_operators(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("shifts:write")),
):
    rows = db.query(User).filter(User.role == "operator", User.is_active == True).order_by(User.id).all()  # noqa: E712
    return [OperatorOption(id=u.id, full_name=u.full_name, email=u.email) for u in rows]


@router.get("/api/shifts", response_model=list[ShiftOut])
def list_shifts(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("shifts:read")),
):
    rows = db.query(Shift).order_by(Shift.starts_at.desc()).all()
    return [_shift_out(row) for row in rows]


@router.post("/api/shifts", response_model=ShiftOut)
def create_shift(
    body: ShiftCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("shifts:write")),
):
    start = as_utc(body.starts_at)
    end = as_utc(body.ends_at)
    if end <= start:
        raise HTTPException(400, "ends_at must be after starts_at")
    site = db.query(Site).filter(Site.id == body.site_id).first()
    if not site:
        raise HTTPException(404, "Site not found")
    operator = db.query(User).filter(User.id == body.operator_id).first()
    if not operator or operator.role != "operator":
        raise HTTPException(400, "operator_id must be an operator user")
    shift = Shift(site_id=site.id, operator_id=operator.id, starts_at=start, ends_at=end)
    db.add(shift)
    db.flush()
    write_audit(
        db,
        user,
        "shift.create",
        f"shift:{shift.id}",
        f"{site.code} {operator.email} {start.isoformat()} → {end.isoformat()}",
    )
    db.commit()
    db.refresh(shift)
    return _shift_out(shift)


@router.post("/api/shifts/{shift_id}/notes", response_model=ShiftOut)
def create_shift_note(
    shift_id: int,
    body: ShiftNoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("shifts:note")),
):
    text = (body.body or "").strip()
    if not text:
        raise HTTPException(400, "Note is required")
    shift = db.query(Shift).filter(Shift.id == shift_id).first()
    if not shift:
        raise HTTPException(404, "Shift not found")
    add_shift_note(db, shift, user, text)
    db.commit()
    db.refresh(shift)
    return _shift_out(shift)


def _watch_out(row: WatchlistEntry, db: Session) -> WatchlistOut:
    count = db.query(WatchlistHit).filter(WatchlistHit.entry_id == row.id).count()
    data = WatchlistOut.model_validate(row)
    data.match_count = count
    data.note = row.note or ""
    return data


@router.get("/api/watchlist", response_model=list[WatchlistOut])
def list_watchlist(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("watchlist:read")),
):
    rows = db.query(WatchlistEntry).order_by(WatchlistEntry.id).all()
    return [_watch_out(row, db) for row in rows]


@router.post("/api/watchlist", response_model=WatchlistOut)
def create_watchlist(
    body: WatchlistCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("watchlist:write")),
):
    kind = (body.kind or "").strip().lower()
    if kind not in ("plate", "person"):
        raise HTTPException(400, "kind must be plate or person")
    value = (body.value or "").strip()
    if not value:
        raise HTTPException(400, "value is required")
    note = ""
    if kind == "person":
        note = "Matches metadata.object 'person' and an equal event label."
    else:
        note = "Matches metadata.plate. Seeded demo events do not store a plate."
    row = WatchlistEntry(kind=kind, value=value, enabled=True, note=note)
    db.add(row)
    db.flush()
    write_audit(db, user, "watchlist.create", f"watchlist:{row.id}", f"{kind}:{value}")
    evaluate_all_watchlist(db)
    db.commit()
    db.refresh(row)
    return _watch_out(row, db)


@router.get("/api/watchlist/hits", response_model=list[WatchlistHitOut])
def list_watchlist_hits(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("watchlist:read")),
):
    rows = db.query(WatchlistHit).order_by(WatchlistHit.created_at.desc()).limit(50).all()
    out: list[WatchlistHitOut] = []
    for hit in rows:
        entry = db.query(WatchlistEntry).filter(WatchlistEntry.id == hit.entry_id).first()
        event = db.query(Event).filter(Event.id == hit.event_id).first()
        out.append(
            WatchlistHitOut(
                id=hit.id,
                entry_id=hit.entry_id,
                event_id=hit.event_id,
                alert_id=hit.alert_id,
                kind=entry.kind if entry else "",
                value=entry.value if entry else "",
                event_label=event.label if event else "",
                created_at=hit.created_at,
            )
        )
    return out
