"""Run in an isolated subprocess; never contact AWS or a database."""
import hashlib
import importlib
import json
from pathlib import Path
import socket
import ssl
import sys


def is_ipv6_capability_check(root, event, args, caller):
    return (event == "socket.bind" and len(args) == 2
            and args[1] == ("::1", 0)
            and args[0].family == socket.AF_INET6
            and args[0].type == socket.SOCK_STREAM
            and caller.f_globals.get("__name__") == "urllib3.util.connection"
            and caller.f_code.co_name == "_has_ipv6"
            and Path(caller.f_code.co_filename).resolve()
            == root / "urllib3/util/connection.py")


def probe(root, handlers):
    root = Path(root).resolve()
    sys.path.insert(0, str(root))
    attempts = []
    capability_checks = []

    def block_network(event, args):
        if event.startswith("socket.") and event != "socket.__new__":
            if is_ipv6_capability_check(root, event, args, sys._getframe(1)):
                capability_checks.append("urllib3 IPv6 loopback bind on port 0")
                return
            attempts.append(event)
            # Capture attribution now: import helpers can catch the rejection.
            # Omit source lines, frame locals and socket arguments/addresses.
            stack = []
            frame = sys._getframe(1)
            while frame is not None:
                stack.append({"module": frame.f_globals.get("__name__", "<unknown>"),
                              "function": frame.f_code.co_name,
                              "file": frame.f_code.co_filename, "line": frame.f_lineno})
                frame = frame.f_back
            print("Blocked network operation: " + json.dumps({"operation": event,
                  "stack": stack}), file=sys.stderr, flush=True)
            raise RuntimeError("Network access attempted during package verification")

    # Audit hooks catch DNS and socket operations even if imported code catches
    # the raised exception. This process is disposable: the hook is permanent.
    sys.addaudithook(block_network)
    modules = {}
    for handler in handlers:
        module_name, entry = handler.rsplit(".", 1)
        module = importlib.import_module(module_name)
        if not callable(getattr(module, entry)):
            raise ValueError(f"Handler is not callable: {handler}")
        modules[module_name] = module
    modules["psycopg2._psycopg"] = importlib.import_module("psycopg2._psycopg")
    for name, module in modules.items():
        if not Path(module.__file__).resolve().is_relative_to(root):
            raise ValueError(f"Module loaded outside archive: {name}")
    sql = (root / "sql/monthly_summary.sql").read_bytes()
    if not sql.decode("utf-8").strip():
        raise ValueError("Bundled SQL is empty")
    ca = root / "certs/global-bundle.pem"
    context = ssl.create_default_context(cafile=str(ca))
    if not context.get_ca_certs():
        raise ValueError("CA bundle contains no usable trust anchors")
    if attempts:
        raise RuntimeError(f"Network operations attempted: {attempts}")
    return {"handlers_imported": handlers, "psycopg_native_loaded": True,
            "sql_sha256": hashlib.sha256(sql).hexdigest(),
            "ca_sha256": hashlib.sha256(ca.read_bytes()).hexdigest(),
            "ca_loaded": True, "network_attempts": attempts,
            "local_capability_checks": capability_checks}


if __name__ == "__main__":
    print(json.dumps(probe(sys.argv[1], json.loads(sys.argv[2]))))
