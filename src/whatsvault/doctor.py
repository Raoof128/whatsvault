"""Vault integrity checks (spec §3.7 I5 + structural + SQLCipher integrity).
A doctor reconstructs evidence truth and repairs drift; it never preserves a
forged or future window value. Send-side invariants I2/I3/I4 are Phase 4."""
from whatsvault import ids


def advance_window(control_conn, conversation_id: str, incoming_provider_ms: int) -> int:
    """Live ingest path: monotonic MAX(existing, incoming). Never used by doctor."""
    row = control_conn.execute(
        "SELECT last_inbound_ms FROM conversation_windows WHERE conversation_id=?",
        (conversation_id,)).fetchone()
    existing = row[0] if row else 0
    new_val = max(existing, incoming_provider_ms)
    control_conn.execute(
        "INSERT INTO conversation_windows(conversation_id, last_inbound_ms) VALUES(?,?) "
        "ON CONFLICT(conversation_id) DO UPDATE SET last_inbound_ms=excluded.last_inbound_ms",
        (conversation_id, new_val))
    control_conn.commit()
    return new_val


def rebuild_window_from_evidence(vault_conn, control_conn, conversation_id: str) -> dict:
    """Doctor path: the window MUST equal the exact MAX over window-eligible inbound
    evidence. If the stored projection differs (e.g. a forged future value), repair it
    to the evidence truth and report drift."""
    (evidence_ms,) = vault_conn.execute(
        "SELECT COALESCE(MAX(ts_lower_ms), 0) FROM messages "
        "WHERE conversation_id=? AND direction='in' AND window_eligible=1",
        (conversation_id,)).fetchone()
    stored_row = control_conn.execute(
        "SELECT last_inbound_ms FROM conversation_windows WHERE conversation_id=?",
        (conversation_id,)).fetchone()
    stored_ms = stored_row[0] if stored_row else 0
    drift = stored_ms != evidence_ms
    if drift:
        control_conn.execute(
            "INSERT INTO conversation_windows(conversation_id, last_inbound_ms) VALUES(?,?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET last_inbound_ms=excluded.last_inbound_ms",
            (conversation_id, evidence_ms))
        control_conn.commit()
    return {"evidence_ms": evidence_ms, "stored_ms": stored_ms, "drift": drift}


def check_vault(vault_conn) -> list[dict]:
    findings: list[dict] = []

    bad = 0
    for (mid,) in vault_conn.execute("SELECT id FROM messages"):
        try:
            ids.validate("msg", mid)
        except ids.IdError:
            bad += 1
    findings.append({"check": "message_id_prefix", "ok": bad == 0,
                     "detail": f"{bad} message id(s) fail prefix/ULID validation"})

    ic = vault_conn.execute("PRAGMA integrity_check").fetchone()[0]
    findings.append({"check": "integrity_check", "ok": ic == "ok", "detail": ic})

    fk = vault_conn.execute("PRAGMA foreign_key_check").fetchall()
    findings.append({"check": "foreign_key_check", "ok": len(fk) == 0,
                     "detail": f"{len(fk)} foreign-key violation(s)"})

    cic = vault_conn.execute("PRAGMA cipher_integrity_check").fetchall()
    findings.append({"check": "cipher_integrity_check", "ok": len(cic) == 0,
                     "detail": f"{len(cic)} encrypted-page HMAC failure(s)"})

    return findings
