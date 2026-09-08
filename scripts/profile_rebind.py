"""Prepare and verify a frozen profile proposal; never apply it to live inputs."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, tempfile
from pathlib import Path
try:
    from .preference_lib import PreferenceError, managed_agents_block, preset_profile, read_json, require_valid, update_managed_agents
except ImportError:
    from preference_lib import PreferenceError, managed_agents_block, preset_profile, read_json, require_valid, update_managed_agents
class RebindError(ValueError): pass
def _sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def _ancestors(path:Path,label:str,*,allow_missing_leaf:bool=False)->None:
    if not path.is_absolute():raise RebindError(f"{label} must be absolute")
    cursor=path.parent if allow_missing_leaf else path
    while not cursor.exists() and cursor.parent!=cursor: cursor=cursor.parent
    # /tmp and /var are OS compatibility redirects on macOS; user-created
    # aliases below them are still refused.
    while cursor.parent!=cursor:
        if cursor.is_symlink() and cursor not in {Path("/tmp"),Path("/var")}:
            raise RebindError(f"{label} has a symlinked ancestor")
        cursor=cursor.parent
def _regular(path:Path,label:str)->Path:
    _ancestors(path,label)
    if path.is_symlink() or not path.is_file() or path.stat().st_nlink!=1:raise RebindError(f"{label} must be a non-symlink one-link regular file")
    return path.resolve(strict=True)
def _new_output(path:Path,label:str,inputs:list[Path],other:Path|None=None)->Path:
    _ancestors(path,label,allow_missing_leaf=True)
    if path.exists() or path.is_symlink():raise RebindError(f"{label} must name a new output file")
    resolved=path.absolute()
    for item in inputs+([other] if other else []):
        if resolved==item or (resolved.exists() and os.path.samefile(resolved,item)):
            raise RebindError(f"{label} aliases an input or other output")
    return resolved
def default_profile()->dict:return preset_profile("core")
def prepare(profile_path:Path,agents_path:Path,expected_profile_sha256:str,expected_agents_sha256:str,*,renderer_path:Path)->dict[str,str]:
    profile_path=_regular(profile_path,"profile");agents_path=_regular(agents_path,"global AGENTS");renderer_path=_regular(renderer_path,"renderer")
    if os.path.samefile(profile_path,agents_path):raise RebindError("profile and global AGENTS must be distinct")
    pb,ab=profile_path.read_bytes(),agents_path.read_bytes()
    if _sha(pb)!=expected_profile_sha256 or _sha(ab)!=expected_agents_sha256:raise RebindError("profile or global AGENTS preimage hash drifted")
    try: profile=read_json(profile_path);require_valid(profile)
    except PreferenceError as e:raise RebindError(f"profile is invalid: {e}") from e
    if profile.get("scope")!="global":raise RebindError("profile rebind requires a global profile")
    block=managed_agents_block(profile_path,renderer_path)
    with tempfile.TemporaryDirectory() as t:
        staged=Path(t)/"AGENTS.md";shutil.copyfile(agents_path,staged);update_managed_agents(staged,block); proposed=staged.read_bytes()
    return {"schema":"CHIEF_PROFILE_REBIND_V1","profile_sha256":_sha(pb),"global_agents_sha256":_sha(ab),"proposed_global_agents_sha256":_sha(proposed),"profile_locator":str(profile_path),"writes_performed":"none","proposed_text":proposed.decode()}
def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("command",choices=("prepare","verify-prepared"));
    for x in ("profile","global-agents","expected-profile-sha256","expected-global-agents-sha256","renderer","receipt-out","frozen-output"):p.add_argument("--"+x,required=True)
    a=p.parse_args(argv)
    try:
        profile,agents,renderer=Path(a.profile),Path(a.global_agents),Path(a.renderer)
        receipt=prepare(profile,agents,a.expected_profile_sha256,a.expected_global_agents_sha256,renderer_path=renderer); frozen=receipt.pop("proposed_text").encode()
        inputs=[_regular(profile,"profile"),_regular(agents,"global AGENTS"),_regular(renderer,"renderer")]
        if a.command=="verify-prepared":
            rp=_regular(Path(a.receipt_out),"receipt output");op=_regular(Path(a.frozen_output),"frozen output")
            if any(os.path.samefile(item, candidate) for item in inputs for candidate in (rp,op)) or os.path.samefile(rp,op):
                raise RebindError("prepared outputs alias a live input or each other")
            if json.loads(rp.read_text(encoding="utf-8")) != receipt or op.read_bytes()!=frozen:
                raise RebindError("prepared receipt or frozen output does not match current preimages")
            print(json.dumps({k:v for k,v in receipt.items() if k!="profile_locator"},sort_keys=True));return 0
        rp=_new_output(Path(a.receipt_out),"receipt output",inputs);op=_new_output(Path(a.frozen_output),"frozen output",inputs,rp)
        rp.parent.mkdir(parents=True,exist_ok=True);op.parent.mkdir(parents=True,exist_ok=True)
        # Both target paths were validated new before either write begins.
        rp.write_text(json.dumps(receipt,sort_keys=True)+"\n",encoding="utf-8");op.write_bytes(frozen)
        print(json.dumps({k:v for k,v in receipt.items() if k!="profile_locator"},sort_keys=True));return 0
    except (OSError,ValueError,RebindError,PreferenceError) as e:print(f"error: {e}");return 2
if __name__=="__main__":raise SystemExit(main())
