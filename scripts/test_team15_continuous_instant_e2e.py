"""Team15: one real HTTP/SQLite student→instant-session→verified mock ledger journey.

Team13 supplies authenticated instant HTTP, server-side event and booking.
Team14 consumes THAT exact event and DB-priced booking, not a fabricated fixture.
Three SQLite files are nonproduction. No video/audio or real money.
"""
import json
import os
import tempfile
import unittest
import time
import sqlite3

import server
import instant_matching as matching
from test_staging import StagingTests as StagingHarness
from team14_persistent import MonthlyStore, SimError
from team14_referral_store import ReferralStore
from team14_statements import lesson_statement
from team14_instant_verified_bridge import settle_verified_instant_event, refund_verified_instant_settlement


class Team15ContinuousJourney(unittest.TestCase):
    setUp=StagingHarness.setUp
    tearDown=StagingHarness.tearDown
    request=StagingHarness.request

    def account(self,name,role="learner",referral_code=None,approved=False):
        body={"email":name+"@example.test","password":"Disposable-Password-12345!",
              "nickname":name,"role":role,"adultConsent":True}
        if referral_code:body["referralCode"]=referral_code
        status,_,payload=self.request("/api/register",body)
        self.assertEqual(status,200,payload)
        user=json.loads(payload)["user"]
        cookie=self.cookie
        if approved:
            with server.connect() as db:
                db.execute("UPDATE users SET approved=1 WHERE id=?",(user["id"],))
        return cookie,user["id"]

    def api(self,cookie,path,body=None,expected=200):
        status,_,raw=self.request(path,body,headers={"Cookie":cookie})
        print(json.dumps({"path":path,"status":status,"expected":expected,"detail":raw.decode()[:180] if status!=200 else ""},ensure_ascii=False),flush=True)
        self.assertEqual(status,expected,raw)
        return json.loads(raw)

    def test_one_identical_booking_and_event_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            monthly_path=os.path.join(tmp,"monthly.sqlite")
            referral_path=os.path.join(tmp,"referrals.sqlite")
            store=MonthlyStore(monthly_path)
            referrals=ReferralStore(referral_path)
            try:
                parent,parent_id=self.account("referring-parent")
                with server.connect() as db:
                    code=db.execute("SELECT referral_code FROM users WHERE id=?",(parent_id,)).fetchone()[0]
                student,student_id=self.account("student",referral_code=code)
                teacher,teacher_id=self.account("teacher","partner",approved=True)
                outsider,outsider_id=self.account("outsider")
                self.api("", "/api/instant/join",{},401)
                self.api(student,"/api/free-progress",{"stage":1,"lesson":1})
                self.api(student,"/api/free-progress/quiz",{"stage":1,"lesson":1,"score":4,"maxScore":5,"requestId":"quiz-1"})
                self.api(student,"/api/free-progress/position",{"stage":1,"lesson":2})
                self.assertEqual(self.api(outsider,"/api/free-progress")["count"],0)
                self.api(student,"/api/logout",{})
                self.api(student,"/api/login",{"email":"student@example.test","password":"Disposable-Password-12345!"})
                student=self.cookie
                self.assertEqual(self.api(student,"/api/free-progress")["count"],1)
                self.assertEqual(self.api(student,"/api/free-progress/quiz")["count"],1)
                self.assertEqual(self.api(student,"/api/free-progress/position")["position"]["lesson"],2)
                self.assertEqual(self.api(outsider,"/api/free-progress/quiz")["count"],0)
                self.assertIsNone(self.api(outsider,"/api/free-progress/position")["position"])
                self.assertEqual("waiting",self.api(student,"/api/instant/join",{})["state"])
                offer=self.api(teacher,"/api/instant/join",{})
                self.assertEqual("offered",offer["state"])
                match_id=offer["matchId"]
                self.api(outsider,"/api/instant/ready",{"matchId":match_id},409)
                self.api(student,"/api/instant/ready",{"matchId":match_id})
                active=self.api(teacher,"/api/instant/ready",{"matchId":match_id})
                self.assertEqual("active",active["state"])
                self.assertTrue(active["roomUrl"].startswith("https://meet.jit.si/"))
                learner_session=self.api(student,"/api/instant/session")
                teacher_session=self.api(teacher,"/api/instant/session")
                booking_id=learner_session["bookingId"]
                self.assertEqual(booking_id,teacher_session["bookingId"])
                self.assertEqual(learner_session["roomUrl"],teacher_session["roomUrl"])
                rejoin=self.api(student,"/api/instant/join",{})
                self.assertEqual(rejoin["matchId"],match_id)
                self.assertEqual(rejoin["state"],"active")
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM instant_booking_links WHERE match_id=?",(match_id,)).fetchone()[0],1)
                self.api(outsider,"/api/instant/session-observe",{"matchId":match_id},409)
                self.api(student,"/api/instant/session-finish",{"matchId":match_id},409)
                self.api(student,"/api/instant/session-observe",{"matchId":match_id})
                self.api(teacher,"/api/instant/session-observe",{"matchId":match_id})
                done=self.api(student,"/api/instant/session-finish",{"matchId":match_id})
                self.assertEqual(booking_id,done["bookingId"])
                event_id=done["event"]["eventId"]
                self.api(teacher,"/api/instant/session-finish",{"matchId":match_id},409)
                with server.connect() as db:
                    booking=db.execute("SELECT * FROM bookings WHERE id=?",(booking_id,)).fetchone()
                    self.assertEqual((booking["learner_id"],booking["teacher_id"],booking["status"]),(student_id,teacher_id,"completed"))
                    self.assertEqual(db.execute("SELECT count(*) FROM instant_lesson_events WHERE booking_id=?",(booking_id,)).fetchone()[0],1)
                    price=booking["price"]
                    self.assertGreater(price,0)
                    self.assertEqual(matching.verified_event_for_team14(db,event_id)["amount"],price)
                store.create_month("team15month",[("team15lesson",booking_id,price)])
                with server.connect() as db:
                    with self.assertRaises(SimError):settle_verified_instant_event(db,store,referrals,"forged-event")
                    first=settle_verified_instant_event(db,store,referrals,event_id)
                    self.assertEqual(first,settle_verified_instant_event(db,store,referrals,event_id))
                    self.assertFalse(first["payment_executed"])
                    award=referrals.awards_for_lesson("team15lesson")
                    self.assertEqual(award["recipients"][0]["user_id"],parent_id)
                    before=lesson_statement(store,"team15month","team15lesson")
                    self.assertEqual(before["teacher_krw"]+before["referral_krw"]+before["platform_krw"],price)
                    with self.assertRaises(SimError):
                        refund_verified_instant_settlement(db,store,booking_id,"unauthorized",100,outsider_id)
                    part=refund_verified_instant_settlement(db,store,booking_id,"refund_partial",1000,student_id)
                    self.assertEqual(part,refund_verified_instant_settlement(db,store,booking_id,"refund_partial",1000,student_id))
                    with self.assertRaises(SimError):
                        refund_verified_instant_settlement(db,store,booking_id,"too_large",price,student_id)
                    full=refund_verified_instant_settlement(db,store,booking_id,"refund_remaining",price-1000,student_id)
                    after=lesson_statement(store,"team15month","team15lesson")
                    self.assertEqual(after["refunded_krw"],price)
                    self.assertEqual(after["teacher_krw"]+after["referral_krw"]+after["platform_krw"],0)
                store.close();referrals.close()
                store=MonthlyStore(monthly_path)
                referrals=ReferralStore(referral_path)
                with server.connect() as db:
                    self.assertEqual(db.execute("SELECT count(*) FROM instant_lesson_events WHERE event_id=?",(event_id,)).fetchone()[0],1)
                    self.assertEqual(first,settle_verified_instant_event(db,store,referrals,event_id))
                    self.assertEqual(part,refund_verified_instant_settlement(db,store,booking_id,"refund_partial",1000,student_id))
                    self.assertEqual(full,refund_verified_instant_settlement(db,store,booking_id,"refund_remaining",price-1000,student_id))
                final=lesson_statement(store,"team15month","team15lesson")
                self.assertEqual(final["refunded_krw"],price)
                self.assertEqual(final["teacher_krw"]+final["referral_krw"]+final["platform_krw"],0)
                print("TEAM15 PASS one HTTP booking:",booking_id,"event:",event_id,"amount_krw:",price,"real_money: false",flush=True)
            finally:
                store.close()
                referrals.close()

if __name__=="__main__":unittest.main(verbosity=2)
