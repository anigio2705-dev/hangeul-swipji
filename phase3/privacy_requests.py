"""Local request intake only; callers supply the authenticated user ID.

Receipt does not complete withdrawal or erasure. Legal retention grounds,
scopes and periods, and external Supabase account handling remain pending
separate review. This module never changes accounts, sessions or records
outside its dedicated request table. Transaction ownership stays with callers.
"""

import secrets


def initialize(db):
    """Prepare only the dedicated request table, without committing."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS privacy_requests (
            request_id TEXT PRIMARY KEY NOT NULL,
            user_id TEXT NOT NULL,
            kind TEXT NOT NULL CHECK (kind IN ('withdrawal', 'erasure')),
            status TEXT NOT NULL DEFAULT 'received',
            retention_status TEXT NOT NULL DEFAULT 'pending_review',
            created_at REAL NOT NULL,
            UNIQUE (user_id, kind, status)
        )
    """)


def _public(row):
    return {
        'requestId': row[0],
        'kind': row[1],
        'status': row[2],
        'retentionStatus': row[3],
        'createdAt': row[4],
    }


def submit(db, user_id, *, kind, now):
    """Receive a request, preserving the ID and timestamp of repeat intake."""
    if not isinstance(kind, str) or kind not in ('withdrawal', 'erasure'):
        raise ValueError('kind must be withdrawal or erasure')
    cursor = db.execute("""
        INSERT INTO privacy_requests
            (request_id, user_id, kind, status, retention_status, created_at)
        VALUES (?, ?, ?, 'received', 'pending_review', ?)
        ON CONFLICT (user_id, kind, status) DO NOTHING
    """, (secrets.token_hex(16), user_id, kind, now))
    duplicate = cursor.rowcount == 0
    row = db.execute("""
        SELECT request_id, kind, status, retention_status, created_at
        FROM privacy_requests
        WHERE user_id = ? AND kind = ? AND status = 'received'
    """, (user_id, kind)).fetchone()
    result = _public(row)
    result['duplicate'] = duplicate
    return result


def list_requests(db, user_id):
    """Return only the authenticated user's request metadata."""
    rows = db.execute("""
        SELECT request_id, kind, status, retention_status, created_at
        FROM privacy_requests
        WHERE user_id = ?
        ORDER BY created_at ASC, request_id ASC
    """, (user_id,))
    return [_public(row) for row in rows]
