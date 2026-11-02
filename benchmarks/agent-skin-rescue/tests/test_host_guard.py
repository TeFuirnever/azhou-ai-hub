"""Bounded fresh-run Seatbelt kernel suite. Never execute a host application."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid

SOURCE = Path(__file__).resolve().parents[1]
WORKTREE = SOURCE.parents[1]
sys.path.insert(0, str(SOURCE))
from host_guard import compile_policy, PUBLIC_READ_ROOTS, HELPER_NAMES

HELPER = r'''from pathlib import Path
import ctypes,errno,json,os,subprocess,sys
os.umask(0o077)
c=json.loads(sys.argv[1]);run=Path(c["run"]);bundle=Path(c["bundle"]);profile=Path(c["profile"])
if len(sys.argv)>2 and sys.argv[2]=="--descendant":
    try:(bundle/"Contents/version.txt").write_bytes(b"DESCENDANT_UNEXPECTED")
    except OSError as e:
        print(json.dumps({"denied":e.errno in (errno.EPERM,errno.EACCES),"errno":e.errno}))
        raise SystemExit(0 if e.errno in (errno.EPERM,errno.EACCES) else 1)
    raise SystemExit(2)
results=[]
def denied(name,fn):
    try:fn()
    except OSError as e:results.append({"name":name,"passed":e.errno in (errno.EPERM,errno.EACCES),"errno":e.errno})
    else:results.append({"name":name,"passed":False,"reason":"unexpectedly allowed"})
target=run/"allowed.bin"
try:
    with target.open("xb") as f:f.write(b"allowed\x00\xff")
    results.append({"name":"allow-new-run-write","passed":target.read_bytes()==b"allowed\x00\xff"})
except OSError as e:results.append({"name":"allow-new-run-write","passed":False,"errno":e.errno})
denied("deny-original-direct-write",lambda:(bundle/"Contents/version.txt").write_bytes(b"UNEXPECTED"))
denied("deny-profile-read",lambda:(profile/"secret.txt").read_bytes())
denied("deny-existing-symlink-read",lambda:(bundle/"Contents/profile-link").read_bytes())
denied("deny-new-symlink",lambda:os.symlink(profile/"secret.txt",run/"new-symlink"))
denied("deny-hardlink-from-readable-original",lambda:os.link(bundle/"Contents/version.txt",run/"new-hardlink"))
def clone():
    lib=ctypes.CDLL("/usr/lib/libSystem.B.dylib",use_errno=True)
    fn=lib.clonefile;fn.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];fn.restype=ctypes.c_int
    if fn(os.fsencode(bundle/"Contents/version.txt"),os.fsencode(run/"new-clone"),0)!=0:
        value=ctypes.get_errno();raise OSError(value,os.strerror(value))
denied("deny-file-clone-from-readable-original",clone)
denied("deny-original-unlink",lambda:(bundle/"Contents/version.txt").unlink())
denied("deny-original-rename-to-run",lambda:os.rename(bundle/"Contents/version.txt",run/"stolen"))
denied("deny-original-parent-replacement",lambda:os.rename(bundle,bundle.parent/"replaced.app"))
try:
    child=subprocess.Popen([c["python"],"-I","-S","-B",c["helper"],sys.argv[1],"--descendant"],
                           stdin=None,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
    stdout,stderr=child.communicate(timeout=5)
    observed=json.loads(stdout)
    results.append({"name":"deny-descendant-original-write","passed":child.returncode==0 and observed.get("denied") is True,
                    "pid":child.pid,"actual_exit_code":child.returncode,"signal":-child.returncode if child.returncode<0 else None,
                    "stdout":stdout.decode(),"stderr":stderr.decode()})
except Exception as e:results.append({"name":"deny-descendant-original-write","passed":False,"error":type(e).__name__})
def updater():
    child=subprocess.Popen([str(bundle/"Contents/update-helper")],stdin=None,stdout=subprocess.PIPE,stderr=subprocess.PIPE,close_fds=True)
    child.communicate(timeout=3)
denied("deny-alternative-updater-exec",updater)
sys.stdout.buffer.write((json.dumps({"scope":"synthetic kernel fileguard only","results":results,
    "passed":sum(x["passed"] for x in results),"total":len(results),"uid":os.getuid()},sort_keys=True)+"\n").encode())
sys.stderr.buffer.write(b"kernel-synthetic-stderr\x00\xff")
raise SystemExit(0 if all(x["passed"] for x in results) else 1)
'''


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def new_json(path, value):
    with Path(path).open("x") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    out = args.out
    if not out.is_absolute() or ".." in out.parts or not out.is_relative_to(WORKTREE/".scratch") or out.parent.resolve()!=out.parent:
        raise ValueError("output must be a fresh canonical worktree scratch directory")
    out.mkdir(mode=0o700,exist_ok=False)
    started=now();checks=[]
    bundle=out/"public/Synthetic.app";(bundle/"Contents").mkdir(mode=0o700,parents=True)
    (bundle/"Contents/version.txt").write_bytes(b"ORIGINAL_SYNTHETIC_BUNDLE\n")
    with (bundle/"Contents/update-helper").open("xb") as f:f.write(Path("/bin/echo").read_bytes())
    (bundle/"Contents/update-helper").chmod(0o700)
    protected=out/"simulated-profile";protected.mkdir(mode=0o700);(protected/"secret.txt").write_bytes(b"SYNTHETIC_NO_PRIVATE_DATA\n")
    (bundle/"Contents/profile-link").symlink_to(protected/"secret.txt")
    helper=out/"kernel-helper.py";helper.write_text(HELPER)
    run=out/"run";run.mkdir(mode=0o700)
    python=Path(sys.executable).resolve()
    roots=[*PUBLIC_READ_ROOTS,Path(sys.base_prefix).resolve()]
    python_helper=Path(sys.base_prefix).resolve()/"Resources/Python.app/Contents/MacOS/Python"
    python_execs=[python]
    if python_helper.is_file(): python_execs.append(python_helper.resolve())
    kwargs=dict(original_bundle=bundle,read_roots=roots,executable_paths=python_execs,
                read_files=[helper],protected_paths=[protected],scope="fixture-only")
    def rejected(name,change,root=run):
        try:compile_policy(root,**dict(kwargs,**change))
        except (ValueError,OSError):checks.append({"name":name,"passed":True})
        else:checks.append({"name":name,"passed":False})
    rejected("reject-global-read-root",{"read_roots":[Path("/")]})
    rejected("reject-whole-users-read-root",{"read_roots":[Path("/Users")]})
    rejected("reject-out-of-role-read-file",{"read_files":[protected/"secret.txt"]})
    from unittest.mock import patch
    with patch("host_guard._file", side_effect=AssertionError("out-of-role read attempted")) as opening:
        rejected_first = False
        try: compile_policy(run, **dict(kwargs, read_files=[protected/"secret.txt"]))
        except ValueError: rejected_first = True
        except AssertionError: pass
        checks.append({"name":"reject-out-of-role-before-any-file-binding", "passed": rejected_first and not opening.called})
    fifo=out/"fifo";os.mkfifo(fifo,0o600)
    rejected("reject-nonregular-fifo-without-blocking",{"read_files":[fifo]})
    alias=out/"protected-alias";alias.symlink_to(run)
    rejected("reject-protected-symlink-alias",{"protected_paths":[alias]})
    prelink=out/"prelinked-run";prelink.mkdir(mode=0o700);os.link(bundle/"Contents/version.txt",prelink/"alias")
    rejected("reject-preexisting-hardlink-in-run",{},prelink)
    presym=out/"presymlink-run";presym.mkdir(mode=0o700);(presym/"alias").symlink_to(protected/"secret.txt")
    rejected("reject-preexisting-symlink-in-run",{},presym)
    validator_count=len(checks)
    policy,manifest=compile_policy(run,**kwargs)
    (out/"fixture.sb").write_text(policy);new_json(out/"fixture-policy.json",manifest)
    config={"run":str(run),"bundle":str(bundle),"profile":str(protected),"helper":str(helper),"python":str(python)}
    argv=["/usr/bin/sandbox-exec","-p",policy,str(python),"-I","-S","-B",str(helper),json.dumps(config,sort_keys=True)]
    env={"PATH":"/usr/bin:/bin","LANG":"C","LC_ALL":"C","HOME":str(run/"home"),"CFFIXED_USER_HOME":str(run/"home"),"TMPDIR":str(run/"tmp")}
    (run/"home").mkdir(mode=0o700);(run/"tmp").mkdir(mode=0o700)
    print(json.dumps({"event":"kernel-started","observed_at":now(),"profile_sha256":hashlib.sha256(policy.encode()).hexdigest(),"out":str(out)}),flush=True)
    kernel_started=now();code=None;error=None;pid=None;timed=False
    with (run/"stdout.raw").open("xb") as stdout,(run/"stderr.raw").open("xb") as stderr:
        try:
            child=subprocess.Popen(argv,cwd=run,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,close_fds=True)
            pid=child.pid
            try:code=child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                timed=True;child.terminate()
                try:code=child.wait(timeout=2)
                except subprocess.TimeoutExpired:child.kill();code=child.wait(timeout=2)
        except OSError as e:error={"type":type(e).__name__,"errno":e.errno,"message":str(e)}
        stdout.flush();stderr.flush();os.fsync(stdout.fileno());os.fsync(stderr.fileno())
    kernel_finished=now()
    record={"kind":"C" if code is not None else "E","command_id":str(uuid.uuid4()),"argv":argv,"cwd":str(run),
            "started_at":kernel_started,"observed_at":kernel_finished,"pid":pid,"exit_code":code,
            "signal":-code if code is not None and code<0 else None,
            "execution_state":"timed_out" if timed else "not_started" if pid is None else "exit_unknown" if code is None else "signaled" if code<0 else "exited",
            "error":error,"policy_sha256":hashlib.sha256(policy.encode()).hexdigest(),"policy_source":"fixed in-memory -p text",
            "close_fds":True,"stdin":"DEVNULL","stdio_exceptions":[str(run/"stdout.raw"),str(run/"stderr.raw")],
            "inputs":[{"path":str(helper),"sha256":sha(helper)}],
            "outputs":{"mode":"separate","raw_files":[{"path":str((run/n).relative_to(out)),"sha256":sha(run/n),"bytes":(run/n).stat().st_size} for n in ["stdout.raw","stderr.raw"]]}}
    new_json(out/"kernel-command.json",record)
    try:report=json.loads((run/"stdout.raw").read_bytes())
    except (ValueError,UnicodeDecodeError):report=None
    if report:checks.extend(report["results"])
    else:checks.append({"name":"kernel-child-executed-report","passed":False,"reason":"no synthetic report; no retry"})
    checks.append({"name":"original-synthetic-bundle-unchanged","passed":(bundle/"Contents/version.txt").is_file() and (bundle/"Contents/version.txt").read_bytes()==b"ORIGINAL_SYNTHETIC_BUNDLE\n"})
    actual={"status":"not_generated"}
    try:
        actual_run=out/"actual-run";actual_run.mkdir(mode=0o700)
        original=Path("/Applications/ZCode.app")
        execs=[original/"Contents/MacOS/ZCode",*(original/("Contents/Frameworks/"+n+".app/Contents/MacOS/"+n) for n in HELPER_NAMES)]
        text,binding=compile_policy(actual_run,original_bundle=original,read_roots=PUBLIC_READ_ROOTS,executable_paths=execs)
        (out/"actual-target.sb").write_text(text);new_json(out/"actual-target-policy.json",binding)
        actual={"status":"generated_not_executed","path":"actual-target.sb","sha256":hashlib.sha256(text.encode()).hexdigest(),"exact_executable_count":len(execs)}
    except (ValueError,OSError) as e:actual={"status":"refused","error":str(e)}
    passed=sum(x["passed"] for x in checks)
    summary={"kind":"A","scope":"deny-default synthetic kernel fileguard + actual target preparation only",
             "status":"passed" if passed==len(checks) and code==0 else "failed",
             "started_at":started,"finished_at":now(),"kernel_started_at":kernel_started,"kernel_finished_at":kernel_finished,
             "actual_exit_code":code,"validator_assertion_count":validator_count, "validator_passed":sum(x["passed"] for x in checks[:validator_count]),
             "kernel_child_reported":report is not None,"kernel_assertion_count":report["total"] if report else 0,"kernel_passed":report["passed"] if report else 0,
             "assertion_count":len(checks),"passed":passed,"failed":len(checks)-passed,"checks":checks,
             "hostLaunchAllowed":False,"hostReady":False,"actual_target":actual,
             "network_attempted":False,"daily_profile_keychain_access_attempted":False,"host_started":False,
             "limitations":manifest["limitations"],"kernel_receipt_sha256":sha(out/"kernel-command.json")}
    new_json(out/"summary.json",summary)
    print(json.dumps({"event":"finished","started_at":started,"finished_at":summary["finished_at"],"actual_exit_code":code,
                      "status":summary["status"],"passed":passed,"total":len(checks),"actual_target":actual,"summary":str(out/"summary.json")}),flush=True)
    if not report:print("RAW_STDERR",repr((run/"stderr.raw").read_bytes()),flush=True)
    return 0 if summary["status"]=="passed" else 1


if __name__=="__main__":
    raise SystemExit(main())
