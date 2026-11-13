"""Participant-reported observations; callers own transaction boundaries."""

import math


_COLUMNS = ('id', 'bookingId', 'slotId', 'actorId', 'kind', 'outcome',
            'source', 'createdAt')
_ALLOWED = (
    ('preview', 'succeeded'),
    ('preview', 'denied'),
    ('preview', 'unavailable'),
    ('preview', 'failed'),
    ('room_open', 'iframe_requested'),
    ('room_open', 'external_link_clicked'),
)


def initialize(db):
    """Create observation storage without committing the caller's transaction."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS session_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bookingId TEXT NOT NULL,
            slotId TEXT NOT NULL,
            actorId TEXT NOT NULL,
            kind TEXT NOT NULL,
            outcome TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'participant_report'
                CHECK (source = 'participant_report'),
            createdAt REAL NOT NULL,
            CHECK (
                (kind = 'preview' AND outcome IN
                    ('succeeded', 'denied', 'unavailable', 'failed'))
                OR (kind = 'room_open' AND outcome IN
                    ('iframe_requested', 'external_link_clicked'))
            )
        )
    """)


def append_observation(db, *, booking_id, slot_id, actor_id, kind, outcome, now):
    """Append a report without modifying attendance or booking state."""
    if not isinstance(kind, str) or not isinstance(outcome, str) or (kind, outcome) not in _ALLOWED:
        raise ValueError('Invalid observation kind/outcome')
    try:
        if isinstance(now, bool) or not isinstance(now, (int, float)):
            raise ValueError('Observation time must be finite')
        created_at = float(now)
        if not math.isfinite(created_at):
            raise ValueError('Observation time must be finite')
    except (TypeError, OverflowError) as exc:
        raise ValueError('Observation time must be finite') from exc
    cursor = db.execute(
        '''INSERT INTO session_observations
           (bookingId, slotId, actorId, kind, outcome, source, createdAt)
           VALUES (?, ?, ?, ?, ?, 'participant_report', ?)''',
        (booking_id, slot_id, actor_id, kind, outcome, created_at),
    )
    row = db.execute(
        '''SELECT id, bookingId, slotId, actorId, kind, outcome, source, createdAt
           FROM session_observations WHERE id = ?''',
        (cursor.lastrowid,),
    ).fetchone()
    return dict(zip(_COLUMNS, row))


def list_observations(db, *, booking_id):
    """Return reports in insertion order, preserving their original slots."""
    rows = db.execute(
        '''SELECT id, bookingId, slotId, actorId, kind, outcome, source, createdAt
           FROM session_observations WHERE bookingId = ? ORDER BY id''',
        (booking_id,),
    )
    return [dict(zip(_COLUMNS, row)) for row in rows]
