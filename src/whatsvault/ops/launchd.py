"""launchd plist validator (ledger #57). Confirms each service has crash-restart
(KeepAlive), starts at load, logs under a logs/ dir, and carries NO inline secret —
credentials live in the Keychain, never in a plist (only whatsvault-meta loads the
Meta token, at runtime)."""
import plistlib
import re

_REQUIRED = ["Label", "ProgramArguments", "RunAtLoad", "KeepAlive", "StandardOutPath", "StandardErrorPath"]
_TOKENISH_KEY = re.compile(r"(?i)(token|secret|password|api[_-]?key|private)")
_HEXKEY = re.compile(r"^[0-9a-fA-F]{32,}$")


def _looks_secret(key, value) -> bool:
    if not isinstance(value, str):
        return False
    if _TOKENISH_KEY.search(str(key)):
        return True
    return bool(_HEXKEY.match(value))


def _scan(obj, key=""):
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            hits += _scan(v, k)
    elif isinstance(obj, list):
        for x in obj:
            hits += _scan(x, key)
    elif _looks_secret(key, obj):
        hits.append(key)
    return hits


def validate(plist_path) -> list:
    with open(plist_path, "rb") as f:
        pl = plistlib.load(f)
    findings = [{"check": f"has_{r}", "ok": r in pl, "detail": plist_path} for r in _REQUIRED]
    findings.append({"check": "keepalive_true", "ok": pl.get("KeepAlive") is True, "detail": "crash restart"})
    findings.append({"check": "runatload_true", "ok": pl.get("RunAtLoad") is True, "detail": "start at load"})
    secrets = _scan(pl)
    findings.append({"check": "no_inline_secret", "ok": len(secrets) == 0, "detail": str(secrets)})
    out, err = pl.get("StandardOutPath", ""), pl.get("StandardErrorPath", "")
    findings.append({"check": "logs_under_logs_dir", "ok": "/logs/" in out and "/logs/" in err, "detail": out})
    return findings
