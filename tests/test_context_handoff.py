import contextlib, importlib.util, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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

def capture_args(root, used=850, boundary="boundary-1"):
    source=root/"s.jsonl"; handoff=root/"h.md"; artifacts=root/"a.json"; inventory=root/"automations-input.json"; codex=root/"codex"
    session(source,used); handoff.write_text("# Handoff\nNext: verify.\n"); artifacts.write_text("{}\n"); inventory.write_text("[]\n")
    return SimpleNamespace(session=source,title="Task",handoff=handoff,artifacts=artifacts,automations=inventory,
                           project_root=None,lineage_id=None,safe_boundary_id=boundary,resume_after_diagnosis=False), codex

def run_capture(args, codex):
    output=io.StringIO()
    with mock.patch.dict(os.environ,{"CODEX_HOME":str(codex)}), contextlib.redirect_stdout(output):
        code=MODULE.capture(args)
    return code,json.loads(output.getvalue())

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

    def test_latest_zero_sample_does_not_replace_newest_usable_nonzero_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"s.jsonl"; session(path,800)
            zero={"timestamp":"2026-08-23T00:02:00Z","type":"event_msg","payload":{"type":"token_count","info":{"last_token_usage":{"input_tokens":0},"model_context_window":1000}}}
            path.write_text(path.read_text()+json.dumps(zero)+"\n")
            sample=MODULE.inspect(path)
            self.assertEqual(sample["input_tokens"],800)
            self.assertEqual(sample["state"],"checkpoint")

    def test_capture_below_threshold_cancels_without_bundle_or_successor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); args,codex=capture_args(root,740)
            code,result=run_capture(args,codex)
            self.assertEqual(code,0)
            self.assertEqual(result["status"],"CHECKPOINT_CANCELLED")
            self.assertFalse(result["successor_created"])
            self.assertFalse((codex/"context-migrations").exists())

    def test_capture_is_limited_to_one_build_verify_per_safe_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); args,codex=capture_args(root)
            first_code,first=run_capture(args,codex)
            second_code,second=run_capture(args,codex)
            self.assertEqual(first_code,0); self.assertEqual(first["status"],"CHECKPOINT_READY")
            self.assertEqual(second_code,0); self.assertEqual(second["status"],"SAFE_BOUNDARY_ATTEMPT_LIMIT")
            lineage=codex/"context-migrations/thread-1"
            self.assertEqual([p.name for p in lineage.iterdir() if p.is_dir() and p.name.isdigit()],["0001"])
            self.assertIsNone(json.loads((lineage/"0001/manifest.json").read_text())["successor_thread_id"])

    def test_session_change_uses_new_number_at_next_safe_boundary_without_operator_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); args,codex=capture_args(root)
            original=MODULE.build_once
            def changing_build(*values):
                bundle,manifest=original(*values)
                args.session.write_text(args.session.read_text()+"{}\n")
                return bundle,manifest
            with mock.patch.object(MODULE,"build_once",side_effect=changing_build):
                first_code,first=run_capture(args,codex)
            self.assertEqual(first_code,3)
            self.assertEqual(first["status"],"TRANSIENT_CAPTURE_RETRY_NEXT_SAFE_BOUNDARY")
            self.assertFalse(first["operator_attention_required"])
            old_manifest=(Path(first["bundle"])/"manifest.json").read_bytes()
            session(args.session,850); args.safe_boundary_id="boundary-2"
            second_code,second=run_capture(args,codex)
            self.assertEqual(second_code,0); self.assertEqual(second["migration_number"],2)
            self.assertEqual((Path(first["bundle"])/"manifest.json").read_bytes(),old_manifest)
            self.assertFalse(second["successor_created"])

    def test_existing_target_number_is_skipped_without_overwrite_or_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/"s.jsonl"; handoff=root/"h.md"; artifacts=root/"a.json"; inventory=root/"automations.json"; codex=root/"codex"
            session(source,850); handoff.write_text("handoff\n"); artifacts.write_text("{}\n"); inventory.write_text("[]\n")
            command=[sys.executable,str(SCRIPT),"build","--session",str(source),"--title","Task","--handoff",str(handoff),"--artifacts",str(artifacts),"--automations",str(inventory),"--migration-number","1"]
            env=dict(os.environ,CODEX_HOME=str(codex))
            first=subprocess.run(command,check=True,capture_output=True,text=True,env=env); first_bundle=Path(json.loads(first.stdout)["bundle"])
            first_hash=MODULE.digest(first_bundle/"manifest.json")
            second=subprocess.run(command,check=True,capture_output=True,text=True,env=env); report=json.loads(second.stdout)
            self.assertEqual(report["manifest"]["migration_number"],2)
            self.assertTrue(report["number_collision_avoided"])
            self.assertEqual(MODULE.digest(first_bundle/"manifest.json"),first_hash)

    def test_regular_file_numeric_slot_is_occupied_and_capture_advances(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); args,codex=capture_args(root)
            lineage=codex/"context-migrations/thread-1"; lineage.mkdir(parents=True)
            occupied=lineage/"0001"; occupied.write_text("preserve exactly\n")
            code,result=run_capture(args,codex)
            self.assertEqual(code,0); self.assertEqual(result["migration_number"],2)
            self.assertEqual(occupied.read_text(),"preserve exactly\n")
            self.assertTrue((lineage/"0002/manifest.json").is_file())

    def test_repeated_transient_failures_enter_chief_owned_diagnosis_without_user_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); args,codex=capture_args(root); original=MODULE.build_once
            def changing_build(*values):
                bundle,manifest=original(*values)
                args.session.write_text(args.session.read_text()+"{}\n")
                return bundle,manifest
            with mock.patch.object(MODULE,"build_once",side_effect=changing_build):
                reports=[]
                for index in range(3):
                    session(args.session,850); args.safe_boundary_id=f"boundary-{index}"
                    _,report=run_capture(args,codex); reports.append(report)
            self.assertEqual(reports[-1]["status"],"TRANSIENT_CAPTURE_DIAGNOSIS_REQUIRED")
            self.assertEqual(reports[-1]["action"],"chief_owned_read_only_diagnosis_and_backoff")
            self.assertFalse(reports[-1]["operator_attention_required"])
            lineage=codex/"context-migrations/thread-1"
            before=sorted(p.name for p in lineage.iterdir() if p.is_dir() and p.name.isdigit())
            session(args.session,850); args.safe_boundary_id="boundary-after-threshold"
            code,diagnosis=run_capture(args,codex)
            after=sorted(p.name for p in lineage.iterdir() if p.is_dir() and p.name.isdigit())
            self.assertEqual(code,0); self.assertEqual(diagnosis["status"],"TRANSIENT_CAPTURE_DIAGNOSIS_REQUIRED")
            self.assertEqual(after,before)

    def test_nontransient_verify_error_stops_without_successor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); args,codex=capture_args(root)
            blocked={"bundle":"fixture","valid":False,"migration_eligibility":"invalid","errors":["checksum mismatch: handoff.md"]}
            with mock.patch.object(MODULE,"verify_bundle",return_value=(blocked,1)):
                code,result=run_capture(args,codex)
            self.assertEqual(code,1); self.assertEqual(result["status"],"CAPTURE_BLOCKED")
            self.assertFalse(result["successor_created"])
            self.assertFalse(result["operator_attention_required"])
            second_code,second=run_capture(args,codex)
            self.assertEqual(second_code,0); self.assertEqual(second["status"],"SAFE_BOUNDARY_ATTEMPT_LIMIT")

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
