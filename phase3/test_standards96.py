"""Teaching-standard coverage and task grading are distinct from human educational approval."""
import hashlib,json,subprocess,unittest
from pathlib import Path
import server,learning,education_standards
import test_server as fixtures
class Standards96Tests(unittest.TestCase):
    setUp=fixtures.PlatformTests.setUp
    tearDown=fixtures.PlatformTests.tearDown
    register=fixtures.PlatformTests.register
    def real(self):self.units_patch.stop();return server.units()
    def test_all_96_link_four_skills_five_phases_and_exact_five_reference_documents(self):
        for u in self.real():
            m=u['teacherStandards'];self.assertEqual(5,len(m['sourceReferences']));self.assertEqual(5,len(m['flow']));self.assertEqual(3,len(m['prompts']));self.assertEqual(3,len(m['anticipatedErrors']))
            self.assertEqual({'listening','speaking','reading','writing'},set(u['performanceAreas']))
            self.assertEqual({'listening','speaking','reading','writing'},{a['area'] for a in m['fourSkillAssessments']})
            self.assertTrue(all(not a['autoApproved'] for a in m['fourSkillAssessments']))
            for ref in m['sourceReferences']:self.assertEqual(ref['sha256'],hashlib.sha256((server.ROOT.parent/ref['path']).read_bytes()).hexdigest())
    def test_original_24_source_materials_preserved_exactly(self):
        # Educational source data and the audio manifest are immutable. The landing page
        # is an evolving UI and is verified by separate integration/browser checks.
        for f in ('phase3/content.json','phase3/content-expansion.json','hangul-audio-manifest.json'):
            self.assertEqual((server.ROOT.parent/f).read_bytes(),subprocess.check_output(['git','show','7418e32:'+f],cwd=server.ROOT.parent))
    def test_all_new_72_have_unique_reading_questions_and_correct_grade_without_client_score(self):
        self.real();us=json.loads((server.ROOT/'content-remaining72.json').read_text())['units'];self.assertEqual(72,len(us))
        self.assertEqual(72,len({u['reading'] for u in us}));self.assertEqual(216,len({a['question'] for u in us for a in u['assessment']}))
        with server.connect() as db:
            for u in us:
                qs=learning.diagnostic(u['id'],'post');correct=[q['answerIndex'] for q in qs]
                x=learning.submit(db,self.l['id'],u['id'],'post',correct);self.assertEqual(3,x['score']);self.assertFalse(x['certified'])
                wrong=[(a+1)%3 for a in correct];self.assertEqual(0,learning.submit(db,self.l['id'],u['id'],'post',wrong)['score'])
    def test_teacher_observation_separates_real_four_skills_from_text_checks(self):
        self.real();u=server.units()[0];uid=self.l['id']
        with server.connect() as db:
            ratings={k:2 for k in ('pronunciation','grammar','interaction','listening','speaking','reading','writing')}
            b={'learner_id':uid,'unit_id':u['id'],'id':None}
            x=learning.teacher_rating(db,b,self.t['id'],'post',ratings,'Observed task only; no actual media or listening approval simulated.')
            self.assertTrue(x['fourSkillsObserved']);self.assertFalse(x['certified']);self.assertEqual(28,x['maxScore'])
            qs=learning.diagnostic(u['id'],'post');learning.submit(db,uid,u['id'],'post',[q['answerIndex'] for q in qs])
            result=learning.summary(db,uid);self.assertEqual(2,result['observedSkillChecks']['reading']['earned']);self.assertIn('reading',result['weakSkills']);self.assertEqual(1,result['textCheckSkillChecks']['reading']['earned'])
    def test_new_guide_is_only_for_approved_provider_and_snapshot_keeps_standards(self):
        us=self.real();uid=us[-1]['id'];s,x=self.learner.call('/api/units/'+uid);self.assertEqual(200,s);self.assertNotIn('teacherStandards',x['unit']);self.assertIn('performanceAreas',x['unit'])
        s,x=self.teacher.call('/api/units/'+uid);self.assertEqual(200,s);self.assertIn('teacherStandards',x['unit'])
        s,b=self.learner.call('/api/bookings',{'teacherId':self.t['id'],'slotId':self.slot,'unitId':uid});self.assertEqual(200,s,b)
        own=self.teacher.call('/api/bookings/'+b['bookingId']+'/unit')[1]['unit'];self.assertEqual(education_standards.VERSION,own['teacherStandards']['version'])
        learner=self.learner.call('/api/bookings/'+b['bookingId']+'/unit')[1]['unit'];self.assertNotIn('teacherStandards',learner)
