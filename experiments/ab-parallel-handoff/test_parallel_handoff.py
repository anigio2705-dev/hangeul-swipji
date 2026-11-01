"""A/B parallel handoff proof. Simulation only: no AI API, GitHub writes, or READY promotion."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
import time
import unittest

def run_pilot():
    qa_queue = Queue()
    a_started_next = Event()
    b_finished_first = Event()
    events = []

    def developer():
        for task in (110, 111):
            events.append(("A_START", task))
            if task == 111:
                a_started_next.set()
                if b_finished_first.is_set():
                    raise AssertionError("A waited for B instead of starting task 111")
            time.sleep(0.02)
            qa_queue.put(task)
            events.append(("A_HANDOFF", task))
        qa_queue.put(None)

    def independent_qa():
        while True:
            task = qa_queue.get(timeout=3)
            if task is None:
                return
            if task == 110:
                if not a_started_next.wait(timeout=3):
                    raise AssertionError("A did not start task 111 while B was reviewing 110")
                time.sleep(0.02)
                b_finished_first.set()
            events.append(("B_PASS_SIMULATED", task))

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(developer)
        b = pool.submit(independent_qa)
        a.result(timeout=5)
        b.result(timeout=5)
    return events

class ParallelHandoffTests(unittest.TestCase):
    def test_a_continues_while_b_reviews(self):
        events = run_pilot()
        self.assertLess(events.index(("A_START", 111)), events.index(("B_PASS_SIMULATED", 110)))
        self.assertEqual(sum(event == "B_PASS_SIMULATED" for event, _ in events), 2)

if __name__ == "__main__":
    unittest.main()
