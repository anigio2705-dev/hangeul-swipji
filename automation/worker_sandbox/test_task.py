import unittest
from task import calculate_total

class TestTask(unittest.TestCase):
    def test_total(self):
        self.assertEqual(calculate_total(2, 3), 5)
        self.assertEqual(calculate_total(-2, 3), 1)

if __name__ == '__main__':
    unittest.main()
