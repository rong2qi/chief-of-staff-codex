import importlib.util, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "context-handoff/scripts/context_handoff.py"
SPEC = importlib.util.spec_from_file_location("context_handoff", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(MODULE)

def session(path, used):
    events = [
        {"timestamp":"2026-08-23T00:00:00Z","type":"session_meta","payload":{"id":"thread-1","cwd":str(path.parent)}},
        {"timestamp":"2026-08-23T00:01:00Z","type":"event_msg","payload":{"type":"token_count","info":{"total_token_usage":{"input_tokens":999999},"last_token_usage":{"input_tokens":used},"model_context_window":1000},"rate_limits":{"primary":{"used_percent":99}}}},
    ]
    path.write_text("".join(json.dumps(x)+"\n" for x in events), encoding="utf-8")

class ContextHandoffTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual([MODULE.state(x) for x in (.74,.75,.84,.85,.95)], ["normal","checkpoint","checkpoint","rollover","emergency"])

    def test_ignores_total_and_rate_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"s.jsonl"; session(path,740)
            self.assertEqual(MODULE.inspect(path)["state"], "normal")

    def test_bundle_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/"s.jsonl"; handoff=root/"h.md"; artifacts=root/"a.json"; codex=root/"codex"
            session(source,850); handoff.write_text("# Handoff\nNext: verify.\n"); artifacts.write_text("{}\n")
            env=dict(os.environ,CODEX_HOME=str(codex))
            result=subprocess.run([sys.executable,str(SCRIPT),"build","--session",str(source),"--title","Task","--handoff",str(handoff),"--artifacts",str(artifacts)],check=True,capture_output=True,text=True,env=env)
            bundle=Path(json.loads(result.stdout)["bundle"])
            valid=subprocess.run([sys.executable,str(SCRIPT),"verify","--bundle",str(bundle)],capture_output=True,text=True)
            self.assertEqual(valid.returncode,0,valid.stdout)
            (bundle/"handoff.md").write_text("tampered\n")
            invalid=subprocess.run([sys.executable,str(SCRIPT),"verify","--bundle",str(bundle)],capture_output=True,text=True)
            self.assertEqual(invalid.returncode,1); self.assertIn("checksum mismatch",invalid.stdout)

if __name__ == "__main__": unittest.main()
