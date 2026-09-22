import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "token_budget_guard.py"

def write(p, sid, parent=None, totals=(0,), turns=1, malformed=False, timestamp="2026-01-01T00:00:00Z", shape="info"):
    rows = [{"type":"session_meta","payload":{"id":sid,"timestamp":timestamp, **({"parent_thread_id":parent} if parent else {})}}, {"type":"turn_context","payload":{}}]
    for total in totals:
        usage = {"input_tokens":total,"cached_input_tokens":total // 2,"total_tokens":total}
        payload = {"info":{"total_token_usage":usage}} if shape == "info" else {shape:usage}
        rows.append({"type":"token_usage_record","payload":payload})
    rows.extend({"type":"turn_context","payload":{}} for _ in range(max(0, turns - 1)))
    text = "{bad\n" if malformed else ""
    p.write_text(text + "\n".join(json.dumps(x) for x in rows))

class GuardTests(unittest.TestCase):
    def run_guard(self, root, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--cwd", str(root), "--json", *args], capture_output=True, text=True)
    def test_tree_latest_no_double_count_and_thresholds(self):
        with tempfile.TemporaryDirectory() as d:
            s=Path(d)/"sessions"; s.mkdir(); write(s/"root.jsonl","r",totals=(100,300)); write(s/"child.jsonl","c","r",totals=(200,))
            r=self.run_guard(d,"--session",str(s/"root.jsonl"),"--soft-limit","250","--hard-limit","250"); self.assertEqual(r.returncode,20); self.assertEqual(json.loads(r.stdout)["tokens"]["total_tokens"],300)
            root_only=self.run_guard(d,"--session",str(s/"root.jsonl")); self.assertEqual(json.loads(root_only.stdout)["tokens"]["total_tokens"],300); self.assertEqual(json.loads(root_only.stdout)["threads"],1)
            tree=self.run_guard(d,"--session",str(s/"root.jsonl"),"--tree","--hard-limit","250"); self.assertEqual(tree.returncode,20); self.assertEqual(json.loads(tree.stdout)["threads"],2); self.assertEqual(json.loads(tree.stdout)["tokens"]["total_tokens"],500)
    def test_malformed_and_no_newest_root_selection(self):
        with tempfile.TemporaryDirectory() as d:
            s=Path(d)/"sessions"; s.mkdir(); write(s/"old.jsonl","o",totals=(1,),timestamp="2026-01-01T00:00:00Z"); write(s/"new.jsonl","n",totals=(2,),malformed=True,timestamp="2026-01-02T00:00:00Z")
            r=self.run_guard(d,"--session",str(s/"new.jsonl")); self.assertEqual(r.returncode,0); self.assertEqual(json.loads(r.stdout)["session"],"n")
            r=self.run_guard(d,"--session","unknown"); self.assertEqual(r.returncode,30)

    def test_supported_shapes_and_unknown_exit(self):
        for shape in ("usage", "thread_token_usage", "info"):
            with self.subTest(shape=shape), tempfile.TemporaryDirectory() as d:
                s=Path(d)/"sessions"; s.mkdir(); p=s/"root.jsonl"; write(p,"r",totals=(101,),shape=shape)
                with p.open("a") as fh:
                    fh.write("\n" + json.dumps({"type":"response_item","payload":{"message":"TOP_SECRET_SENTINEL"}}))
                r=self.run_guard(d,"--session",str(p),"--soft-limit","100"); self.assertEqual(r.returncode,10)
                self.assertNotIn("TOP_SECRET_SENTINEL", r.stdout)
        with tempfile.TemporaryDirectory() as d:
            s=Path(d)/"sessions"; s.mkdir(); write(s/"root.jsonl","r",totals=())
            r=self.run_guard(d,"--session",str(s/"root.jsonl")); self.assertEqual(r.returncode,30); self.assertEqual(json.loads(r.stdout)["status"],"unknown")

    def test_per_request_usage_is_summed_when_no_cumulative_total_exists(self):
        with tempfile.TemporaryDirectory() as d:
            s=Path(d)/"sessions"; s.mkdir(); write(s/"root.jsonl","r",totals=(40,60),shape="usage")
            r=self.run_guard(d,"--session",str(s/"root.jsonl"),"--soft-limit","100")
            body=json.loads(r.stdout); self.assertEqual(r.returncode,10)
            self.assertEqual(body["tokens"]["total_tokens"],100)
            self.assertEqual(body["measurement"],"cumulative-usage-not-context")

    def test_no_default_cap(self):
        with tempfile.TemporaryDirectory() as d:
            s=Path(d)/"sessions"; s.mkdir(); write(s/"root.jsonl","r",totals=(9000000,))
            r=self.run_guard(d,"--session",str(s/"root.jsonl"))
            self.assertEqual(r.returncode,0)
            self.assertIsNone(json.loads(r.stdout)["default_hard_limit"])

if __name__ == "__main__": unittest.main()
