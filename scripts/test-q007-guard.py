import fcntl
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest

spec = importlib.util.spec_from_file_location('guard', Path(__file__).parent / 'run-one-q007.py')
guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)

class OneTaskTests(unittest.TestCase):
    def setup_case(self, code='console.log("fixture only")', duration=10):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name); (root/'scripts').mkdir(); (root/'intro.html').write_text('fixture')
        (root/'scripts/test-q007-explanations.cjs').write_text(code)
        run = root/'run'; run.mkdir()
        request = {'task':'Q007','original_number':45,'input_sha':guard.INPUT_SHA,
                   'source_sha256':guard.digest(root/'intro.html'),
                   'test_sha256':guard.digest(root/'scripts/test-q007-explanations.cjs'),
                   'deadline':time.time()+duration}
        (run/'REQUEST.json').write_text(json.dumps(request))
        return root, run, request

    def test_success_stops_and_refuses_replay(self):
        root,run,_=self.setup_case()
        result=guard.run(root,run); self.assertEqual(result['status'],'PASS_STOPPED')
        original=(run/'RESULT.json').read_bytes()
        with self.assertRaisesRegex(RuntimeError,'NO_REPLAY'):guard.run(root,run)
        self.assertEqual((run/'RESULT.json').read_bytes(),original)
        self.assertFalse(result['next_task_created'])

    def test_failure_stops_and_refuses_replay(self):
        root,run,_=self.setup_case('process.exit(7)')
        self.assertEqual(guard.run(root,run)['status'],'FAIL_STOPPED')
        with self.assertRaisesRegex(RuntimeError,'NO_REPLAY'):guard.run(root,run)

    def test_timeout_stops_child(self):
        root,run,_=self.setup_case('setInterval(()=>{},100)',duration=.2)
        self.assertEqual(guard.run(root,run)['status'],'TIMEOUT_STOPPED')

    def test_crashed_run_is_not_restarted(self):
        root,run,_=self.setup_case();(run/'STARTED.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'NO_REPLAY'):guard.run(root,run)

    def test_duplicate_lock_rejected(self):
        root,run,_=self.setup_case()
        with (run/'LOCK').open('a') as held:
            fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):guard.run(root,run)

    def test_next_task_or_wrong_source_rejected(self):
        for field,value in [('task','Q008'),('original_number',46),('input_sha','wrong'),('source_sha256','wrong'),('test_sha256','wrong')]:
            root,run,request=self.setup_case();request[field]=value;(run/'REQUEST.json').write_text(json.dumps(request))
            with self.assertRaisesRegex(RuntimeError,'MISMATCH'):guard.run(root,run)
            self.assertFalse((run/'STARTED.json').exists())

    def test_deadline_rejected_before_start(self):
        for duration in [-1,1600]:
            root,run,_=self.setup_case(duration=duration)
            with self.assertRaisesRegex(RuntimeError,'DEADLINE'):guard.run(root,run)
            self.assertFalse((run/'STARTED.json').exists())

    def test_mutation_prevents_pass(self):
        root,run,_=self.setup_case('require("fs").writeFileSync("intro.html","changed")')
        self.assertEqual(guard.run(root,run)['status'],'BINDING_CHANGED_STOPPED')

if __name__=='__main__':unittest.main()
