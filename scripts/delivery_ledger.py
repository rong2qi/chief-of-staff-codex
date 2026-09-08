#!/usr/bin/env python3
"""Journal-authoritative delivery ledger; observed files, never caller hashes, advance state."""
from __future__ import annotations
import argparse, fcntl, hashlib, json, os, tempfile
from pathlib import Path
from typing import Any
try:
    from . import continuous_execution
except ImportError:  # pragma: no cover - direct CLI import path
    import continuous_execution
try:
    from . import retry_policy
except ImportError:
    import retry_policy

EVENTS = {"ARTIFACT_FROZEN","SEND_ATTEMPTED","TRANSPORT_ACCEPTED","SEND_FAILED","RECEIVER_ACK_OBSERVED","REVIEW_DECIDED","NEXT_STEP_DISPATCHED","NEXT_STEP_ACCEPTED","NO_NEXT_STEP_DECIDED","BLOCKED","COMPLETION_OBSERVATION","COMPLETED_EMPTY","RETURN_ACTION_CONSUMED","RETURN_NATIVE_INTENT_PREPARED","RETURN_NATIVE_DISPATCH_OBSERVED"}
TERMINAL = {"blocked","completed_empty","no_next_step","failed_candidate","native_execution_dispatched"}
HEX = set("0123456789abcdef")
class LedgerError(ValueError): pass
def _canonical(x: object) -> bytes: return (json.dumps(x, sort_keys=True, separators=(",",":"), ensure_ascii=False)+"\n").encode()
def _sha(x: bytes) -> str: return hashlib.sha256(x).hexdigest()
def _hash(x: object) -> bool: return isinstance(x,str) and len(x)==64 and set(x)<=HEX
def _atomic(path: Path, value: object) -> None:
    fd, raw=tempfile.mkstemp(prefix=".ledger-",dir=path.parent); staged=Path(raw)
    try:
        with os.fdopen(fd,"wb") as f: f.write(_canonical(value)); f.flush(); os.fsync(f.fileno())
        os.replace(staged,path)
    finally:
        if staged.exists(): staged.unlink()

class Ledger:
    def __init__(self, root: Path):
        raw=Path(root).absolute(); self._lexical_safe(raw); raw.mkdir(parents=True,exist_ok=True)
        if raw.is_symlink() or not raw.is_dir(): raise LedgerError("ledger root must be a real directory")
        self.root=raw.resolve(strict=True); self.journal=self.root/"events.jsonl"; self.snapshot_path=self.root/"snapshot.json"; self.lock_path=self.root/".lock"
        self._validate_fixed_topology()
    @staticmethod
    def _lexical_safe(path:Path)->None:
        cursor=path
        while cursor.parent!=cursor:
            if cursor.is_symlink() and cursor not in {Path("/tmp"),Path("/var")}:
                raise LedgerError("ledger root has a symlinked ancestor")
            cursor=cursor.parent
    def _validate_fixed_topology(self)->None:
        for path in (self.journal,self.snapshot_path,self.lock_path):
            if path.is_symlink():
                raise LedgerError("ledger topology contains an unsafe fixed path")
            if not path.exists():
                continue
            if not path.is_file():
                raise LedgerError("ledger topology contains an unsafe fixed path")
            if path.stat().st_nlink != 1:
                raise LedgerError("ledger topology contains a hardlink alias")
    @staticmethod
    def _empty() -> dict[str,Any]: return {"schema":"CHIEF_DELIVERY_LEDGER_V1","reports":{},"event_ids":{}}
    def _evidence_file(self, raw: object) -> Path:
        if not isinstance(raw,str) or not raw: raise LedgerError("evidence_path is required")
        p=Path(raw)
        if not p.is_absolute() or p.is_symlink() or not p.is_file() or p.stat().st_nlink!=1: raise LedgerError("evidence_path must be an absolute non-symlink regular file")
        try: resolved=p.resolve(strict=True); relative=resolved.relative_to(self.root)
        except (OSError,ValueError) as exc: raise LedgerError("evidence_path escapes the ledger surface") from exc
        cursor=self.root
        for part in relative.parts:
            cursor=cursor/part
            if cursor.is_symlink(): raise LedgerError("evidence_path has a symlinked ancestor")
        return resolved
    def _evidence(self,payload:dict[str,Any],kind:str,hash_key:str,identity:dict[str,Any]) -> dict[str,Any]:
        path=self._evidence_file(payload.get("evidence_path")); raw=path.read_bytes()
        if payload.get("evidence_sha256") != _sha(raw): raise LedgerError("evidence hash does not match retained bytes")
        try: v=json.loads(raw)
        except (UnicodeDecodeError,json.JSONDecodeError) as exc: raise LedgerError("evidence must be readable JSON") from exc
        if not isinstance(v,dict) or v.get("schema")!="CHIEF_DELIVERY_EVIDENCE_V1" or v.get("kind")!=kind or v.get("identity")!=identity or not isinstance(v.get("observation"),dict): raise LedgerError("evidence kind or identity is invalid")
        if payload.get(hash_key)!=_sha(_canonical(v["observation"])): raise LedgerError("claimed observation hash does not match evidence")
        return v["observation"]
    @staticmethod
    def _report(p:dict[str,Any]) -> tuple[str,dict[str,Any]]:
        ks=("report_id","source_task_id","target_task_id","project_id","payload_sha256")
        if any(not isinstance(p.get(k),str) or not p[k] for k in ks) or not _hash(p.get("payload_sha256")): raise LedgerError("report identity and payload SHA-256 are required")
        if p["source_task_id"]==p["target_task_id"]: raise LedgerError("source and target task must differ")
        return p["report_id"],{k:p[k] for k in ks}
    def _load(self) -> dict[str,Any]:
        # Never seed from snapshot: it is a derived cache and may be forged/stale.
        self._validate_fixed_topology()
        s=self._empty()
        if not self.journal.exists(): return s
        if self.journal.is_symlink() or not self.journal.is_file(): raise LedgerError("journal is unsafe")
        try: lines=self.journal.read_text(encoding="utf-8").splitlines()
        except OSError as exc: raise LedgerError("journal unreadable") from exc
        for raw in lines:
            try: ev=json.loads(raw)
            except json.JSONDecodeError as exc: raise LedgerError("journal contains invalid JSON") from exc
            if not isinstance(ev,dict) or set(ev)!={"event_id","kind","payload"} or not isinstance(ev["event_id"],str) or not isinstance(ev["payload"],dict): raise LedgerError("journal event schema is invalid")
            digest=_sha(_canonical(ev)); old=s["event_ids"].get(ev["event_id"])
            if old is not None:
                if old!=digest: raise LedgerError("journal reuses an event ID with different bytes")
                continue
            self._apply(s,ev["kind"],ev["payload"],ev["event_id"]); s["event_ids"][ev["event_id"]]=digest
        return s
    def snapshot(self)->dict[str,Any]: return self._load()
    def _apply(self,s:dict[str,Any],kind:str,p:dict[str,Any],event_id:str)->None:
        if kind not in EVENTS: raise LedgerError("unsupported event")
        rid,identity=self._report(p); reports=s["reports"]; r=reports.get(rid)
        if r is None:
            refs=p.get("artifact_refs")
            if kind!="ARTIFACT_FROZEN" or not isinstance(refs,list) or not refs or not all(isinstance(x,str) and x for x in refs): raise LedgerError("first event must freeze non-empty artifact references")
            payload=None
            payload_ref=p.get("continuous_payload_ref")
            if payload_ref is not None:
                fd=retry_policy._open_project_directory(self.root)
                try: payload=retry_policy._read_retained_json(fd,payload_ref,identity["payload_sha256"],"continuous payload")
                finally: os.close(fd)
                if not {"work_id","package_id","candidate_sha256","kind","source_task_id","target_task_id","project_id"}.issubset(payload) or any(payload.get(key)!=identity.get(key) for key in ("source_task_id","target_task_id","project_id")):
                    raise LedgerError("continuous payload binding is invalid")
            reports[rid]={**identity,"artifact_refs":refs,"continuous_payload":payload,"state":"artifact_frozen","attempts":{},"events":[event_id]}; return
        if {k:r[k] for k in identity}!=identity: raise LedgerError("same report ID has conflicting identity")
        if r["state"] in TERMINAL: raise LedgerError("terminal report cannot be replayed")
        if kind=="ARTIFACT_FROZEN": raise LedgerError("duplicate artifact requires same event ID")
        evidence_identity={**identity,"attempt_id":p.get("attempt_id")}
        if kind in {"TRANSPORT_ACCEPTED","RECEIVER_ACK_OBSERVED","REVIEW_DECIDED","NEXT_STEP_DISPATCHED","NEXT_STEP_ACCEPTED"} and (not isinstance(p.get("attempt_id"),str) or not p["attempt_id"]):
            raise LedgerError("observed transition must bind a stable send attempt")
        if kind == "RETURN_NATIVE_INTENT_PREPARED":
            required = (
                "action_id",
                "return_id",
                "return_kind",
                "work_id",
                "package_id",
                "candidate_sha256",
                "return_to_task_id",
                "native_root_id",
                "coordinator_task_id",
                "return_receipt_ref",
                "return_receipt_sha256",
                "current_task_ref",
                "current_task_sha256",
                "current_task_observation_id",
                "expected_head",
            )
            if (
                r.get("state") != "reviewed"
                or r.get("review_decision") != "accepted"
                or any(not isinstance(p.get(key), str) or not p[key] for key in required)
                or p.get("return_kind") not in {"recovery", "test_pass", "approval", "resource_recovered"}
                or not _hash(p.get("candidate_sha256"))
                or not _hash(p.get("return_receipt_sha256"))
                or not _hash(p.get("current_task_sha256"))
                or len(p.get("expected_head", "")) != 40
                or bool(set(p.get("expected_head", "")) - HEX)
            ):
                raise LedgerError(
                    "native return intent requires one reviewed recovery report and exact identity"
                )

            retained = r.get("continuous_payload")
            if (
                not isinstance(retained, dict)
                or retained.get("report_id") != rid
                or retained.get("return_id") != p["return_id"]
                or retained.get("kind") != p["return_kind"]
                or retained.get("work_id") != p["work_id"]
                or retained.get("package_id") != p["package_id"]
                or retained.get("candidate_sha256") != p["candidate_sha256"]
                or retained.get("source_task_id") != r["source_task_id"]
                or retained.get("target_task_id") != r["target_task_id"]
                or retained.get("return_to_task_id") != p["return_to_task_id"]
                or retained.get("native_receipt_ref") != p["return_receipt_ref"]
                or retained.get("native_receipt_sha256") != p["return_receipt_sha256"]
            ):
                raise LedgerError("native return intent conflicts with retained report payload")

            intent = {key: p[key] for key in required}
            if r.get("native_execution_intent") not in (None, intent):
                raise LedgerError("native return intent conflicts with its persisted identity")
            r["native_execution_intent"] = intent
            r["state"] = "native_execution_intent_pending"

        elif kind == "RETURN_NATIVE_DISPATCH_OBSERVED":
            required = (
                "action_id",
                "return_id",
                "work_id",
                "package_id",
                "candidate_sha256",
                "dispatch_evidence_ref",
                "dispatch_evidence_sha256",
                "dispatch_observation",
            )
            if (
                r.get("state") != "native_execution_intent_pending"
                or any(key not in p for key in required)
                or not _hash(p.get("dispatch_evidence_sha256"))
                or not isinstance(p.get("dispatch_observation"), dict)
            ):
                raise LedgerError("native dispatch receipt requires one pending native intent")

            intent = r.get("native_execution_intent")
            if not isinstance(intent, dict):
                raise LedgerError("pending native return intent is missing")
            for key in ("action_id", "return_id", "work_id", "package_id", "candidate_sha256"):
                if p.get(key) != intent.get(key):
                    raise LedgerError("native dispatch receipt conflicts with pending action")

            observed = p["dispatch_observation"]
            dispatch_keys = {
                "schema",
                "kind",
                "observation_id",
                "authority_kind",
                "native_root_id",
                "coordinator_task_id",
                "report_id",
                "return_id",
                "action_id",
                "work_id",
                "package_id",
                "candidate_sha256",
                "project",
                "source_task_id",
                "target_task_id",
                "current_task_observation_id",
                "expected_head",
                "status",
                "dispatch_tool",
                "native_event_id",
            }
            if (
                set(observed) != dispatch_keys
                or observed.get("schema") != "CHIEF_NATIVE_RETURN_DISPATCH_RECEIPT_V1"
                or observed.get("kind") != f"{intent['return_kind']}_dispatch"
                or observed.get("authority_kind") != "native_coordinator_observation"
                or observed.get("status") != "accepted"
                or observed.get("report_id") != rid
                or observed.get("return_id") != intent["return_id"]
                or observed.get("action_id") != intent["action_id"]
                or observed.get("work_id") != intent["work_id"]
                or observed.get("package_id") != intent["package_id"]
                or observed.get("candidate_sha256") != intent["candidate_sha256"]
                or observed.get("native_root_id") != intent["native_root_id"]
                or observed.get("coordinator_task_id") != intent["coordinator_task_id"]
                or observed.get("source_task_id") != intent["coordinator_task_id"]
                or observed.get("target_task_id") != intent["return_to_task_id"]
                or observed.get("current_task_observation_id")
                != intent["current_task_observation_id"]
                or observed.get("expected_head") != intent["expected_head"]
                or any(
                    not isinstance(observed.get(key), str) or not observed[key]
                    for key in ("observation_id", "dispatch_tool", "native_event_id")
                )
            ):
                raise LedgerError("native dispatch receipt does not bind the pending action")

            r["native_execution_dispatch"] = {
                "dispatch_evidence_ref": p["dispatch_evidence_ref"],
                "dispatch_evidence_sha256": p["dispatch_evidence_sha256"],
                "observation_id": observed["observation_id"],
                "native_event_id": observed["native_event_id"],
                "dispatch_tool": observed["dispatch_tool"],
            }
            r["state"] = "native_execution_dispatched"
        if kind=="RETURN_ACTION_CONSUMED":
            required=("action_id","return_id","work_id","package_id","candidate_sha256")
            if r.get("state")!="reviewed" or any(not isinstance(p.get(key),str) or not p[key] for key in required): raise LedgerError("return action requires reviewed report and stable identity")
            intent={key:p[key] for key in required}
            if r.get("execution_intent") not in (None,intent): raise LedgerError("return action conflicts")
            r["execution_intent"]=intent; r["state"]="execution_intent_pending"
        elif kind=="SEND_ATTEMPTED":
            a=p.get("attempt_id")
            if not isinstance(a,str) or not a or a in r["attempts"]: raise LedgerError("send attempt needs a fresh stable attempt ID")
            r["attempts"][a]={"status":"attempted"}; r["state"]="send_attempted"
        elif kind=="TRANSPORT_ACCEPTED":
            a,tool=p.get("attempt_id"),p.get("tool_name")
            if not isinstance(a,str) or not a or not isinstance(tool,str) or not tool: raise LedgerError("accepted transport needs attempt ID and exact tool")
            o=self._evidence(p,"transport_accepted","raw_receipt_sha256",evidence_identity)
            if o.get("status")!="accepted" or o.get("attempt_id")!=a or o.get("tool_name")!=tool: raise LedgerError("transport evidence is not accepted for this attempt/tool")
            old=r["attempts"].get(a); accepted={"status":"accepted","tool_name":tool,"raw_receipt_sha256":p["raw_receipt_sha256"],"evidence_path":str(self._evidence_file(p["evidence_path"]))}
            if old is None: raise LedgerError("accepted transport must follow attempt")
            if old not in ({"status":"attempted"},accepted): raise LedgerError("attempt receipt conflicts")
            r["attempts"][a]=accepted; r["state"]="sent_unacked"
        elif kind=="SEND_FAILED":
            if not isinstance(p.get("reason"),str) or not p["reason"]: raise LedgerError("send failure needs reason")
            r["state"]="send_failed"; r["blocked_reason"]=p["reason"]
        elif kind=="RECEIVER_ACK_OBSERVED":
            attempt=p.get("attempt_id")
            if r["attempts"].get(attempt,{}).get("status")!="accepted": raise LedgerError("receiver ACK must bind its exact accepted transport attempt")
            o=self._evidence(p,"receiver_ack","raw_observation_sha256",evidence_identity)
            keys=("ack_task_id","observed_by_task_id","observation_kind","receiver_event_id")
            # The target authors the ACK; the durable source Chief may be the
            # observer/ingest owner after native delivery.  Do not conflate
            # author with observer or require a fabricated provider ID.
            if p.get("ack_task_id")!=r["target_task_id"] or p.get("observed_by_task_id")!=r["source_task_id"] or p.get("observation_kind")!="receiver_stream" or not isinstance(p.get("receiver_event_id"),str) or not p["receiver_event_id"] or any(o.get(k)!=p.get(k) for k in keys): raise LedgerError("ACK must retain target-authored evidence observed by the source Chief")
            r["state"]="received_unprocessed"; r["ack_receipt_sha256"]=p["raw_observation_sha256"]; r["ack_attempt_id"]=attempt
        elif kind=="REVIEW_DECIDED":
            o=self._evidence(p,"review_decision","review_receipt_sha256",evidence_identity)
            if r["state"]!="received_unprocessed" or p.get("attempt_id")!=r.get("ack_attempt_id") or p.get("decision") not in {"accepted","rejected"} or p.get("reviewer_task_id")!=r["target_task_id"] or o.get("decision")!=p["decision"] or o.get("reviewer_task_id")!=p["reviewer_task_id"]: raise LedgerError("review requires matching acknowledged-attempt evidence")
            r["state"]="reviewed" if p["decision"]=="accepted" else "failed_candidate"; r["review_decision"]=p["decision"]
        elif kind=="NEXT_STEP_DISPATCHED":
            a,t=p.get("next_action_id"),p.get("next_target_task_id"); o=self._evidence(p,"next_dispatch","dispatch_receipt_sha256",evidence_identity)
            keys=("next_action_id","next_target_task_id","next_target_status","next_target_scope")
            if r["state"]!="reviewed" or p.get("attempt_id")!=r.get("ack_attempt_id") or not isinstance(a,str) or not a or not isinstance(t,str) or not t or p.get("next_target_status")!="active" or not isinstance(p.get("next_target_scope"),str) or not p["next_target_scope"] or o.get("status")!="accepted" or any(o.get(k)!=p.get(k) for k in keys): raise LedgerError("next dispatch needs a matching accepted active-target evidence")
            r.update({"state":"next_step_dispatched","next_action_id":a,"next_target_task_id":t,"next_target_scope":p["next_target_scope"]})
        elif kind=="NEXT_STEP_ACCEPTED":
            o=self._evidence(p,"next_acceptance","next_ack_receipt_sha256",evidence_identity)
            if r["state"]!="next_step_dispatched" or p.get("attempt_id")!=r.get("ack_attempt_id") or o.get("status")!="accepted" or o.get("next_action_id")!=r["next_action_id"] or o.get("next_target_task_id")!=r["next_target_task_id"]: raise LedgerError("next acceptance evidence invalid")
            r["state"]="continued"
        elif kind=="COMPLETION_OBSERVATION":
            if p.get("items")!=[] or p.get("result_artifact_confirmed") is not False: raise LedgerError("observation must be incomplete summary")
            r["state"]="completed_unobserved"; r["observation_cursor"]=p.get("observation_cursor")
        elif kind=="COMPLETED_EMPTY":
            o=self._evidence(p,"completion_absence","absence_evidence_sha256",evidence_identity)
            if r["state"]!="completed_unobserved" or r.get("review_decision")!="accepted" or p.get("attempt_id")!=r.get("ack_attempt_id") or p.get("absence_verified") is not True or o.get("status")!="absent" or o.get("absence_verified") is not True: raise LedgerError("empty completion requires reviewed retained absence evidence")
            r["state"]="completed_empty"
        elif kind=="NO_NEXT_STEP_DECIDED":
            o=self._evidence(p,"no_next_step","decision_receipt_sha256",evidence_identity)
            if r["state"]!="reviewed" or p.get("attempt_id")!=r.get("ack_attempt_id") or o.get("decision")!="no_next_step" or o.get("reviewer_task_id")!=r["target_task_id"]: raise LedgerError("no-next needs retained receiver final-decision evidence")
            r["state"]="no_next_step"
        elif kind=="BLOCKED":
            if not isinstance(p.get("blocked_reason"),str) or not p["blocked_reason"]: raise LedgerError("block requires reason")
            r["state"]="blocked";r["blocked_reason"]=p["blocked_reason"]
        r["events"].append(event_id)
    def ingest(self,kind:str,payload:dict[str,Any])->None:
        if kind not in EVENTS or not isinstance(payload,dict): raise LedgerError("invalid event")
        eid=payload.get("event_id") or hashlib.sha256(kind.encode()+_canonical(payload)).hexdigest()[:32]
        if not isinstance(eid,str) or not eid: raise LedgerError("event ID invalid")
        ev={"event_id":eid,"kind":kind,"payload":payload}
        self._validate_fixed_topology()
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX); s=self._load(); d=_sha(_canonical(ev)); old=s["event_ids"].get(eid)
            if old is not None:
                if old!=d: raise LedgerError("same event ID conflicts")
                return False
            self._apply(s,kind,payload,eid);s["event_ids"][eid]=d
            with self.journal.open("ab") as f:f.write(_canonical(ev));f.flush();os.fsync(f.fileno())
            _atomic(self.snapshot_path,s); return True
    def reconcile(self)->dict[str,list[dict[str,Any]]]:
        actions={"sent_unacked":"OBSERVE_RECEIVER_ACK","received_unprocessed":"REVIEW_RECEIVED_REPORT","reviewed":"DISPATCH_NEXT_STEP_OR_RECORD_FINAL_DECISION","completed_unobserved":"OBSERVATION_GAP"}; s=self._load(); intents=[]
        for rid in sorted(s["reports"]):
            r=s["reports"][rid]; action=actions.get(r["state"])
            if action:intents.append({"report_id":rid,"project_id":r["project_id"],"source_task_id":r["source_task_id"],"target_task_id":r["target_task_id"],"payload_sha256":r["payload_sha256"],"phase":r["state"],"next_required_action":action,"attempts":r["attempts"],"observation_cursor":r.get("observation_cursor")})
        return {"intents":intents}
    def reconcile_execution(self, execution_state: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
        """Bind current-work return intents to retained ledger receipts.

        A caller cannot make a return actionable merely by inventing a return
        ID: its ledger report must be receiver-reviewed.  Existing
        ``NEXT_STEP_DISPATCHED`` state is the persistent no-replay marker.
        This method returns an intent only and does not append a dispatch.
        """
        if not isinstance(execution_state, dict):
            raise LedgerError("execution state must be an object")
        snapshot = self._load()
        returns = execution_state.get("returns", [])
        if not isinstance(returns, list):
            raise LedgerError("execution returns must be an array")
        accepted: list[dict[str, Any]] = []
        dispatched = list(execution_state.get("dispatched_return_ids", []))
        if not all(isinstance(value, str) for value in dispatched):
            raise LedgerError("execution dispatched_return_ids must be strings")
        for returned in returns:
            if not isinstance(returned, dict):
                continue
            report_id = returned.get("ledger_report_id")
            report = snapshot["reports"].get(report_id) if isinstance(report_id, str) else None
            if not isinstance(report, dict):
                continue
            payload = report.get("continuous_payload")
            if not isinstance(payload, dict):
                continue
            if returned.get("ledger_report_id") == report_id and any(returned.get(key) != payload.get(key) for key in ("work_id", "package_id", "candidate_sha256", "kind", "source_task_id", "target_task_id")):
                raise LedgerError("continuous return conflicts with retained report payload")
            # A receiver-reviewed report is only evidence for this exact local
            # work packet.  Do not let another project's review be wrapped in
            # a caller-provided return object.
            if (
                report.get("project_id") != package.get("project", {}).get("project_id")
                or report.get("source_task_id") != package.get("writer_task_id")
                or returned.get("source_task_id") != report.get("source_task_id")
                or returned.get("target_task_id") != report.get("target_task_id")
                or returned.get("project_id") != report.get("project_id")
                or returned.get("package_id") != package.get("package_id")
                or returned.get("candidate_sha256") not in {None, package.get("candidate_sha256")}
                or returned.get("kind") not in continuous_execution.RETURN_KINDS
                or any(returned.get(key) != payload.get(key) for key in ("work_id", "package_id", "candidate_sha256", "kind", "source_task_id", "target_task_id"))
            ):
                continue
            if returned.get("work_id") != execution_state.get("work_id"):
                continue
            if report.get("state") in {"next_step_dispatched", "continued", "no_next_step", "failed_candidate"}:
                if isinstance(returned.get("return_id"), str) and returned["return_id"] not in dispatched:
                    dispatched.append(returned["return_id"])
                continue
            if report.get("state") != "reviewed" or report.get("review_decision") != "accepted":
                continue
            accepted.append(returned)
        bound = dict(execution_state)
        bound["returns"] = accepted
        bound["dispatched_return_ids"] = dispatched
        try:
            result=continuous_execution.reconcile_execution(bound, package)
            if result.get("next_action")=="CONTINUE_RETURNED_WORK":
                returned=next(item for item in accepted if item.get("return_id")==result.get("return_id"))
                action_id=_sha(_canonical({"report_id":returned["ledger_report_id"],"work_id":returned["work_id"],"package_id":returned["package_id"],"candidate_sha256":returned.get("candidate_sha256"),"return_id":returned["return_id"]}))
                payload={"report_id":returned["ledger_report_id"],"source_task_id":returned["source_task_id"],"target_task_id":returned["target_task_id"],"project_id":returned["project_id"],"payload_sha256":snapshot["reports"][returned["ledger_report_id"]]["payload_sha256"],"action_id":action_id,"return_id":returned["return_id"],"work_id":returned["work_id"],"package_id":returned["package_id"],"candidate_sha256":returned.get("candidate_sha256")}
                if not self.ingest("RETURN_ACTION_CONSUMED",payload): return {**result,"next_action":"NO_ACTION"}
            return result
        except continuous_execution.ContinuousExecutionError as exc:
            raise LedgerError(str(exc)) from exc
    def reconcile_native_execution(
        self,
        *,
        project: Path,
        execution_package_id: str,
        execution_work_id: str,
        native_observation_root: Path,
        native_intake: dict[str, Any],
        expected_head: str,
        current_task_ref: str,
        current_task_sha256: str,
        dispatch: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Authorize only an exact native recovery-return continuation.

        The method never performs a dispatch. The first successful pending-event
        append exposes one dispatchable intent. A restart only observes it. An
        exact native receipt is required for pending -> dispatched.
        """
        project_fd: int | None = None
        state_fd: int | None = None
        native_fd: int | None = None

        def require_string(value: object, label: str) -> str:
            if not isinstance(value, str) or not value:
                raise LedgerError(f"{label} must be a non-empty string")
            return value

        def require_sha256(value: object, label: str) -> str:
            checked = require_string(value, label)
            if not _hash(checked):
                raise LedgerError(f"{label} must be a lowercase SHA-256")
            return checked

        def is_within(child: Path, parent: Path) -> bool:
            try:
                child.relative_to(parent)
                return True
            except ValueError:
                return False

        def read_state_json(name: str) -> dict[str, Any]:
            raw = retry_policy._read_owned_text(state_fd, name, required=True)
            try:
                value = json.loads(raw)
            except (TypeError, json.JSONDecodeError) as exc:
                raise LedgerError(f"{name} is not readable JSON") from exc
            if not isinstance(value, dict):
                raise LedgerError(f"{name} must contain a JSON object")
            return value

        try:
            require_string(execution_package_id, "execution_package_id")
            require_string(execution_work_id, "execution_work_id")
            require_string(current_task_ref, "current_task_ref")
            require_sha256(current_task_sha256, "current_task_sha256")
            if (
                not isinstance(expected_head, str)
                or len(expected_head) != 40
                or bool(set(expected_head) - HEX)
            ):
                raise LedgerError(
                    "expected_head must be an independently supplied 40-character Git HEAD"
                )

            project_path = Path(project).absolute()
            native_path = Path(native_observation_root).absolute()
            project_real = project_path.resolve(strict=True)
            native_real = native_path.resolve(strict=True)
            if is_within(project_real, native_real) or is_within(native_real, project_real):
                raise LedgerError("native root and writer project must be disjoint")

            project_fd, state_fd = retry_policy._open_fixed_state(project_path)
            native_fd = retry_policy._open_project_directory(native_path)
            retry_policy._require_disjoint_directories(project_fd, native_fd)
            project_stat = os.fstat(project_fd)
            native_stat = os.fstat(native_fd)
            if (project_stat.st_dev, project_stat.st_ino) == (
                native_stat.st_dev,
                native_stat.st_ino,
            ):
                raise LedgerError("native root aliases the writer project")

            def retained_loader(reference: object, digest: object, label: str) -> dict[str, Any]:
                return retry_policy._read_retained_json(project_fd, reference, digest, label)

            def native_loader(reference: object, digest: object, label: str) -> dict[str, Any]:
                if not isinstance(reference, str) or not reference.startswith("native://"):
                    raise LedgerError(f"{label}_ref must be a native:// reference")
                return retry_policy._read_retained_json(
                    native_fd,
                    "repo://" + reference.removeprefix("native://"),
                    digest,
                    label,
                )

            plan = read_state_json("project-plan.json")
            registry = read_state_json("task-registry.json")
            approvals = read_state_json("approval-queue.json")

            raw_packages = plan.get("execution_packages")
            if not isinstance(raw_packages, list) or not raw_packages:
                raise LedgerError("project plan has no execution packages")
            checked_packages = [
                continuous_execution.validate_execution_package(item)
                for item in raw_packages
            ]
            if (
                len({item["package_id"] for item in checked_packages}) != len(checked_packages)
                or len({item["work_id"] for item in checked_packages}) != len(checked_packages)
                or len({item["approval_id"] for item in checked_packages}) != len(checked_packages)
            ):
                raise LedgerError("execution package/work/approval IDs must be unique")

            matches = [
                item
                for item in checked_packages
                if item["package_id"] == execution_package_id
                and item["work_id"] == execution_work_id
            ]
            if len(matches) != 1:
                raise LedgerError("package and work ID must select exactly one package")
            package = matches[0]

            selected_plan = dict(plan)
            selected_plan["execution_packages"] = [package]
            continuous_execution.validate_execution_records(
                selected_plan,
                registry,
                approvals,
                retained_loader=retained_loader,
                native_observation_loader=native_loader,
                submitting_project=project_path,
                native_observation_root=native_path,
            )
            # Existing exact-nine-key ABI. expected_head is intentionally separate.
            retry_policy._validate_native_intake(native_intake, package)

            tasks = registry.get("tasks")
            if not isinstance(tasks, list):
                raise LedgerError("task registry tasks must be an array")
            writers = [
                task
                for task in tasks
                if isinstance(task, dict)
                and task.get("execution_work_id") == package["work_id"]
                and task.get("execution_package_id") == package["package_id"]
                and task.get("task_id") == package["writer_task_id"]
            ]
            if len(writers) != 1:
                raise LedgerError("package must bind exactly one registered writer")
            registered_writer = writers[0]

            current_task = native_loader(
                current_task_ref,
                current_task_sha256,
                "current task",
            )
            current_task_keys = {
                "schema",
                "kind",
                "observation_id",
                "authority_kind",
                "native_root_id",
                "coordinator_task_id",
                "work_id",
                "package_id",
                "package_digest",
                "project",
                "candidate_sha256",
                "writer_task_id",
                "task_id",
                "owner_task_id",
                "registered_status",
                "status",
                "current_head",
                "resource_unit",
                "resource_units_used",
            }
            if set(current_task) != current_task_keys:
                raise LedgerError("current task fields are incomplete or ambiguous")
            fixed_current_task = {
                "schema": "CHIEF_NATIVE_TASK_STATE_V1",
                "kind": "current_task_state",
                "authority_kind": "native_coordinator_observation",
                "native_root_id": package["native_intake"]["root_id"],
                "coordinator_task_id": package["native_intake"]["coordinator_task_id"],
                "work_id": package["work_id"],
                "package_id": package["package_id"],
                "package_digest": continuous_execution.package_digest(package),
                "project": package["project"],
                "candidate_sha256": package["candidate_sha256"],
                "writer_task_id": package["writer_task_id"],
                "task_id": package["writer_task_id"],
                "registered_status": registered_writer["status"],
                "current_head": expected_head,
                "resource_unit": package["resource_limits"]["resource_unit"],
            }
            if any(current_task.get(key) != value for key, value in fixed_current_task.items()):
                raise LedgerError("current task does not bind the approved package")
            if (
                not isinstance(current_task["observation_id"], str)
                or not current_task["observation_id"]
                or not isinstance(current_task["owner_task_id"], str)
                or not current_task["owner_task_id"]
                or not isinstance(current_task["status"], str)
                or not current_task["status"]
                or type(current_task["resource_units_used"]) is not int
                or current_task["resource_units_used"] < 0
            ):
                raise LedgerError("current task native fields are invalid")

            snapshot = self._load()
            return_keys = {
                "schema",
                "report_id",
                "return_id",
                "work_id",
                "package_id",
                "candidate_sha256",
                "kind",
                "scope",
                "source_task_id",
                "target_task_id",
                "project_id",
                "return_to_task_id",
                "native_receipt_ref",
                "native_receipt_sha256",
            }
            exact_reports: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
            for report_id in sorted(snapshot["reports"]):
                report = snapshot["reports"][report_id]
                payload = report.get("continuous_payload")
                if not isinstance(payload, dict):
                    continue
                if (
                    payload.get("work_id") != package["work_id"]
                    or payload.get("package_id") != package["package_id"]
                    or payload.get("candidate_sha256") != package["candidate_sha256"]
                ):
                    continue
                allowed_return_keys = return_keys | ({"testing_delegation"} if payload.get("kind") == "test_pass" and "testing_delegation" in payload else set())
                if set(payload) != allowed_return_keys:
                    raise LedgerError("exact return payload fields are incomplete or ambiguous")
                if (
                    payload.get("schema") != "CHIEF_CONTINUOUS_RETURN_V1"
                    or payload.get("report_id") != report_id
                    or payload.get("source_task_id") != report.get("source_task_id")
                    or payload.get("target_task_id") != report.get("target_task_id")
                    or payload.get("project_id") != report.get("project_id")
                    or payload.get("project_id") != package["project"]["project_id"]
                    or payload.get("source_task_id") != package["writer_task_id"]
                    or payload.get("target_task_id")
                    != package["native_intake"]["coordinator_task_id"]
                    or payload.get("return_to_task_id") != package["writer_task_id"]
                    or payload.get("scope") != "local"
                    or not isinstance(payload.get("return_id"), str)
                    or not payload["return_id"]
                    or not isinstance(payload.get("native_receipt_ref"), str)
                    or not payload["native_receipt_ref"]
                    or not _hash(payload.get("native_receipt_sha256"))
                ):
                    raise LedgerError("return payload does not bind writer -> coordinator")
                exact_reports.append((report_id, report, payload))

            if len(exact_reports) > 1:
                raise LedgerError("multiple reports claim the exact active candidate")
            exact = exact_reports[0] if exact_reports else None

            if dispatch is None and exact is not None and exact[1].get("state") == "native_execution_dispatched":
                intent = exact[1].get("native_execution_intent")
                stored = exact[1].get("native_execution_dispatch")
                if not isinstance(intent, dict) or not isinstance(stored, dict):
                    raise LedgerError("dispatched native action is missing its retained receipt")
                dispatch = {"report_id": exact[0], "action_id": intent.get("action_id"), "evidence_ref": stored.get("dispatch_evidence_ref"), "evidence_sha256": stored.get("dispatch_evidence_sha256")}

            if dispatch is not None:
                dispatch_keys = {
                    "report_id",
                    "action_id",
                    "evidence_ref",
                    "evidence_sha256",
                }
                if set(dispatch) != dispatch_keys:
                    raise LedgerError("dispatch arguments are incomplete or ambiguous")
                require_sha256(dispatch["evidence_sha256"], "dispatch.evidence_sha256")
                if exact is None or dispatch["report_id"] != exact[0]:
                    raise LedgerError("dispatch receipt does not select the exact report")

                report_id, report, payload = exact
                intent = report.get("native_execution_intent")
                if (
                    report.get("state")
                    not in {"native_execution_intent_pending", "native_execution_dispatched"}
                    or not isinstance(intent, dict)
                    or dispatch["action_id"] != intent.get("action_id")
                    or any(intent.get(key) != package_value for key, package_value in (("work_id", package["work_id"]), ("package_id", package["package_id"]), ("candidate_sha256", package["candidate_sha256"]), ("native_root_id", package["native_intake"]["root_id"]), ("coordinator_task_id", package["native_intake"]["coordinator_task_id"]), ("return_to_task_id", package["writer_task_id"])))
                ):
                    raise LedgerError("dispatch receipt has no matching native intent")

                observed = native_loader(
                    dispatch["evidence_ref"],
                    dispatch["evidence_sha256"],
                    "return dispatch",
                )
                observed_keys = {
                    "schema",
                    "kind",
                    "observation_id",
                    "authority_kind",
                    "native_root_id",
                    "coordinator_task_id",
                    "report_id",
                    "return_id",
                    "action_id",
                    "work_id",
                    "package_id",
                    "candidate_sha256",
                    "project",
                    "source_task_id",
                    "target_task_id",
                    "current_task_observation_id",
                    "expected_head",
                    "status",
                    "dispatch_tool",
                    "native_event_id",
                }
                expected_dispatch = {
                    "schema": "CHIEF_NATIVE_RETURN_DISPATCH_RECEIPT_V1",
                    "kind": f"{intent['return_kind']}_dispatch",
                    "authority_kind": "native_coordinator_observation",
                    "native_root_id": intent["native_root_id"],
                    "coordinator_task_id": intent["coordinator_task_id"],
                    "report_id": report_id,
                    "return_id": intent["return_id"],
                    "action_id": intent["action_id"],
                    "work_id": intent["work_id"],
                    "package_id": intent["package_id"],
                    "candidate_sha256": intent["candidate_sha256"],
                    "project": package["project"],
                    "source_task_id": intent["coordinator_task_id"],
                    "target_task_id": intent["return_to_task_id"],
                    "current_task_observation_id": intent["current_task_observation_id"],
                    "expected_head": intent["expected_head"],
                    "status": "accepted",
                }
                if (
                    set(observed) != observed_keys
                    or any(observed.get(key) != value for key, value in expected_dispatch.items())
                    or any(
                        not isinstance(observed.get(key), str) or not observed[key]
                        for key in ("observation_id", "dispatch_tool", "native_event_id")
                    )
                ):
                    raise LedgerError("native dispatch receipt does not bind the action")

                if report["state"] == "native_execution_dispatched":
                    previous = report.get("native_execution_dispatch")
                    if (
                        not isinstance(previous, dict)
                        or previous.get("dispatch_evidence_ref") != dispatch["evidence_ref"]
                        or previous.get("dispatch_evidence_sha256")
                        != dispatch["evidence_sha256"]
                    ):
                        raise LedgerError("dispatched action conflicts with retained receipt")
                    return {
                        "status": current_task["status"],
                        "phase": "native_execution_dispatched",
                        "next_action": "NO_ACTION",
                        "action_id": intent["action_id"],
                    }

                event_payload = {
                    "report_id": report_id,
                    "source_task_id": report["source_task_id"],
                    "target_task_id": report["target_task_id"],
                    "project_id": report["project_id"],
                    "payload_sha256": report["payload_sha256"],
                    "action_id": intent["action_id"],
                    "return_id": intent["return_id"],
                    "work_id": intent["work_id"],
                    "package_id": intent["package_id"],
                    "candidate_sha256": intent["candidate_sha256"],
                    "dispatch_evidence_ref": dispatch["evidence_ref"],
                    "dispatch_evidence_sha256": dispatch["evidence_sha256"],
                    "dispatch_observation": observed,
                }
                self.ingest("RETURN_NATIVE_DISPATCH_OBSERVED", event_payload)
                return {
                    "status": current_task["status"],
                    "phase": "native_execution_dispatched",
                    "next_action": "NO_ACTION",
                    "action_id": intent["action_id"],
                }

            if exact is not None:
                report_id, report, payload = exact
                if report.get("state") == "native_execution_intent_pending":
                    intent = report["native_execution_intent"]
                    return {
                        "status": current_task["status"],
                        "phase": "native_execution_intent_pending",
                        "next_action": "OBSERVE_RETURN_DISPATCH",
                        "report_id": report_id,
                        "return_id": intent["return_id"],
                        "action_id": intent["action_id"],
                    }
                if report.get("state") == "native_execution_dispatched":
                    intent = report["native_execution_intent"]
                    return {
                        "status": current_task["status"],
                        "phase": "native_execution_dispatched",
                        "next_action": "NO_ACTION",
                        "report_id": report_id,
                        "return_id": intent["return_id"],
                        "action_id": intent["action_id"],
                    }

            status = current_task["status"]
            if current_task["owner_task_id"] != package["writer_task_id"]:
                return {"status": status, "next_action": "HOLD_OWNER_MISMATCH"}
            if status in {"paused", "archived"}:
                return {"status": status, "next_action": "HOLD_INACTIVE_TARGET"}
            if status in {"completed", "local_delivered"}:
                return {"status": status, "next_action": "NO_ACTION"}
            if status == "running":
                return {"status": status, "next_action": "NO_ACTION_ACTIVE_WRITER"}
            if (
                current_task["resource_units_used"]
                >= package["resource_limits"]["max_resource_units"]
            ):
                return {"status": status, "next_action": "STOP_RESOURCE_LIMIT"}
            if exact is None:
                return {"status": status, "next_action": "OBSERVATION_GAP"}

            report_id, report, payload = exact
            if payload["kind"] not in {"recovery", "test_pass", "approval", "resource_recovered"}:
                return {
                    "status": status,
                    "next_action": "HOLD_RETURN_KIND_NOT_IMPLEMENTED",
                    "return_kind": payload["kind"],
                }
            expected_status = {"recovery": "technical_blocked", "test_pass": "testing_queue", "approval": "awaiting_permission", "resource_recovered": "quota_limited"}[payload["kind"]]
            if status != expected_status:
                return {"status": status, "next_action": "HOLD_RETURN_STATE_MISMATCH"}
            if report.get("state") != "reviewed" or report.get("review_decision") != "accepted":
                return {"status": status, "next_action": "HOLD_RETURN_NOT_REVIEWED"}

            if payload["kind"] == "test_pass":
                continuous_execution.validate_native_testing_return(payload, package=package, native_loader=native_loader, submitting_project=project_path, native_observation_root=native_path)
            else:
                recovery = native_loader(payload["native_receipt_ref"], payload["native_receipt_sha256"], "recovery return")
            recovery_keys = {
                "schema",
                "kind",
                "observation_id",
                "authority_kind",
                "native_root_id",
                "coordinator_task_id",
                "report_id",
                "work_id",
                "package_id",
                "package_digest",
                "candidate_sha256",
                "project",
                "source_task_id",
                "target_task_id",
                "return_to_task_id",
                "current_head",
                "status",
            }
            expected_recovery = {
                "schema": {"recovery": "CHIEF_NATIVE_RECOVERY_RETURN_V1", "approval": "CHIEF_NATIVE_APPROVAL_RETURN_V1", "resource_recovered": "CHIEF_NATIVE_RESOURCE_RECOVERY_RETURN_V1"}.get(payload["kind"]),
                "kind": payload["kind"] + "_return",
                "observation_id": payload["return_id"],
                "authority_kind": "native_coordinator_observation",
                "native_root_id": package["native_intake"]["root_id"],
                "coordinator_task_id": package["native_intake"]["coordinator_task_id"],
                "report_id": report_id,
                "work_id": package["work_id"],
                "package_id": package["package_id"],
                "package_digest": continuous_execution.package_digest(package),
                "candidate_sha256": package["candidate_sha256"],
                "project": package["project"],
                "source_task_id": package["writer_task_id"],
                "target_task_id": package["native_intake"]["coordinator_task_id"],
                "return_to_task_id": package["writer_task_id"],
                "current_head": expected_head,
                "status": "accepted",
            }
            if payload["kind"] == "approval":
                # A return releases only this already approved package. New
                # permissions and unrelated waiting inputs are not inferred.
                approval_fields = {key: package[key] for key in ("approval_id", "approval_evidence_ref", "approval_receipt_sha256")}
                recovery_keys.update(approval_fields)
                expected_recovery.update(approval_fields)
            elif payload["kind"] == "resource_recovered":
                resource_fields = {"resource_unit": package["resource_limits"]["resource_unit"], "resource_units_used": current_task["resource_units_used"], "available": True, "new_paid_capacity": False}
                recovery_keys.update(resource_fields)
                expected_recovery.update(resource_fields)
                if recovery.get("available") is not True or recovery.get("new_paid_capacity") is not False or type(recovery.get("resource_units_used")) is not int:
                    raise LedgerError("resource recovery cannot buy or reset capacity")
            if payload["kind"] != "test_pass" and (
                set(recovery) != recovery_keys
                or any(recovery.get(key) != value for key, value in expected_recovery.items())
            ):
                raise LedgerError("native return receipt does not bind the approved continuation")

            action_core = {
                "schema": "CHIEF_RETURN_DISPATCH_INTENT_V1",
                "report_id": report_id,
                "report_payload_sha256": report["payload_sha256"],
                "return_id": payload["return_id"],
                "return_kind": payload["kind"],
                "work_id": package["work_id"],
                "package_id": package["package_id"],
                "candidate_sha256": package["candidate_sha256"],
                "return_to_task_id": package["writer_task_id"],
                "native_root_id": package["native_intake"]["root_id"],
                "coordinator_task_id": package["native_intake"]["coordinator_task_id"],
                "return_receipt_sha256": payload["native_receipt_sha256"],
                "current_task_observation_id": current_task["observation_id"],
                "current_task_sha256": current_task_sha256,
                "expected_head": expected_head,
            }
            action_id = _sha(_canonical(action_core))
            pending_event = {
                "report_id": report_id,
                "source_task_id": report["source_task_id"],
                "target_task_id": report["target_task_id"],
                "project_id": report["project_id"],
                "payload_sha256": report["payload_sha256"],
                "action_id": action_id,
                "return_id": payload["return_id"],
                "return_kind": payload["kind"],
                "work_id": package["work_id"],
                "package_id": package["package_id"],
                "candidate_sha256": package["candidate_sha256"],
                "return_to_task_id": package["writer_task_id"],
                "native_root_id": package["native_intake"]["root_id"],
                "coordinator_task_id": package["native_intake"]["coordinator_task_id"],
                "return_receipt_ref": payload["native_receipt_ref"],
                "return_receipt_sha256": payload["native_receipt_sha256"],
                "current_task_ref": current_task_ref,
                "current_task_sha256": current_task_sha256,
                "current_task_observation_id": current_task["observation_id"],
                "expected_head": expected_head,
            }
            created = self.ingest("RETURN_NATIVE_INTENT_PREPARED", pending_event)
            if not created:
                return {
                    "status": status,
                    "phase": "native_execution_intent_pending",
                    "next_action": "OBSERVE_RETURN_DISPATCH",
                    "report_id": report_id,
                    "return_id": payload["return_id"],
                    "action_id": action_id,
                }
            return {
                "status": status,
                "phase": "native_execution_intent_pending",
                "next_action": "DISPATCH_RETURNED_WORK",
                "action": {
                    **action_core,
                    "action_id": action_id,
                    "target_task_id": package["writer_task_id"],
                },
            }
        except (
            retry_policy.RetryPolicyError,
            continuous_execution.ContinuousExecutionError,
        ) as exc:
            raise LedgerError(str(exc)) from exc
        finally:
            for fd in (native_fd, state_fd, project_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--ledger",required=True);sub=p.add_subparsers(dest="command",required=True);i=sub.add_parser("ingest");i.add_argument("--event",required=True);i.add_argument("--payload",required=True);sub.add_parser("check");sub.add_parser("reconcile");c=sub.add_parser("continuous-reconcile");c.add_argument("--project",required=True);c.add_argument("--execution-package-id",required=True);c.add_argument("--execution-work-id",required=True);c.add_argument("--native-observation-root",required=True);c.add_argument("--native-intake-json",required=True);c.add_argument("--current-task-ref",required=True);c.add_argument("--current-task-sha256",required=True);c.add_argument("--expected-head",required=True);c.add_argument("--dispatch-report-id");c.add_argument("--dispatch-action-id");c.add_argument("--dispatch-evidence-ref");c.add_argument("--dispatch-evidence-sha256");a=p.parse_args(argv)
    try:
        l=Ledger(Path(a.ledger))
        if a.command=="ingest":
            if a.event in {"RETURN_NATIVE_INTENT_PREPARED","RETURN_NATIVE_DISPATCH_OBSERVED"}: raise LedgerError("native execution events require continuous-reconcile")
            l.ingest(a.event,json.loads(Path(a.payload).read_text(encoding="utf-8")));print(json.dumps(l.snapshot(),sort_keys=True))
        elif a.command=="check": print(json.dumps(l.snapshot(),sort_keys=True))
        elif a.command=="reconcile": print(json.dumps(l.reconcile(),sort_keys=True))
        else:
            dispatch_values=(a.dispatch_report_id,a.dispatch_action_id,a.dispatch_evidence_ref,a.dispatch_evidence_sha256)
            if any(value is not None for value in dispatch_values):
                if not all(isinstance(value,str) and value for value in dispatch_values): raise LedgerError("dispatch mode requires all four dispatch arguments")
                dispatch={"report_id":a.dispatch_report_id,"action_id":a.dispatch_action_id,"evidence_ref":a.dispatch_evidence_ref,"evidence_sha256":a.dispatch_evidence_sha256}
            else: dispatch=None
            result=l.reconcile_native_execution(project=Path(a.project),execution_package_id=a.execution_package_id,execution_work_id=a.execution_work_id,native_observation_root=Path(a.native_observation_root),native_intake=json.loads(a.native_intake_json),expected_head=a.expected_head,current_task_ref=a.current_task_ref,current_task_sha256=a.current_task_sha256,dispatch=dispatch)
            print(json.dumps(result,sort_keys=True))
        return 0
    except (OSError,json.JSONDecodeError,LedgerError,retry_policy.RetryPolicyError,continuous_execution.ContinuousExecutionError) as e: print(f"error: {e}",file=os.sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
