"""Exercise real curriculum, ownership, grading and unrestricted paged discovery."""
import datetime as dt
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import server
import learning
import test_server as fixtures

class GlobalLearningTests(unittest.TestCase):
    setUp=fixtures.PlatformTests.setUp
    tearDown=fixtures.PlatformTests.tearDown
    register=fixtures.PlatformTests.register
    action=fixtures.PlatformTests.action
    def real_units(self):
        self.units_patch.stop()
        return server.units()
    def create_real_booking(self):
        units=self.real_units();unit=units[4]
        s,x=self.learner.call('/api/bookings',{'teacherId':self.t['id'],'slotId':self.slot,'unitId':unit['id']})
        self.assertEqual(200,s,x);return x['bookingId'],unit
    def test_96_slots_and_24_authored_with_original_12_untouched(self):
        units=self.real_units();self.assertEqual(24,len(units));p=learning.catalog()
        self.assertEqual(4,len(p['stages']));slots=[x for st in p['stages'] for x in st['lessons']]
        self.assertEqual(96,len(slots));self.assertEqual(24,sum(x['status']=='authored' for x in slots));self.assertEqual(72,sum(x['status']=='planned' for x in slots))
        self.assertEqual(24,len({u['reading'] for u in units}));self.assertEqual(72,sum(len(u['assessment']) for u in units))
        for u in units:
            self.assertTrue(u['teacherNotes']);self.assertTrue(u['performanceRubric'])
            for phase in ('pre','post'):
                qs=learning.diagnostic(u['id'],phase);self.assertEqual(3,len(qs))
                for q in qs:self.assertEqual(3,len(set(q['choices'])));self.assertIn(q['answerIndex'],range(3))
        for u in json.loads((server.ROOT/'content-expansion.json').read_text())['units']:
            for a in u['assessment']:
                for e in a['evidence']:self.assertIn(e,u['reading']+' '+' '.join(u['dialogue']))
    def test_public_catalog_and_unapproved_provider_do_not_receive_private_guides(self):
        units=self.real_units();s,x=self.outsider.call('/api/units');self.assertEqual(200,s)
        self.assertFalse(any('_diagnostics' in u or 'teacherGuide' in u or 'teacherNotes' in u for u in x['units']))
        applicant,_=self.register('teacher','applicant')
        s,x=applicant.call('/api/units/'+units[0]['id']);self.assertEqual(200,s);self.assertNotIn('teacherGuide',x['unit'])
        self.assertEqual(200,applicant.call('/api/availability',{'start':self.clock+10000,'end':self.clock+13000})[0])
        own=applicant.call('/api/me')[1]['user']['id']
        self.assertEqual(1,len(applicant.call('/api/availability?teacherId='+own)[1]['slots']))
        self.assertEqual([],self.learner.call('/api/availability?teacherId='+own)[1]['slots'])
        self.assertNotIn(own,[u['id'] for u in self.learner.call('/api/teachers')[1]['teachers']])
        s,x=self.teacher.call('/api/units/'+units[0]['id']);self.assertIn('teacherGuide',x['unit']);self.assertNotIn('_diagnostics',x['unit'])
        self.assertEqual(404,self.learner.call('/api/units/S1-24')[0])
    def test_placement_validation_and_account_isolation(self):
        self.assertEqual(200,self.learner.call('/api/learning/placement',{'groups':[2,3,1,0],'userId':self.o['id']})[0])
        s,x=self.learner.call('/api/learning');self.assertEqual(1,x['placement']['stage']);self.assertEqual(0,x['placement']['stage']<0)
        self.assertIsNone(self.outsider.call('/api/learning')[1]['placement'])
        for groups in [[True,1,2,3],[6,0,0,0],[1,2,3],'invalid']:
            self.assertEqual(400,self.learner.call('/api/learning/placement',{'groups':groups})[0])
    def test_real_pre_post_grading_not_client_score_and_immutable_snapshot(self):
        bid,unit=self.create_real_booking();qs=unit['_diagnostics']['pre'];answers=[q['answerIndex'] for q in qs]
        s,x=self.learner.call('/api/learning/check',{'unitId':unit['id'],'phase':'pre','answers':answers,'bookingId':bid,'score':999})
        self.assertEqual(200,s,x);self.assertEqual(3,x['score'])
        self.action(self.learner,bid,'pay-test')
        self.assertEqual(403,self.learner.call('/api/learning/check',{'unitId':unit['id'],'phase':'post','answers':[0,0,0],'bookingId':bid})[0])
        self.clock+=600;self.assertEqual(200,self.action(self.learner,bid,'join')[0])
        # A later editorial change must not rewrite the booked check or expected keys.
        with patch.object(learning,'diagnostic',lambda *a:[{'question':'changed','choices':['a','b','c'],'answerIndex':(q['answerIndex']+1)%3,'skill':'reading'} for q in unit['_diagnostics']['post']]):
            expected=[q['answerIndex'] for q in unit['_diagnostics']['post']]
            s,x=self.learner.call('/api/learning/check',{'unitId':unit['id'],'phase':'post','answers':expected,'bookingId':bid})
            self.assertEqual(200,s,x);self.assertEqual(3,x['score'])
        self.assertEqual(403,self.outsider.call('/api/learning/check',{'unitId':unit['id'],'phase':'post','answers':[0,0,0],'bookingId':bid})[0])
        self.assertEqual(403,self.outsider.call('/api/learning/booking/'+bid)[0])
        self.assertEqual(2,len(self.teacher.call('/api/learning/booking/'+bid)[1]['records']))
        with server.connect() as db:
            for _ in range(51):learning.submit(db,self.l['id'],unit['id'],'pre',[0,0,0])
        self.assertEqual(50,len(self.learner.call('/api/learning')[1]['records']))
        self.assertEqual(2,len(self.teacher.call('/api/learning/booking/'+bid)[1]['records']))
        self.assertEqual([],self.outsider.call('/api/learning')[1]['records'])
    def test_teacher_observation_is_booked_provider_only_and_requires_evidence(self):
        bid,unit=self.create_real_booking();data={'bookingId':bid,'phase':'pre','ratings':{'pronunciation':1,'grammar':2,'interaction':3},'note':'Learner required repeated clarification on final consonants.'}
        self.assertEqual(403,self.learner.call('/api/learning/observation',data)[0]);self.assertEqual(403,self.outsider.call('/api/learning/observation',data)[0])
        self.assertEqual(200,self.teacher.call('/api/learning/observation',data)[0]);self.assertEqual(400,self.teacher.call('/api/learning/observation',dict(data,note='short'))[0])
        self.assertEqual(409,self.teacher.call('/api/learning/observation',dict(data,phase='post'))[0])
        record=self.learner.call('/api/learning')[1]['records'][0];self.assertEqual('teacher-observation',record['kind']);self.assertEqual(6,record['score'])
    def test_many_providers_can_be_found_across_pages_and_time_filters(self):
        with server.connect() as db:
            for i in range(24):
                uid=f'provider{i:02}'
                db.execute('INSERT INTO users(id,email,password,nickname,role,approved,specialty,referral_code,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(uid,uid+'@example.test','unused','Provider '+str(i),'teacher',1,'직장 회화',uid,self.clock))
                db.execute('INSERT INTO slots VALUES(?,?,?,?)',('slot'+uid,uid,self.clock+7200,self.clock+10800))
        seen=set()
        for offset in (0,10,20):
            s,x=self.learner.call('/api/teachers?limit=10&offset='+str(offset));self.assertEqual(200,s);self.assertEqual(25,x['total']);seen.update(t['id'] for t in x['teachers'])
        self.assertEqual(25,len(seen));s,x=self.learner.call('/api/teachers?purpose=%EC%A7%81%EC%9E%A5&from='+dt.datetime.fromtimestamp(self.clock+7000,dt.timezone.utc).isoformat().replace('+','%2B')+'&to='+dt.datetime.fromtimestamp(self.clock+11000,dt.timezone.utc).isoformat().replace('+','%2B'))
        self.assertEqual(200,s,x);self.assertEqual(24,x['total']);self.assertTrue(x['hasMore'])
        self.assertEqual(400,self.learner.call('/api/teachers?limit=0')[0]);self.assertEqual(400,self.learner.call('/api/teachers?from=1')[0])
