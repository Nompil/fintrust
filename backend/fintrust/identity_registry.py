"""Atomic local identity registry access shared by HTTP governance and enrollment.
This is a single-host credential store, not enterprise authentication.
"""
import contextlib,json,os,threading,time,uuid
from pathlib import Path
LOCK=threading.RLock()
_local=threading.local()
@contextlib.contextmanager
def locked_registry(path):
    path=Path(path).resolve()
    with LOCK:
        held=getattr(_local,'held',set())
        if str(path) in held:
            yield
            return
        with open(str(path)+'.lock','a+b') as lock:
            lock.seek(0)
            if not lock.read(1):lock.write(b'0');lock.flush()
            deadline=time.monotonic()+5
            while True:
                try:
                    lock.seek(0)
                    if os.name=='nt':
                        import msvcrt
                        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
                    else:
                        import fcntl
                        fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic()>deadline:raise RuntimeError('Identity registry busy') from None
                    time.sleep(.02)
            _local.held=held|{str(path)}
            try:yield
            finally:
                _local.held=held;lock.seek(0)
                if os.name=='nt':msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
                else:fcntl.flock(lock.fileno(),fcntl.LOCK_UN)
def read_registry():
    path=os.getenv('FINTRUST_AUTH_FILE')
    if not path:raise PermissionError('Identity registry unavailable')
    with locked_registry(path):return json.loads(Path(path).read_text(encoding='utf8'))
def write_registry(path,data):
    path=Path(path);temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with open(temp,'x',encoding='utf8') as f:
            if os.name!='nt':os.chmod(temp,0o600)
            json.dump(data,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()
def user_id(record):
    # Legacy subjects remain stable; display-name/role edits cannot change this ID.
    return record.get('user_id') or str(uuid.uuid5(uuid.NAMESPACE_URL,'fintrust-local-user:'+record['subject']))
