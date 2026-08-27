"""Numbered, transactional migration runner. This package's __init__ IS the
runner (a sibling migrations.py would be shadowed by this package directory);
the numbered SQL assets live under vault/ and control/ within this package.

Each migration runs inside a BEGIN/COMMIT and bumps PRAGMA user_version
atomically; a failure rolls back and leaves the version unchanged."""
from importlib import resources

MIGRATIONS: dict[str, list[tuple[int, str]]] = {
    "vault": [(1, "vault/0001_initial.sql"), (2, "vault/0002_import_provenance.sql"), (3, "vault/0003_search.sql"), (4, "vault/0004_mcp_visibility.sql")],
    "control": [(1, "control/0001_initial.sql")],
}


def user_version(conn) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _read_asset(relpath: str) -> str:
    return resources.files("whatsvault.db.migrations").joinpath(relpath).read_text(encoding="utf-8")


def migrate(conn, lane: str) -> int:
    if lane not in MIGRATIONS:
        raise ValueError(f"unknown migration lane: {lane!r}")
    for version, relpath in MIGRATIONS[lane]:
        if version <= user_version(conn):
            continue
        sql = _read_asset(relpath)
        script = f"BEGIN;\n{sql}\nPRAGMA user_version = {version};\nCOMMIT;"
        try:
            conn.executescript(script)
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise
    return user_version(conn)
