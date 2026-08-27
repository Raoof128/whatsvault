import os
from apps.mcp import server
from whatsvault.db import connection as C
from whatsvault.db import migrations as M


def test_no_forbidden_tool_registered():
    assert server.REGISTERED_TOOLS.isdisjoint(server.FORBIDDEN_TOOLS)


def test_expected_read_tools():
    assert server.REGISTERED_TOOLS == {
        "search", "get_messages", "list_chats", "get_message_status",
        "get_conversation_window", "list_templates",
    }


def test_all_tools_read_only():
    for name, a in server.TOOL_ANNOTATIONS.items():
        assert a["read_only_hint"] is True and a["open_world_hint"] is False


def test_handlers_require_token(tmp_path):
    import pytest
    v = C.open_db(str(tmp_path / "v.db"), os.urandom(32)); M.migrate(v, "vault")
    c = C.open_db(str(tmp_path / "c.db"), os.urandom(32)); M.migrate(c, "control")
    token, audit_key = "sekret", os.urandom(32)
    handlers = server.build_tool_handlers(v, c, token, audit_key)
    with pytest.raises(PermissionError):
        handlers["list_templates"](bearer="wrong")
    assert handlers["list_templates"](bearer=token)["status"] == "FEATURE_NOT_INITIALISED"
    row = c.execute("SELECT tool, args_hash FROM audit_log").fetchone()
    assert row["tool"] == "list_templates" and len(row["args_hash"]) == 64
