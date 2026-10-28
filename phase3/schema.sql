PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password TEXT NOT NULL,nickname TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('learner','partner','teacher','admin')),approved INTEGER NOT NULL DEFAULT 0,languages TEXT NOT NULL DEFAULT '한국어',timezone TEXT NOT NULL DEFAULT 'Asia/Seoul',specialty TEXT NOT NULL DEFAULT '',price INTEGER NOT NULL DEFAULT 20000 CHECK(price BETWEEN 1000 AND 1000000),level TEXT NOT NULL DEFAULT 'beginner',qualifications TEXT NOT NULL DEFAULT '',referral_code TEXT NOT NULL UNIQUE,referred_by TEXT REFERENCES users(id),created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS slots(id TEXT PRIMARY KEY,teacher_id TEXT NOT NULL REFERENCES users(id),start REAL NOT NULL,end REAL NOT NULL,CHECK(end>start));
CREATE TABLE IF NOT EXISTS bookings(id TEXT PRIMARY KEY,learner_id TEXT NOT NULL REFERENCES users(id),teacher_id TEXT NOT NULL REFERENCES users(id),slot_id TEXT NOT NULL REFERENCES slots(id),unit_id TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'reserved',price INTEGER NOT NULL,referrer_id TEXT REFERENCES users(id),room TEXT NOT NULL UNIQUE,created_at REAL NOT NULL,evidence TEXT NOT NULL DEFAULT '',homework TEXT NOT NULL DEFAULT '',feedback TEXT NOT NULL DEFAULT '',score INTEGER,review TEXT NOT NULL DEFAULT '',rating INTEGER,CHECK(learner_id<>teacher_id));
CREATE TABLE IF NOT EXISTS rate_snapshots(booking_id TEXT PRIMARY KEY REFERENCES bookings(id),commission_bps INTEGER NOT NULL,referral_bps INTEGER NOT NULL,processor_bps INTEGER NOT NULL,refund_bps INTEGER NOT NULL,tax_bps INTEGER NOT NULL,policy TEXT NOT NULL DEFAULT 'illustrative-test-v1');
CREATE TABLE IF NOT EXISTS unit_snapshots(booking_id TEXT PRIMARY KEY REFERENCES bookings(id),content TEXT NOT NULL,sha256 TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS unit_no_update BEFORE UPDATE ON unit_snapshots BEGIN SELECT RAISE(ABORT,'immutable unit snapshot'); END;
CREATE TRIGGER IF NOT EXISTS unit_no_delete BEFORE DELETE ON unit_snapshots BEGIN SELECT RAISE(ABORT,'immutable unit snapshot'); END;
CREATE TRIGGER IF NOT EXISTS rate_no_update BEFORE UPDATE ON rate_snapshots BEGIN SELECT RAISE(ABORT,'immutable rate snapshot'); END;
CREATE TRIGGER IF NOT EXISTS rate_no_delete BEFORE DELETE ON rate_snapshots BEGIN SELECT RAISE(ABORT,'immutable rate snapshot'); END;
CREATE UNIQUE INDEX IF NOT EXISTS active_slot ON bookings(slot_id) WHERE status NOT IN ('cancelled','refunded');
CREATE TABLE IF NOT EXISTS attendance(booking_id TEXT NOT NULL REFERENCES bookings(id),user_id TEXT NOT NULL REFERENCES users(id),joined REAL NOT NULL,last_seen REAL NOT NULL,seconds REAL NOT NULL DEFAULT 0,confirmed INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(booking_id,user_id));
CREATE TABLE IF NOT EXISTS reschedule_consents(booking_id TEXT NOT NULL REFERENCES bookings(id),user_id TEXT NOT NULL REFERENCES users(id),slot_id TEXT NOT NULL REFERENCES slots(id),created_at REAL NOT NULL,PRIMARY KEY(booking_id,user_id));
CREATE TABLE IF NOT EXISTS disputes(id TEXT PRIMARY KEY,booking_id TEXT NOT NULL REFERENCES bookings(id),reporter_id TEXT NOT NULL REFERENCES users(id),category TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',decision TEXT NOT NULL DEFAULT '',resolution TEXT NOT NULL DEFAULT '',created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY AUTOINCREMENT,booking_id TEXT NOT NULL REFERENCES bookings(id),kind TEXT NOT NULL,amount INTEGER NOT NULL,beneficiary TEXT,created_at REAL NOT NULL,UNIQUE(booking_id,kind));
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT NOT NULL,action TEXT NOT NULL,entity TEXT NOT NULL,detail TEXT NOT NULL,created_at REAL NOT NULL);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'append-only audit'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'append-only audit'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger BEGIN SELECT RAISE(ABORT,'append-only ledger'); END;

CREATE TABLE IF NOT EXISTS attendance_intervals(id INTEGER PRIMARY KEY AUTOINCREMENT,booking_id TEXT NOT NULL REFERENCES bookings(id),user_id TEXT NOT NULL REFERENCES users(id),start REAL NOT NULL,end REAL NOT NULL,CHECK(end>start));
CREATE INDEX IF NOT EXISTS attendance_intervals_lookup ON attendance_intervals(booking_id,user_id,start);
DROP INDEX IF EXISTS active_slot;
CREATE UNIQUE INDEX IF NOT EXISTS active_slot_v2 ON bookings(slot_id) WHERE status NOT IN ('cancelled','refunded','expired');

CREATE TABLE IF NOT EXISTS external_identities(project_ref TEXT NOT NULL,subject TEXT NOT NULL,user_id TEXT NOT NULL REFERENCES users(id),PRIMARY KEY(project_ref,subject));
CREATE TABLE IF NOT EXISTS payment_sessions(booking_id TEXT PRIMARY KEY REFERENCES bookings(id),session_id TEXT UNIQUE NOT NULL,url TEXT NOT NULL,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS provider_events(event_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,booking_id TEXT NOT NULL REFERENCES bookings(id),created_at REAL NOT NULL);

-- Local integration records only. This file is never applied to hosted Supabase.
CREATE TABLE IF NOT EXISTS learning_placements(user_id TEXT PRIMARY KEY REFERENCES users(id),stage INTEGER NOT NULL CHECK(stage BETWEEN 0 AND 6),groups_json TEXT NOT NULL,source TEXT NOT NULL,created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS learning_checks(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),unit_id TEXT NOT NULL,booking_id TEXT REFERENCES bookings(id),phase TEXT NOT NULL CHECK(phase IN ('pre','post')),kind TEXT NOT NULL CHECK(kind IN ('text-check','teacher-observation')),score INTEGER NOT NULL,max_score INTEGER NOT NULL,skills_json TEXT NOT NULL,notes TEXT NOT NULL,created_at REAL NOT NULL,assessor_id TEXT NOT NULL REFERENCES users(id),CHECK(score>=0 AND score<=max_score));
CREATE INDEX IF NOT EXISTS learning_checks_owner ON learning_checks(user_id,created_at DESC);
CREATE INDEX IF NOT EXISTS learning_checks_booking ON learning_checks(booking_id);
CREATE INDEX IF NOT EXISTS providers_search ON users(approved,role,price,nickname,id);
CREATE INDEX IF NOT EXISTS provider_future_slots ON slots(teacher_id,start,end);

-- Team11: per-account free curriculum progress; seven stages, fifty lessons each.
CREATE TABLE IF NOT EXISTS free_lesson_progress (
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 stage INTEGER NOT NULL CHECK(stage BETWEEN 1 AND 7),
 lesson INTEGER NOT NULL CHECK(lesson BETWEEN 1 AND 50),
 completed_at REAL NOT NULL,
 PRIMARY KEY(user_id,stage,lesson)
);
CREATE INDEX IF NOT EXISTS free_lesson_progress_user ON free_lesson_progress(user_id,stage,lesson);

-- Authenticated free-course quiz attempts and last resume location; additive migration.
CREATE TABLE IF NOT EXISTS free_quiz_results (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 stage INTEGER NOT NULL CHECK(stage BETWEEN 1 AND 7),
 lesson INTEGER NOT NULL CHECK(lesson BETWEEN 1 AND 50),
 score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
 max_score INTEGER NOT NULL CHECK(max_score BETWEEN 1 AND 100),
 request_id TEXT NOT NULL CHECK(length(request_id) BETWEEN 1 AND 100),
 recorded_at REAL NOT NULL,
 UNIQUE(user_id,request_id),
 CHECK(score<=max_score)
);
CREATE INDEX IF NOT EXISTS free_quiz_results_owner ON free_quiz_results(user_id,stage,lesson,recorded_at DESC);
CREATE TABLE IF NOT EXISTS free_resume_positions (
 user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 stage INTEGER NOT NULL CHECK(stage BETWEEN 1 AND 7),
 lesson INTEGER NOT NULL CHECK(lesson BETWEEN 1 AND 50),
 updated_at REAL NOT NULL
);
