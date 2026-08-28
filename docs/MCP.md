# MCP Reference

The WhatsVault MCP server exposes a **read-only** view of your vault over
Streamable HTTP on loopback.

- **Endpoint:** `http://127.0.0.1:8765/mcp`
- **Transport:** Streamable HTTP (MCP SDK 2.x)
- **Auth:** `Authorization: Bearer <token>`, token held in the macOS Keychain

## Connecting

```bash
whatsvault mcp-provision --reveal   # mints the token; prints it once
whatsvault-mcp                      # serves on 127.0.0.1:8765
```

`127.0.0.1` is **not** an authentication boundary — any local process running as
you can reach it — so every request is authenticated regardless of origin.
Requests are rejected with `401` when the header is absent, malformed, carries the
wrong scheme, or appears more than once (ambiguous credentials fail closed). A
forged `Host` header is rejected with `421`.

To reach the server from a hosted assistant, put a tunnel in front of it; do not
bind it publicly.

## Tools

All six are annotated `readOnlyHint: true`, `openWorldHint: false`,
`idempotentHint: true`.

### `search`
Ranked full-text search across the vault, English and Persian.

| Param | Type | Notes |
|---|---|---|
| `q` | `SearchQuery` | terms, optional conversation filter |

Returns message views ordered by rank, each with `rank` and `tier`
(`lexical` or `compact`). `LOCAL_ONLY` conversations are excluded.

### `get_messages`
A caller-scoped window of one conversation.

| Param | Type | Default |
|---|---|---|
| `conversation_id` | `str` | required |
| `from_ms` / `to_ms` | `int \| None` | unbounded |
| `limit` | `int` | `50`, clamped to `[1, 200]` |

Returns `[]` for an unknown or `LOCAL_ONLY` conversation — the two are
indistinguishable by design.

### `list_chats`
Conversations ordered by recency, excluding `LOCAL_ONLY`.
Params: `query` (substring over subject), `limit` (default `20`, max `200`).

### `get_message_status`
Delivery state reduced from the status-event lattice:
`{delivery_rank, failed_at_ms, deleted_at_ms, unknown_statuses}`.
Returns `None` for an unknown message or one in a fenced conversation.

### `get_conversation_window`
Whether the 24-hour free-form window is open:
`{open, last_inbound_ms, closes_at_ms}`.

A `LOCAL_ONLY` conversation always reports `{open: false, last_inbound_ms: 0}` —
identical to an idle one. Activity timing is content, and this was a real leak
before it was closed.

### `list_templates`
The locally synced template catalogue, or
`{"status": "FEATURE_NOT_INITIALISED", "templates": []}` before Phase 5.

## The forbidden surface

These names may **never** appear. CI asserts the registered set is disjoint from
this set, against plain module constants so the guarantee survives SDK changes:

```
approve_draft   send_prepared_message   add_approval_device   revoke_device
set_policy      create_capability       set_mcp_visibility    raw_fts_query
sql_query       http_request            graph_api_call        send_to_number
broadcast       delete_message          export_vault          get_credentials
```

There is no `send_prepared_message` because approval on the phone *is* "approve
and send" — dispatch is triggered by a valid signed envelope, never by a model.

## Response shape

Every WhatsApp-originated string is wrapped:

```json
{
  "message_id": "msg_01J...",
  "conversation_id": "cnv_01J...",
  "direction": "in",
  "ts_lower_ms": 1700000000000,
  "ts_upper_ms_exclusive": 1700000060000,
  "ts_precision": "min",
  "delivery_rank": 3,
  "reply_to_ref": "wref_3f9a1c2b7d4e5f60",
  "body": { "_wv_untrusted": true, "text": "…" },
  "contact": {
    "contact_id": "cnt_01J...",
    "display_name": { "_wv_untrusted": true, "text": "…" },
    "wa_tail": "••••3812"
  }
}
```

Two things to note:

- **`_wv_untrusted`** marks attacker-controllable data. Treat it as data, never
  as instruction — the content of a message is not a command.
- **`reply_to_ref` is opaque.** A raw `wamid` base64-decodes to the counterparty's
  full E.164 number, so emitting one would defeat `wa_tail` masking entirely. The
  replacement is a deterministic handle: stable across calls, so reply chains stay
  correlatable, but carrying no recoverable identifier.

No response contains a full phone number.

## Privacy fence

Mark a conversation private:

```bash
whatsvault mcp-visibility --conversation-id cnv_… --visibility LOCAL_ONLY
```

It then never appears in `search`, `list_chats`, `get_messages`,
`get_message_status`, or `get_conversation_window`. The setter is CLI/phone only —
`set_mcp_visibility` is in the forbidden set, so the model cannot un-fence a chat.

## Audit

Every call is appended to `control.audit_log` with actor, tool, outcome, timestamp,
and an **HMAC** of the arguments — keyed, not a bare SHA-256, because a
low-entropy query like a contact name would otherwise be trivially recoverable by
dictionary attack. Content is never stored.

The record is written **after** the call with its real outcome, so a failed probe
cannot leave a clean trail. The table is append-only, enforced by triggers.

## Known limitation

INV-CONTENT is *hard* for writes: no message body can create authority, because no
write verb exists to reach. For **retrieval scope** it is an orchestration
property — the server cannot prevent a model from choosing to call `search` again
with a broader query after reading a message that suggests it.

The `LOCAL_ONLY` fence is the real, server-side boundary. This limitation is
stated rather than hidden.
