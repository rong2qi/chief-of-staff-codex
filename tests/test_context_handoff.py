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

def automation(automation_id="automation-1", target="thread-1", **overrides):
    value = {
        "id": automation_id, "name": "Unanswered Chief heartbeat", "kind": "heartbeat",
        "target_thread_id": target, "status": "ACTIVE",
        "schedule": {"hours": [9, 10, 22], "timezone": "local"},
        "prompt_sha256": "a" * 64, "notification_policy": "normal",
    }
    value.update(overrides)
    return value

def build_bundle(root, automations):
    source=root/"s.jsonl"; handoff=root/"h.md"; artifacts=root/"a.json"; inventory=root/"automations-input.json"; codex=root/"codex"
    session(source,850); handoff.write_text("# Handoff\nNext: verify.\n"); artifacts.write_text("{}\n"); inventory.write_text(json.dumps(automations))
    env=dict(os.environ,CODEX_HOME=str(codex))
    result=subprocess.run([sys.executable,str(SCRIPT),"build","--session",str(source),"--title","Task","--handoff",str(handoff),"--artifacts",str(artifacts),"--automations",str(inventory)],check=True,capture_output=True,text=True,env=env)
    return Path(json.loads(result.stdout)["bundle"])

def parity(bundle, root, live, *extra, successor="successor"):
    manifest=json.loads((bundle/"manifest.json").read_text()); inventory=json.loads((bundle/"automations.json").read_text())
    live.setdefault("observed_at","2026-08-26T00:00:00Z")
    live.setdefault("query_scope","predecessor_target_and_recorded_ids")
    live.setdefault("queried_predecessor_thread_id",manifest["predecessor_thread_id"])
    live.setdefault("queried_recorded_automation_ids",[item["id"] for item in inventory])
    live.setdefault("authorization",{"authorization_ref":"approval-example","rebind_allowed":True,"minimal_equivalent_if_missing_allowed":True})
    evidence=root/"live.json"; evidence.write_text(json.dumps(live))
    arguments=list(extra)
    if "--pin-parity-verified" in arguments:
        arguments.remove("--pin-parity-verified")
        pin=root/"pin.json"; pin.write_text(json.dumps({"evidence_kind":"live_list_threads","observed_at":"2026-08-26T00:01:00Z","successor_thread_id":successor,"pinned_thread_ids":[successor]}))
        arguments.extend(["--pin-evidence",str(pin)])
    return subprocess.run([sys.executable,str(SCRIPT),"verify-migration","--bundle",str(bundle),"--live-automations",str(evidence),"--successor-thread-id",successor,*arguments],capture_output=True,text=True)

class ContextHandoffTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual([MODULE.state(x) for x in (.74,.75,.84,.85,.95)], ["normal","checkpoint","checkpoint","rollover","emergency"])

    def test_ignores_total_and_rate_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"s.jsonl"; session(path,740)
            self.assertEqual(MODULE.inspect(path)["state"], "normal")

    def test_bundle_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/"s.jsonl"; handoff=root/"h.md"; artifacts=root/"a.json"; automations=root/"automations.json"; codex=root/"codex"
            session(source,850); handoff.write_text("# Handoff\nNext: verify.\n"); artifacts.write_text("{}\n"); automations.write_text("[]\n")
            env=dict(os.environ,CODEX_HOME=str(codex))
            result=subprocess.run([sys.executable,str(SCRIPT),"build","--session",str(source),"--title","Task","--handoff",str(handoff),"--artifacts",str(artifacts),"--automations",str(automations)],check=True,capture_output=True,text=True,env=env)
            bundle=Path(json.loads(result.stdout)["bundle"])
            self.assertEqual(json.loads((bundle/"automations.json").read_text()), [])
            valid=subprocess.run([sys.executable,str(SCRIPT),"verify","--bundle",str(bundle)],capture_output=True,text=True)
            self.assertEqual(valid.returncode,0,valid.stdout)
            (bundle/"handoff.md").write_text("tampered\n")
            invalid=subprocess.run([sys.executable,str(SCRIPT),"verify","--bundle",str(bundle)],capture_output=True,text=True)
            self.assertEqual(invalid.returncode,1); self.assertIn("checksum mismatch",invalid.stdout)

    def test_existing_automation_rebind_requires_live_exact_parity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); original=automation(); bundle=build_bundle(root,[original])
            live=automation(target="successor")
            valid=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[live],"absent_automation_ids":[]},"--pin-applicable","--pin-parity-verified")
            self.assertEqual(valid.returncode,0,valid.stdout)
            self.assertEqual(json.loads(valid.stdout)["status"],"MIGRATION_READY")
            for key, value in {
                "target_thread_id":"wrong", "status":"PAUSED", "schedule":{"hours":[9]},
                "prompt_sha256":"b"*64, "notification_policy":"muted",
            }.items():
                with self.subTest(key=key):
                    changed=automation(target="successor",**{key:value})
                    result=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[changed],"absent_automation_ids":[]},"--pin-applicable","--pin-parity-verified")
                    report=json.loads(result.stdout)
                    self.assertEqual(result.returncode,1)
                    self.assertEqual(report["status"],"MIGRATION_BLOCKED")
                    self.assertEqual(report["failure_record"],"automation_rebind_failed")
                    self.assertTrue(report["keep_predecessor_active_unarchived"])

    def test_missing_automation_allows_exactly_one_equivalent_with_live_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=build_bundle(root,[automation()])
            replacement=automation("automation-replacement",target="successor")
            valid=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[replacement],"absent_automation_ids":["automation-1"]})
            self.assertEqual(valid.returncode,0,valid.stdout)
            no_absence=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[replacement],"absent_automation_ids":[]})
            self.assertEqual(no_absence.returncode,1); self.assertIn("without live missing evidence",no_absence.stdout)
            duplicate=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[replacement,automation("automation-duplicate",target="successor")],"absent_automation_ids":["automation-1"]})
            self.assertEqual(duplicate.returncode,1); self.assertIn("duplicate ACTIVE automation duty",duplicate.stdout)

    def test_receipt_is_not_live_proof_and_pin_parity_also_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=build_bundle(root,[automation()])
            receipt=parity(bundle,root,{"evidence_kind":"update_receipt","automations":[automation(target="successor")],"absent_automation_ids":[]})
            self.assertEqual(receipt.returncode,1); self.assertIn("reference or receipt is not proof",receipt.stdout)
            missing_pin=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[automation(target="successor")],"absent_automation_ids":[]},"--pin-applicable")
            self.assertEqual(missing_pin.returncode,1); self.assertIn("applicable pin parity live evidence missing",missing_pin.stdout)
            self.assertTrue(json.loads(missing_pin.stdout)["automation_parity"])

    def test_anonymous_historical_repair_fixture_preserves_archived_predecessor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            fixture=json.loads((ROOT/"tests/fixtures/context-handoff/current-todo-remediation.json").read_text())
            source=fixture["source_automation"]; source["target_thread_id"]="thread-1"
            live=fixture["live_evidence"]; live["automations"][0]["target_thread_id"]="successor"
            bundle=build_bundle(root,[source])
            manifest=json.loads((bundle/"manifest.json").read_text())
            manifest["takeover"]={"authority_switched":True,"predecessor_active":False,"predecessor_archived":True}
            (bundle/"manifest.json").write_text(json.dumps(manifest))
            result=parity(bundle,root,live,"--historical-repair")
            self.assertEqual(result.returncode,0,result.stdout)
            self.assertEqual(json.loads(result.stdout)["status"],"REPAIR_VERIFIED")
            manifest=json.loads((bundle/"manifest.json").read_text())
            self.assertEqual(manifest["takeover"],{"authority_switched":True,"predecessor_active":False,"predecessor_archived":True})

    def test_no_binding_requires_explicit_empty_inventory_and_live_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=build_bundle(root,[])
            result=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[],"absent_automation_ids":[]})
            self.assertEqual(result.returncode,0,result.stdout)
            manifest=json.loads((bundle/"manifest.json").read_text())
            self.assertEqual(manifest["parity"]["automation"],"not_applicable")

    def test_replacement_requires_predecessor_binding_and_existing_authorization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=build_bundle(root,[automation(target="unrelated-thread")])
            replacement=automation("replacement",target="successor")
            result=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[replacement],"absent_automation_ids":["automation-1"]})
            self.assertEqual(result.returncode,1); self.assertIn("not bound to the predecessor",result.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=build_bundle(root,[automation()])
            replacement=automation("replacement",target="successor")
            live={"evidence_kind":"live_automation_view","automations":[replacement],"absent_automation_ids":["automation-1"],"authorization":{"authorization_ref":None,"rebind_allowed":True,"minimal_equivalent_if_missing_allowed":False}}
            result=parity(bundle,root,live)
            self.assertEqual(result.returncode,1); self.assertIn("replacement lacks existing authorization",result.stdout)

    def test_unknown_bundle_schema_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=build_bundle(root,[])
            manifest=json.loads((bundle/"manifest.json").read_text()); manifest["schema_version"]=999; (bundle/"manifest.json").write_text(json.dumps(manifest))
            result=subprocess.run([sys.executable,str(SCRIPT),"verify","--bundle",str(bundle)],capture_output=True,text=True)
            self.assertEqual(result.returncode,1); self.assertIn("schema_version must be 1 or 2",result.stdout)

    def test_schema_v1_is_checksum_valid_but_migration_unassessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=build_bundle(root,[])
            manifest=json.loads((bundle/"manifest.json").read_text()); manifest["schema_version"]=1; (bundle/"manifest.json").write_text(json.dumps(manifest))
            result=subprocess.run([sys.executable,str(SCRIPT),"verify","--bundle",str(bundle)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout)
            self.assertEqual(json.loads(result.stdout)["migration_eligibility"],"legacy_unassessed")

    def test_intentional_split_schedules_are_distinct_duties(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            morning=automation("morning",schedule={"hours":[9],"timezone":"local"})
            evening=automation("evening",schedule={"hours":[22],"timezone":"local"})
            bundle=build_bundle(root,[morning,evening])
            morning_live=dict(morning,target_thread_id="successor")
            evening_live=dict(evening,target_thread_id="successor")
            result=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[morning_live,evening_live],"absent_automation_ids":[]})
            self.assertEqual(result.returncode,0,result.stdout)

    def test_successor_binding_cannot_be_rewritten_by_failed_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=build_bundle(root,[automation()])
            first=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[automation(target="successor")],"absent_automation_ids":[]})
            self.assertEqual(first.returncode,0,first.stdout)
            for _ in range(2):
                attempted=parity(bundle,root,{"evidence_kind":"live_automation_view","automations":[automation(target="successor-b")],"absent_automation_ids":[]},successor="successor-b")
                self.assertEqual(attempted.returncode,1,attempted.stdout)
                self.assertIn("successor thread ID mismatch",attempted.stdout)
                self.assertEqual(json.loads((bundle/"manifest.json").read_text())["successor_thread_id"],"successor")

    def test_failed_historical_repair_preserves_archived_predecessor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); bundle=build_bundle(root,[automation()])
            manifest=json.loads((bundle/"manifest.json").read_text())
            archived={"authority_switched":True,"predecessor_active":False,"predecessor_archived":True}
            manifest["takeover"]=archived; (bundle/"manifest.json").write_text(json.dumps(manifest))
            changed=automation(target="successor",schedule={"hours":[11],"timezone":"local"})
            live={"evidence_kind":"live_automation_view","historical_state":{"predecessor":"archived","successor":"active","repair":"without_unarchive_delete_or_duplicate"},"automations":[changed],"absent_automation_ids":[]}
            result=parity(bundle,root,live,"--historical-repair")
            self.assertEqual(result.returncode,1,result.stdout)
            self.assertFalse(json.loads(result.stdout)["keep_predecessor_active_unarchived"])
            self.assertEqual(json.loads((bundle/"manifest.json").read_text())["takeover"],archived)

if __name__ == "__main__": unittest.main()
