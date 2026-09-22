import unittest
from pathlib import Path

POLICY = Path(__file__).parents[1] / "SKILL.md"

class PolicyContract(unittest.TestCase):
    def setUp(self): self.text = POLICY.read_text()
    def test_concise_and_controls(self):
        self.assertLessEqual(len(self.text.splitlines()), 180)
        for phrase in ("swarm everything", "no task too small", "full-history fanout", "mandatory background agents"):
            self.assertNotIn(phrase, self.text)
        for phrase in ("fork_turns=none", "60s", "pause/interrupt", "cost band", "narrow tests"):
            self.assertIn(phrase, self.text)
        for phrase in ("one independent review", "one targeted remediation", "context-handoff", "no default cumulative-token approval gate"):
            self.assertIn(phrase, self.text)
        self.assertNotIn("start no new phase or agent without explicit user confirmation", self.text)
        for phrase in ("default GitHub account is `Comradery64`", "Use `RadixAlan` only", "restore `Comradery64`"):
            self.assertIn(phrase, self.text)

if __name__ == "__main__": unittest.main()
