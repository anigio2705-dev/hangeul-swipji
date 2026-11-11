"""Schedule operations within the caller's SQLite transaction."""
import math


class ScheduleError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def initialize(db) -> None:
    db.execute('''CREATE TABLE IF NOT EXISTS time_off (
        id TEXT PRIMARY KEY,
        teacher_id TEXT NOT NULL,
        start REAL NOT NULL,
        end REAL NOT NULL,
        CHECK (end > start)
    )''')
    db.execute('''CREATE INDEX IF NOT EXISTS time_off_teacher_range
                  ON time_off(teacher_id, start, end)''')


def _seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScheduleError('유한한 UTC 초가 필요합니다')
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise ScheduleError('유한한 UTC 초가 필요합니다') from None
    if not math.isfinite(value):
        raise ScheduleError('유한한 UTC 초가 필요합니다')
    return value


def _range(start, end):
    start, end = _seconds(start), _seconds(end)
    if end <= start:
        raise ScheduleError('종료 시간은 시작 시간 이후여야 합니다')
    return start, end


def _teacher(db, teacher_id):
    row = db.execute('SELECT role FROM users WHERE id=?', (teacher_id,)).fetchone()
    if row is None or row[0] not in ('teacher', 'partner'):
        raise ScheduleError('강사 또는 회화 파트너 권한이 필요합니다', 403)


def _audit(db, teacher_id, action, entity, now):
    db.execute('''INSERT INTO audit(actor,action,entity,detail,created_at)
                  VALUES(?,?,?,?,?)''', (teacher_id, action, entity, '', now))


def assert_available(db, teacher_id: str, start: float, end: float) -> None:
    start, end = _range(start, end)
    if db.execute('''SELECT 1 FROM time_off
                     WHERE teacher_id=? AND start<? AND end>? LIMIT 1''',
                  (teacher_id, end, start)).fetchone():
        raise ScheduleError('휴무 시간과 겹칩니다', 409)


def update_slot(db, teacher_id: str, slot_id: str, start: float,
                end: float, now: float) -> dict:
    row = db.execute('SELECT teacher_id FROM slots WHERE id=?',
                     (slot_id,)).fetchone()
    if row is None:
        raise ScheduleError('일정이 없습니다', 404)
    if row[0] != teacher_id:
        raise ScheduleError('본인 일정만 수정할 수 있습니다', 403)
    _teacher(db, teacher_id)
    start, end = _range(start, end)
    now = _seconds(now)
    if start <= now or not 300 <= end - start <= 7200:
        raise ScheduleError('미래의 5~120분 일정을 입력하세요')
    if db.execute('''SELECT 1 FROM bookings WHERE slot_id=?
                     AND status NOT IN ('cancelled','refunded','expired')
                     LIMIT 1''', (slot_id,)).fetchone():
        raise ScheduleError('예약이 있는 일정은 수정할 수 없습니다', 409)
    if db.execute('''SELECT 1 FROM slots WHERE teacher_id=? AND id<>?
                     AND start<? AND end>? LIMIT 1''',
                  (teacher_id, slot_id, end, start)).fetchone():
        raise ScheduleError('기존 일정과 겹칩니다', 409)
    assert_available(db, teacher_id, start, end)
    db.execute('UPDATE slots SET start=?, end=? WHERE id=?',
               (start, end, slot_id))
    _audit(db, teacher_id, 'availability.update', slot_id, now)
    return {'id': slot_id, 'teacher_id': teacher_id, 'start': start, 'end': end}


def add_time_off(db, teacher_id: str, start: float, end: float,
                 now: float) -> dict:
    _teacher(db, teacher_id)
    start, end = _range(start, end)
    now = _seconds(now)
    if start <= now:
        raise ScheduleError('미래의 휴무 시간을 입력하세요')
    assert_available(db, teacher_id, start, end)
    if db.execute('''SELECT 1 FROM bookings b JOIN slots s ON s.id=b.slot_id
                     WHERE b.teacher_id=?
                     AND b.status NOT IN ('cancelled','refunded','expired')
                     AND s.start<? AND s.end>? LIMIT 1''',
                  (teacher_id, end, start)).fetchone():
        raise ScheduleError('기존 예약과 휴무가 겹칩니다', 409)
    time_off_id = db.execute('SELECT lower(hex(randomblob(16)))').fetchone()[0]
    db.execute('INSERT INTO time_off(id,teacher_id,start,end) VALUES(?,?,?,?)',
               (time_off_id, teacher_id, start, end))
    _audit(db, teacher_id, 'availability.time_off', time_off_id, now)
    return {'id': time_off_id, 'teacher_id': teacher_id, 'start': start, 'end': end}


def list_time_off(db, teacher_id: str, now: float) -> list[dict]:
    _teacher(db, teacher_id)
    now = _seconds(now)
    rows = db.execute('''SELECT id,teacher_id,start,end FROM time_off
                         WHERE teacher_id=? AND end>?
                         ORDER BY start,end,id''', (teacher_id, now))
    return [dict(zip(('id', 'teacher_id', 'start', 'end'), row)) for row in rows]
