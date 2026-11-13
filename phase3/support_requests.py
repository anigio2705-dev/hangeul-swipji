"""Private support requests using a caller-owned SQLite transaction."""

import math
import secrets


def initialize(db):
    """Create only support storage; never commit the caller's transaction."""
    db.execute("""
        CREATE TABLE IF NOT EXISTS support_requests (
            id TEXT PRIMARY KEY,
            author_id TEXT NOT NULL REFERENCES users(id),
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'open' CHECK (status = 'open')
        )
    """)


def _text(value, minimum, maximum, name):
    if not isinstance(value, str):
        raise ValueError(name + ' must be a string')
    value = value.strip()
    if not minimum <= len(value) <= maximum:
        raise ValueError(name + ' has an invalid length')
    return value


def submit(db, actor_id, *, subject, body, now):
    """Store a request; authentication and auditing belong to the caller."""
    subject = _text(subject, 2, 100, 'subject')
    body = _text(body, 10, 5000, 'body')
    if not isinstance(actor_id, str) or not actor_id:
        raise ValueError('Invalid author')
    if db.execute('SELECT 1 FROM users WHERE id = ?', (actor_id,)).fetchone() is None:
        raise ValueError('Unknown author')
    if isinstance(now, bool) or not isinstance(now, (int, float)):
        raise ValueError('Invalid timestamp')
    try:
        created_at = float(now)
    except (OverflowError, ValueError):
        raise ValueError('Invalid timestamp') from None
    if not math.isfinite(created_at):
        raise ValueError('Invalid timestamp')
    request_id = secrets.token_hex(16)
    db.execute(
        "INSERT INTO support_requests "
        "(id, author_id, subject, body, created_at, status) "
        "VALUES (?, ?, ?, ?, ?, 'open')",
        (request_id, actor_id, subject, body, created_at),
    )
    return {'requestId': request_id}


def _request(row, *, include_author=False):
    result = dict(zip(('id', 'subject', 'body', 'createdAt', 'status'), row[:5]))
    if include_author:
        result['authorId'] = row[5]
    return result


def list_requests(db, actor_id):
    """Return only the authenticated caller's requests."""
    rows = db.execute(
        'SELECT id, subject, body, created_at, status FROM support_requests '
        'WHERE author_id = ? ORDER BY created_at DESC, id DESC',
        (actor_id,),
    )
    return [_request(row) for row in rows]


def list_admin_requests(db, *, limit=20, offset=0):
    """Return a page for a caller whose administrator role was verified."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('limit must be an integer from 1 to 100')
    if type(offset) is not int or offset < 0:
        raise ValueError('offset must be a nonnegative integer')
    if offset > 9223372036854775807:
        return {'requests': [], 'limit': limit, 'offset': offset, 'hasMore': False}
    rows = list(db.execute(
        'SELECT id, subject, body, created_at, status, author_id '
        'FROM support_requests ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?',
        (limit + 1, offset),
    ))
    return {
        'requests': [_request(row, include_author=True) for row in rows[:limit]],
        'limit': limit,
        'offset': offset,
        'hasMore': len(rows) > limit,
    }
