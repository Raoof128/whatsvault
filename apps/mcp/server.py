"""Loopback Streamable-HTTP MCP server (spec §5, ledger #18/#20/#24/#54).

Registers exactly the read tools, each token-authenticated (#19) and keyed-HMAC
audited (#21). The negative surface (§5.5) is asserted by CI against the plain
module constants below, so the guarantee is robust to MCP-SDK version churn. Live
Streamable-HTTP serving on 127.0.0.1 is Phase-2b-gated (ChatGPT connectivity)."""
import time

from whatsvault.mcp import audit, auth, reads

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


def build_tool_handlers(vault_conn, control_conn, token, audit_key) -> dict:
    """Auth+audit-wrapped read handlers, independent of the MCP SDK transport."""
    def guard(tool_name, fn):
        def handler(bearer=None, **kwargs):
            if not auth.require_token(bearer, token):
                raise PermissionError("AUTHORIZATION_MISSING")
            audit.record(control_conn, audit_key, actor="mcp", tool=tool_name,
                         args=kwargs, outcome="ok", now_ms=int(time.time() * 1000))
            return fn(**kwargs)
        return handler

    return {
        "search": guard("search", lambda q: reads.search(vault_conn, q)),
        "get_messages": guard("get_messages", lambda conversation_id, from_ms=None, to_ms=None, limit=50:
                              reads.get_messages(vault_conn, conversation_id, from_ms, to_ms, limit)),
        "list_chats": guard("list_chats", lambda query=None, limit=20: reads.list_chats(vault_conn, query, limit)),
        "get_message_status": guard("get_message_status", lambda message_id: reads.get_message_status(vault_conn, message_id)),
        "get_conversation_window": guard("get_conversation_window", lambda conversation_id, now_ms:
                                         reads.get_conversation_window(control_conn, conversation_id, now_ms)),
        "list_templates": guard("list_templates", lambda: reads.list_templates(control_conn)),
    }


def build_server(vault_conn, control_conn, token, audit_key, *, name="whatsvault"):  # pragma: no cover - 2b-gated
    from mcp.server.mcpserver import MCPServer
    from mcp.types import ToolAnnotations
    server = MCPServer(name)
    ann = ToolAnnotations(read_only_hint=True, open_world_hint=False, idempotent_hint=True)
    handlers = build_tool_handlers(vault_conn, control_conn, token, audit_key)
    for tool_name, handler in handlers.items():
        server.tool(name=tool_name, annotations=ann)(handler)
    return server
