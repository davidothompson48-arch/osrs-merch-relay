import re
import unittest
from pathlib import Path


class ScheduledRelayTests(unittest.TestCase):
    def test_job_length_matches_schedule(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/update-snapshot.yml").read_text(encoding="utf8")
        self.assertIn("cron: '7,37 * * * *'", workflow)
        count = re.search(r'for cycle in \$\(seq 1 (\d+)\); do', workflow)
        self.assertIsNotNone(count)
        self.assertEqual(int(count.group(1)), 6)
        self.assertIn("sleep_for=$((300 - elapsed))", workflow)
        self.assertRegex(workflow, r"timeout-minutes: 45")
        self.assertIn("cancel-in-progress: true", workflow)


if __name__ == "__main__":
    unittest.main()
