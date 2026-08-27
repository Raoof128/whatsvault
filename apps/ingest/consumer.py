"""Pull-consumer ingest loop (spec §7, ledger #2/#35/#40/#41, INV-ACK).

Per queue message: decrypt -> Mac-side fan-out -> per atomic child a single implicit
transaction (dedup-ledger insert + domain writes) -> COMMIT -> post-commit projection
(#40) + search index (#35). ACK only after ALL children durable (partial commits are
absorbed by the dedup ledger on redelivery). Decrypt failures split transient (no ACK,
redeliver) / poison (DLQ + ACK) / systemic (circuit-break, no ACK) by KEY HEALTH."""
import hashlib
import json

from whatsvault import ids
from whatsvault.crypto import sealed
from whatsvault.doctor import advance_window
from whatsvault.ingest import dlq, normalise
from whatsvault.search import index


def _get_account(v, pnid):
    row = v.execute("SELECT id FROM accounts WHERE phone_number_id=?", (pnid,)).fetchone()
    if row:
        return row[0]
    aid = ids.new_id("acc")
    v.execute("INSERT INTO accounts(id, phone_number_id) VALUES(?,?)", (aid, pnid))
    return aid


def _get_contact(v, wa_id, name):
    row = v.execute("SELECT id FROM contacts WHERE wa_id=?", (wa_id,)).fetchone()
    if row:
        return row[0]
    cid = ids.new_id("cnt")
    v.execute("INSERT INTO contacts(id, wa_id, display_name) VALUES(?,?,?)", (cid, wa_id, name))
    return cid


def _get_conversation(v, account_id, wa_chat_id):
    row = v.execute("SELECT id FROM conversations WHERE account_id=? AND wa_chat_id=?",
                    (account_id, wa_chat_id)).fetchone()
    if row:
        return row[0]
    cid = ids.new_id("cnv")
    v.execute("INSERT INTO conversations(id, account_id, type, wa_chat_id) VALUES(?,?,'dm',?)",
              (cid, account_id, wa_chat_id))
    return cid


def _apply_rows(v, rows):
    fam = rows["family"]
    if fam in ("MESSAGE_INBOUND", "MESSAGE_ECHO"):
        c, m = rows["contact"], rows["message"]
        account_id = _get_account(v, m["phone_number_id"])
        contact_id = _get_contact(v, c["wa_id"], c["name"])
        conv_id = _get_conversation(v, account_id, c["wa_id"])
        msg_id = ids.new_id("msg")
        v.execute(
            "INSERT INTO messages(id, account_id, conversation_id, sender_contact_id, direction, "
            "ts_lower_ms, ts_upper_ms_exclusive, ts_precision, type, text_original, origin, "
            "window_eligible, wamid) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (msg_id, account_id, conv_id, contact_id, m["direction"], m["ts_lower_ms"],
             m["ts_upper_ms_exclusive"], m["ts_precision"], m["type"], m["text_original"],
             m["origin"], m["window_eligible"], m["wamid"]))
        return {"conversation_id": conv_id, "message_id": msg_id,
                "text": m["text_original"], "provider_ms": m["ts_lower_ms"]}
    if fam == "MESSAGE_STATUS":
        s = rows["status"]
        v.execute("INSERT INTO message_status_events(id, wamid, status, provider_ts_ms, recipient_id) "
                  "VALUES(?,?,?,?,?)", (ids.new_id("evt"), s["wamid"], s["status"],
                                        s["provider_ts_ms"], s["recipient_id"]))
        return {}
    return {}  # SYSTEM/HISTORY/UNKNOWN -> ingest_events only (#42)


def _provider_ts(rows):
    if "message" in rows:
        return rows["message"]["ts_lower_ms"]
    if "status" in rows:
        return rows["status"]["provider_ts_ms"]
    return None


def _process_payload(pt, v, c, now_ms, fault):
    for atom in normalise.split_webhook(json.loads(pt)):
        fam, key = normalise.semantic_key(atom)
        rows = normalise.to_rows(atom)
        raw = json.dumps(atom.get("raw"), sort_keys=True, ensure_ascii=False).encode("utf-8")
        try:
            cur = v.execute(
                "INSERT OR IGNORE INTO ingest_events(id, provider, external_event_id, "
                "semantic_event_key, family, provider_ts_ms, received_at_ms, raw_payload_sha256, "
                "raw_payload, parser_version) VALUES(?,?,?,?,?,?,?,?,?,1)",
                (ids.new_id("evt"), "meta", (atom.get("raw") or {}).get("id"), key, fam,
                 _provider_ts(rows), now_ms, hashlib.sha256(raw).hexdigest(), raw))
            if cur.rowcount == 0:
                v.commit()          # duplicate -> deduped-as-seen
                continue
            applied = _apply_rows(v, rows)
            v.commit()
        except Exception:
            v.rollback()
            raise
        if fam == "MESSAGE_INBOUND" and applied.get("conversation_id"):
            advance_window(c, applied["conversation_id"], applied["provider_ms"])   # #40
            try:
                index.index_message(v, applied["message_id"], applied["text"])       # #35
            except Exception:
                pass                                                                  # never block ACK
        if fault:
            fault()
    return True


def drain_once(queue, vault_conn, control_conn, key_lookup, *, key_health, now_ms,
               _fault_after_commit=None, max_lease=32) -> dict:
    if dlq.state(vault_conn) == "OPEN":
        return {"circuit": "OPEN", "leased": 0, "acked": 0}
    leased = queue.lease(max_lease)
    to_ack = []
    counts = {"leased": len(leased), "poison": 0, "transient": 0, "systemic": 0, "durable": 0}
    for lm in leased:
        try:
            pt, hdr = sealed.open_sealed(lm.body, key_lookup)
            key_health.add(hdr["recipient_key_id"])
        except sealed.KeyUnavailable:
            counts["transient"] += 1
            queue.nack([lm.lease_id])
            continue
        except sealed.BadEnvelope:
            counts["poison"] += 1
            dlq.quarantine(vault_conn, lm.body, failure_class="POISON_MALFORMED",
                           failure_code="bad_envelope", pipeline_stage="decrypt",
                           detail="stage=decrypt", now_ms=now_ms)
            to_ack.append(lm.lease_id)
            continue
        except sealed.AeadAuthFailed as exc:
            try:
                key_id = sealed.parse_header(lm.body)["recipient_key_id"]
            except sealed.BadEnvelope:
                key_id = None
            healthy = key_id in key_health
            cls = dlq.classify_decrypt_error(exc, key_healthy=healthy)
            if cls == "AEAD_AUTH_FAILED_ISOLATED":
                counts["poison"] += 1
                dlq.quarantine(vault_conn, lm.body, failure_class=cls, failure_code="aead",
                               pipeline_stage="decrypt", detail="stage=decrypt", now_ms=now_ms)
                to_ack.append(lm.lease_id)
                continue
            counts["systemic"] += 1
            dlq.trip(vault_conn, f"systemic decrypt failure key={key_id}", now_ms)
            break   # stop leasing; leave this message leased (no ACK)
        try:
            if _process_payload(pt, vault_conn, control_conn, now_ms, _fault_after_commit):
                to_ack.append(lm.lease_id)
                counts["durable"] += 1
        except Exception:
            counts["transient"] += 1
            queue.nack([lm.lease_id])          # partial commit is absorbed by the dedup ledger on retry
    queue.ack(to_ack)
    counts["acked"] = len(to_ack)
    counts["circuit"] = dlq.state(vault_conn)
    return counts
