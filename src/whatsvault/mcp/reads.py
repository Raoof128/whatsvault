"""MCP read query layer (spec §5) — composes search + present, and enforces the
hard LOCAL_ONLY privacy fence (#23). Every result is redacted and untrusted-wrapped;
LOCAL_ONLY conversations never leave the boundary. No write verb exists here."""
from ..ingest.status import reduce_status
from ..search.query import run as _search_run
from . import acl
from . import present

WINDOW_MS = 24 * 3600 * 1000
MAX_LIMIT = 200


def _contact(vault_conn, contact_id):
    if not contact_id:
        return None
    return vault_conn.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()


def _view(vault_conn, msg_row):
    return present.message_view(msg_row, _contact(vault_conn, msg_row["sender_contact_id"]))


def search(vault_conn, q) -> list:
    local = acl.local_only_ids(vault_conn)
    out = []
    for r in _search_run(vault_conn, q):
        if r.get("conversation_id") in local:
            continue
        m = vault_conn.execute("SELECT * FROM messages WHERE id=?", (r["message_id"],)).fetchone()
        if not m:
            continue
        v = _view(vault_conn, m)
        v["rank"] = r["rank"]
        v["tier"] = r["tier"]
        out.append(v)
    return out


def get_messages(vault_conn, conversation_id, from_ms=None, to_ms=None, limit=50) -> list:
    vis = vault_conn.execute("SELECT mcp_visibility FROM conversations WHERE id=?",
                             (conversation_id,)).fetchone()
    if not vis or vis[0] == "LOCAL_ONLY":
        return []
    preds, params = ["conversation_id=?"], [conversation_id]
    if from_ms is not None:                       # interval overlap
        preds.append("ts_upper_ms_exclusive > ?"); params.append(from_ms)
    if to_ms is not None:
        preds.append("ts_lower_ms < ?"); params.append(to_ms)
    sql = "SELECT * FROM messages WHERE " + " AND ".join(preds) + " ORDER BY ts_lower_ms, id LIMIT ?"
    rows = vault_conn.execute(sql, params + [min(limit, MAX_LIMIT)]).fetchall()
    return [_view(vault_conn, m) for m in rows]


def list_chats(vault_conn, query=None, limit=20) -> list:
    preds = ["mcp_visibility != 'LOCAL_ONLY'"]
    params = []
    if query:
        preds.append("subject LIKE ?"); params.append(f"%{query}%")
    sql = ("SELECT id, type, subject, last_message_ms FROM conversations WHERE "
           + " AND ".join(preds) + " ORDER BY last_message_ms DESC LIMIT ?")
    rows = vault_conn.execute(sql, params + [min(limit, MAX_LIMIT)]).fetchall()
    return [{"conversation_id": r["id"], "type": r["type"],
             "subject": present.untrusted(r["subject"]), "last_message_ms": r["last_message_ms"]}
            for r in rows]


def get_message_status(vault_conn, message_id):
    m = vault_conn.execute("SELECT wamid, conversation_id FROM messages WHERE id=?",
                           (message_id,)).fetchone()
    if not m:
        return None
    if m["conversation_id"] in acl.local_only_ids(vault_conn):
        return None
    if not m["wamid"]:
        return {"delivery_rank": 0, "failed_at_ms": None, "deleted_at_ms": None, "unknown_statuses": []}
    events = [{"status": r["status"], "provider_ts_ms": r["provider_ts_ms"]}
              for r in vault_conn.execute(
                  "SELECT status, provider_ts_ms FROM message_status_events WHERE wamid=?", (m["wamid"],)).fetchall()]
    return reduce_status(events)


def get_conversation_window(control_conn, conversation_id, now_ms) -> dict:
    row = control_conn.execute("SELECT last_inbound_ms FROM conversation_windows WHERE conversation_id=?",
                               (conversation_id,)).fetchone()
    last = row[0] if row else 0
    closes = last + WINDOW_MS
    return {"open": bool(last > 0 and now_ms < closes), "last_inbound_ms": last, "closes_at_ms": closes}


def list_templates(control_conn) -> dict:
    exists = control_conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='templates'").fetchone()
    if not exists:
        return {"status": "FEATURE_NOT_INITIALISED", "templates": []}
    rows = control_conn.execute(
        "SELECT template_id, name, language, category, status FROM templates").fetchall()
    return {"status": "OK", "templates": [dict(r) for r in rows]}
