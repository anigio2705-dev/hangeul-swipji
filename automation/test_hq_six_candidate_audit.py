"""Read-only six-team candidate intake: never equate paths with readiness."""
import json
import re
import unittest
from pathlib import Path
from hq_160_task_cycle import contracts
ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"11": 11, "12": 45, "13": 23, "14": 101, "15": 9, "16": 143}
COUNTS = {"11": 30, "12": 30, "13": 30, "14": 40, "15": 20, "16": 10}
class SixTeamCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = json.loads((ROOT/"automation/hq_six_candidate_audit.json").read_text())
        cls.tasks = contracts((ROOT/"automation/hq_backlog_160.md").read_text())
    def test_canonical_160_owners(self):
        self.assertEqual(list(range(1,161)), list(self.tasks))
        self.assertEqual(COUNTS,{t:sum(v["owner"]==t for v in self.tasks.values()) for t in COUNTS})
    def test_six_candidate_real_paths_and_no_fake_ready(self):
        self.assertEqual(1,self.c["schema"])
        self.assertEqual(set(EXPECTED),set(self.c["candidates"]))
        touched=set()
        for team,item in self.c["candidates"].items():
            with self.subTest(team=team):
                self.assertEqual(EXPECTED[team],item["task"])
                self.assertEqual(team,item["owner"])
                self.assertEqual(team,self.tasks[item["task"]]["owner"])
                self.assertTrue(set(item["support"]).issubset(self.tasks[item["task"]]["support"]))
                self.assertEqual("CANDIDATE",item["state"])
                self.assertEqual("PENDING",item["independent_team15"])
                self.assertFalse(item["development_dispatched"])
                self.assertTrue(item["acceptance"] and item["blockers"] and item["next_action"])
                for path in item["source_paths"]+item["test_paths"]:
                    file=(ROOT/path).resolve()
                    self.assertTrue(file.is_relative_to(ROOT) and file.is_file(),path)
                for path in item["source_paths"]:
                    self.assertNotIn(path,touched)
                    touched.add(path)
    def test_blocked_22_47_and_partial_45_remain_closed(self):
        reg=json.loads((ROOT/"automation/hq_semantic_contract_paths.json").read_text())["items"]
        self.assertEqual("BLOCKED",reg["22"]["state"])
        self.assertEqual("BLOCKED",reg["47"]["state"])
        self.assertEqual("CANDIDATE",reg["45"]["state"])
        self.assertIn("0/1758"," ".join(reg["45"]["unmet"]))
    def test_team16_conflicting_language_menus_are_visible(self):
        site=(ROOT/"site-language.js").read_text()
        global_js=(ROOT/"global-language.js").read_text()
        a=re.search(r"languages=\[(.*?)\];",site,re.S)
        b=re.search(r"const langs=\[(.*?)\];",global_js,re.S)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        first=set(re.findall(r'\["([^"]+)"\s*,',a.group(1)))
        second=set(re.findall(r"\['([^']+)'\s*,",b.group(1)))
        self.assertEqual({"ko","en","ja","es","zh-CN","ru","mn","vi"},first)
        self.assertTrue(first.issubset(second))
        self.assertTrue(second-first)
if __name__=="__main__": unittest.main()
