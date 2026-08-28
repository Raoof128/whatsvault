"""Loopback Streamable-HTTP MCP server (spec §5, ledger #18/#20/#24/#54).

Registers exactly the read tools, each token-authenticated (#19) and keyed-HMAC
audited (#21). The negative surface (§5.5) is asserted by CI against the plain
module constants below, so the guarantee is robust to MCP-SDK version churn.

Auth is enforced by BearerAuthMiddleware at the transport, never as a tool
argument (#19). The app is built and asserted in tests; only the uvicorn serve
call in main() is uncovered."""
import functools
import inspect
import time

from whatsvault.mcp import audit, auth as auth_mod, reads
from whatsvault.mcp.http_auth import BearerAuthMiddleware

#18: loopback bind + the port the launchd unit and the tunnel client both target.
HOST = "127.0.0.1"
PORT = 8765
MCP_PATH = "/mcp"

# INV-CONTENT (#54): two strengths, honestly separated.
INV_CONTENT_HARD = ("Retrieved content cannot create write authority, create or modify policy, "
                    "access credentials, or bypass server-side ACLs.")
INV_CONTENT_ORCHESTRATION = ("Retrieved content should not influence the model to widen retrieval "
                             "scope or invoke additional read tools; not cryptographically enforceable "
                             "absent separately authorised retrieval scopes.")
# #24 disclosure boundary.
OPENAI_DISCLOSURE = ("MCP returns only the minimum selected excerpts required; using ChatGPT with "
                     "WhatsVault intentionally discloses those plaintext excerpts to the LLM service.")

REGISTERED_TOOLS = frozenset({
    "search", "get_messages", "list_chats", "get_message_status",
    "get_conversation_window", "list_templates",
})
FORBIDDEN_TOOLS = frozenset({
    "approve_draft", "send_prepared_message", "add_approval_device", "revoke_device",
    "set_policy", "create_capability", "set_mcp_visibility", "raw_fts_query", "sql_query",
    "http_request", "graph_api_call", "send_to_number", "broadcast", "delete_message",
    "export_vault", "get_credentials",
})
# #20: read-only tools; the audit append is documented as outside the tool's logical environment.
_READ = {"read_only_hint": True, "open_world_hint": False, "idempotent_hint": True,
         "audit_exception": "appends to control.audit_log; no domain/message-state mutation"}
TOOL_ANNOTATIONS = {name: dict(_READ) for name in REGISTERED_TOOLS}


def _json_safe(value):
    """Audit args are HMACed over canonical JSON; coerce non-JSON values (e.g. a
    SearchQuery) so hashing a structured query cannot raise mid-request."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return repr(value)


def build_tool_handlers(vault_conn, control_conn, audit_key) -> dict:
    """Audited read handlers, independent of the MCP SDK transport.

    Authentication is NOT here — it is enforced by BearerAuthMiddleware on the
    transport (#19). A `bearer` parameter on these functions would be published
    in each tool's JSON schema, i.e. the server would be asking the model to
    supply the secret.
    """
    def guard(tool_name, fn):
        @functools.wraps(fn)          # keeps the real signature for schema generation
        def handler(*args, **kwargs):
            try:
                bound = inspect.signature(fn).bind(*args, **kwargs)
                recorded = _json_safe(dict(bound.arguments))
            except TypeError:
                recorded = {"_wv_unbindable": True}
            outcome = "ok"
            try:
                return fn(*args, **kwargs)
            except BaseException as exc:                # audit the failure, then re-raise
                outcome = f"error:{type(exc).__name__}"
                raise
            finally:
                # Recorded AFTER the call so the outcome is the real one: a probe
                # that errors must not leave a clean trail (§5.8).
                audit.record(control_conn, audit_key, actor="mcp", tool=tool_name,
                             args=recorded, outcome=outcome, now_ms=int(time.time() * 1000))
        return handler

    return {
        "search": guard("search", lambda q: reads.search(vault_conn, q)),
        "get_messages": guard("get_messages", lambda conversation_id, from_ms=None, to_ms=None, limit=50:
                              reads.get_messages(vault_conn, conversation_id, from_ms, to_ms, limit)),
        "list_chats": guard("list_chats", lambda query=None, limit=20: reads.list_chats(vault_conn, query, limit)),
        "get_message_status": guard("get_message_status", lambda message_id: reads.get_message_status(vault_conn, message_id)),
        "get_conversation_window": guard("get_conversation_window", lambda conversation_id, now_ms:
                                         reads.get_conversation_window(control_conn, vault_conn, conversation_id, now_ms)),
        "list_templates": guard("list_templates", lambda: reads.list_templates(control_conn)),
    }


def transport_security_settings(port: int = PORT):
    """DNS-rebinding protection. Binding loopback is not sufficient on its own —
    a hostile page can still drive a browser at 127.0.0.1 unless Host is pinned."""
    from mcp.server.transport_security import TransportSecuritySettings
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[f"127.0.0.1:{port}", "127.0.0.1", f"localhost:{port}", "localhost"],
        allowed_origins=[f"http://127.0.0.1:{port}", f"http://localhost:{port}"],
    )


def build_mcp_server(vault_conn, control_conn, audit_key, *, name="whatsvault"):
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations
    server = MCPServer(name)
    ann = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
    for tool_name, handler in build_tool_handlers(vault_conn, control_conn, audit_key).items():
        server.tool(name=tool_name, annotations=ann)(handler)
    return server


def build_app(vault_conn, control_conn, token, audit_key, *, name="whatsvault", port=PORT):
    """The full ASGI app: token gate in front of the Streamable-HTTP transport."""
    mcp_server = build_mcp_server(vault_conn, control_conn, audit_key, name=name)
    inner = mcp_server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        transport_security=transport_security_settings(port),
        host=HOST,
    )
    return BearerAuthMiddleware(inner, token)


def main():  # pragma: no cover - process entrypoint; see test_main_symbols_resolve
    """Serve the loopback MCP. Mirrors cli.main's production wiring exactly."""
    import uvicorn
    from whatsvault.crypto.keystore import KeyringKeyStore
    from whatsvault.db import connection as C
    from whatsvault.ops import fsperms, paths
    fsperms.harden_umask()
    p = paths.from_env()
    ks = KeyringKeyStore()
    token = ks.require(auth_mod.TOKEN_KEY_NAME, 32).hex()
    audit_key = ks.require(audit.AUDIT_KEY_NAME, 32)
    app = build_app(C.open_existing("vault", p.vault_db, ks),
                    C.open_existing("control", p.control_db, ks),
                    token, audit_key)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
