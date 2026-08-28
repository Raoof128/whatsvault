"""whatsvault CLI command handlers (ledger #56). Every verb is an OPERATIONS verb —
inspect, recover, administer. NONE creates approval authority: there is no approve/send/
sign/mint verb, and no handler drives the sender write path or the capability grant store.
Approval authority is the phone's Secure Enclave signature (Phase 4)."""
from .. import doctor
from ..approval import devices, reconcile
from ..crypto import keystore
from ..mcp import audit, auth
from ..ops import health

FORBIDDEN_VERBS = frozenset({
    "approve", "send", "sign", "dispatch", "mint_capability", "create_capability",
    "send_message", "get_credentials", "export_vault", "prepare",
})


class Ctx:
    def __init__(self, vault_conn, control_conn, ks=None):
        self.vault = vault_conn
        self.control = control_conn
        self.ks = ks                 # optional: only the provisioning/doctor paths use it


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


def cmd_doctor(ctx, args):
    return {"ok": True, "vault": doctor.check_vault(ctx.vault),
            "search": doctor.check_search(ctx.vault), "ingest": doctor.check_ingest(ctx.vault),
            "mcp": doctor.check_mcp(ctx.vault, ctx.control, ks=getattr(ctx, "ks", None))}


def cmd_mcp_provision(ctx, args):
    """Create the MCP daemon's Keychain keys if absent. Never rotates: replacing
    the token would silently break an already-configured connector, and replacing
    the audit key would orphan every existing audit HMAC.

    The token is withheld unless --reveal is passed, because cli.main prints
    results to stdout and the launchd units capture stdout to a log file.
    """
    if ctx.ks is None:
        return {"ok": False, "error": "no keystore available on this context"}
    provisioned, already = [], []
    for name in (auth.TOKEN_KEY_NAME, audit.AUDIT_KEY_NAME):
        try:
            ctx.ks.require(name, 32)
            already.append(name)
        except keystore.KeyMissing:
            ctx.ks.provision(name, 32)
            provisioned.append(name)
        except Exception as exc:
            # e.g. a present-but-wrong-length key. Report it; never overwrite —
            # provisioning over a corrupt key destroys evidence of the corruption.
            return {"ok": False, "error": f"{name}: {type(exc).__name__}: {exc}"}
    out = {"ok": True, "provisioned": provisioned, "already_present": already,
           "endpoint": "http://127.0.0.1:8765/mcp"}
    if args.get("reveal"):
        out["token"] = ctx.ks.require(auth.TOKEN_KEY_NAME, 32).hex()
    else:
        out["note"] = ("token withheld; re-run with --reveal to print it "
                       "(avoid doing so where stdout is captured to a log)")
    return out


def cmd_health(ctx, args):
    return health.status(ctx.vault, ctx.control)


def cmd_devices_list(ctx, args):
    return {"ok": True, "devices": _rows(ctx.control.execute(
        "SELECT id, name, status, key_algorithm FROM approval_devices"))}


def cmd_devices_revoke(ctx, args):
    devices.revoke(ctx.control, args["device_id"])
    return {"ok": True, "revoked": args["device_id"]}


def cmd_dlq_list(ctx, args):
    return {"ok": True, "dlq": _rows(ctx.vault.execute(
        "SELECT id, failure_class, recipient_key_id, first_seen_ms FROM ingest_dlq"))}


def cmd_dlq_show(ctx, args):
    row = ctx.vault.execute(
        "SELECT id, failure_class, failure_code, pipeline_stage, recipient_key_id, crypto_version, "
        "ciphertext_sha256, sanitised_detail FROM ingest_dlq WHERE id=?", (args["dlq_id"],)).fetchone()
    return {"ok": row is not None, "row": dict(row) if row else None}


def cmd_keys_list(ctx, args):
    return {"ok": True, "keys_referenced_by_dlq": [r[0] for r in ctx.vault.execute(
        "SELECT DISTINCT recipient_key_id FROM ingest_dlq WHERE recipient_key_id IS NOT NULL")]}


def cmd_templates_list(ctx, args):
    return {"ok": True, "templates": _rows(ctx.control.execute(
        "SELECT template_id, name, language, status FROM templates"))}


def cmd_reconcile_list(ctx, args):
    return {"ok": True, "candidates": _rows(ctx.control.execute(
        "SELECT id, wamid, status, state FROM reconciliation_candidates WHERE state='POSSIBLE_MATCH'"))}


def cmd_reconcile_resolve(ctx, args):
    r = reconcile.resolve(ctx.control, args["candidate_id"], decision=args.get("decision") or "resolve")
    return {"ok": True, **r}


def cmd_scheduler_list(ctx, args):
    return {"ok": True, "jobs": _rows(ctx.control.execute(
        "SELECT job_id, conversation_id, generation_mode, enabled FROM scheduled_jobs"))}


def _set_enabled(ctx, job_id, enabled):
    ctx.control.execute("UPDATE scheduled_jobs SET enabled=? WHERE job_id=?", (enabled, job_id))
    ctx.control.commit()
    return {"ok": True, "job_id": job_id, "enabled": enabled}


def cmd_scheduler_enable(ctx, args):
    return _set_enabled(ctx, args["job_id"], 1)


def cmd_scheduler_disable(ctx, args):
    return _set_enabled(ctx, args["job_id"], 0)


COMMANDS = {
    "doctor": cmd_doctor,
    "mcp-provision": cmd_mcp_provision,
    "health": cmd_health,
    "devices-list": cmd_devices_list,
    "devices-revoke": cmd_devices_revoke,
    "dlq-list": cmd_dlq_list,
    "dlq-show": cmd_dlq_show,
    "keys-list": cmd_keys_list,
    "templates-list": cmd_templates_list,
    "reconcile-list": cmd_reconcile_list,
    "reconcile-resolve": cmd_reconcile_resolve,
    "scheduler-list": cmd_scheduler_list,
    "scheduler-enable": cmd_scheduler_enable,
    "scheduler-disable": cmd_scheduler_disable,
}
