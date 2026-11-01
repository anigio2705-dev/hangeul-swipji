#!/usr/bin/env python3
"""Isolated 4-minute rotation dry-run. Never calls an AI API or product services."""
import argparse
import datetime as dt
import json
import os
import sqlite3
import time

TEAMS = ("C", "D", "A", "B")
PERIOD = 240
EPOCH = dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc).timestamp()

def slot(at):
    sequence = int((at - EPOCH) // PERIOD)
    return sequence, TEAMS[sequence % 4], EPOCH + sequence * PERIOD

def init(db):
    db.execute("CREATE TABLE IF NOT EXISTS ticks (seq INTEGER PRIMARY KEY, team TEXT NOT NULL, scheduled_utc TEXT NOT NULL, actual_utc TEXT NOT NULL, lag_seconds REAL NOT NULL)")
    db.commit()

def record(db, at):
    seq, team, due = slot(at)
    scheduled = dt.datetime.fromtimestamp(due, dt.timezone.utc).isoformat()
    actual = dt.datetime.fromtimestamp(at, dt.timezone.utc).isoformat()
    cur = db.execute("INSERT OR IGNORE INTO ticks VALUES (?,?,?,?,?)", (seq, team, scheduled, actual, round(at - due, 3)))
    db.commit()
    if cur.rowcount:
        print(json.dumps({"seq":seq,"team":team,"scheduled_utc":scheduled,"actual_utc":actual,"lag_seconds":round(at-due,3),"status":"DRY_RUN_ONLY"}),flush=True)
    return bool(cur.rowcount)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--db",default=os.environ.get("ROTATION_DB","/tmp/hangeul-rotation-dryrun.sqlite3"))
    p.add_argument("--once",action="store_true")
    p.add_argument("--simulate",type=int,default=0,metavar="TICKS")
    args=p.parse_args()
    with sqlite3.connect(args.db,timeout=15) as db:
        init(db)
        if args.simulate:
            if not 1 <= args.simulate <= 10000: p.error("--simulate must be 1..10000")
            start=slot(time.time())[0]
            for seq in range(start,start+args.simulate):
                record(db,EPOCH+seq*PERIOD)
            return
        if args.once:
            record(db,time.time())
            return
        while True:
            now=time.time()
            record(db,now)
            _,_,due=slot(now)
            time.sleep(max(0.5,min(30,due+PERIOD-time.time())))

if __name__=="__main__":
    main()
