# Usage

## Install

```bash
brew install sqlcipher          # sqlcipher3 builds against this; no arm64 wheel exists
git clone https://github.com/Raoof128/whatsvault.git
cd whatsvault
make install
make check                      # lint + format + 353 tests
```

## Create the vault

```bash
whatsvault init --reveal
```

This creates `~/.whatsvault` (override with `WHATSVAULT_HOME`), provisions four
Keychain keys, creates both SQLCipher databases, runs every migration, and sets
directories to `0700` and database files to `0600`.

It is idempotent — a second run is a no-op — and it **refuses** to act if a
database exists whose key is missing from the Keychain. SQLCipher keys are not
recoverable, so minting a fresh one there would leave the existing data
permanently unreadable. It reports the situation instead of "fixing" it.

Without `--reveal` the MCP token is withheld; re-run with the flag to print it.

## Import an existing export

This path needs no Meta account, no cloud, and no network.

In WhatsApp: **Chat ▸ More ▸ Export chat ▸ Without media**, then:

```bash
# Preview first — nothing is written.
whatsvault import --path ~/Downloads/chat.txt --dry-run

# Then import into a specific conversation.
whatsvault import --path ~/Downloads/chat.txt \
  --conversation-id cnv_01J… --account-id acc_01J… \
  --timezone Australia/Sydney --date-format DMY --self-label "Me"
```

The import refuses to guess its target: without `--conversation-id` and
`--account-id` it stops rather than inventing one. Provenance is recorded for
every batch, so an import can be undone exactly:

```bash
whatsvault import-undo --job-id imp_01J…
```

Imported timestamps are stored as **intervals**, not instants — a `14:32` line has
minute precision in an unknown second, and DST-ambiguous local times are
classified rather than silently resolved. An import can never reopen a send
window; it writes evidence only.

## Check health

```bash
whatsvault doctor     # vault integrity, search index, ingest, MCP readiness
whatsvault health     # rolled-up status with DLQ depth and circuit state
```

`doctor` reports the search index as repairable drift rather than corruption — it
is a derived artefact and can be rebuilt.

## Run the MCP server

```bash
whatsvault-mcp
```

If you skipped `--reveal` at init, `whatsvault mcp-provision --reveal` prints the
token without changing it. It is idempotent and **never rotates**: replacing the token would
silently break an already-configured connector, and replacing the audit key would
orphan every existing audit HMAC. Without `--reveal` the token is withheld,
because the launchd units capture stdout to a log file.

Verify:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8765/mcp   # 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8765/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'   # 200
```

## Connect an assistant

**Claude Desktop / Claude Code** — add it as a remote HTTP MCP server pointing at
`http://127.0.0.1:8765/mcp` with the bearer token.

**ChatGPT** — ChatGPT cannot reach a local server directly. Enable Developer mode
(Settings ▸ Apps ▸ Advanced), then use OpenAI's Secure MCP Tunnel to expose the
loopback endpoint without publishing it. Developer mode is available on Pro, Plus,
Business, and Enterprise/Edu, though write-tool availability differs by plan — see
the [Phase-0 record](internal/findings/2026-08-27-phase0-verification.md) for
the current verified position.

Whichever you use: connecting an assistant intentionally discloses the excerpts it
retrieves to that provider. That is the trade; make it deliberately.

## Keep a conversation private

```bash
whatsvault mcp-visibility --conversation-id cnv_01J… --visibility LOCAL_ONLY
```

It disappears from every MCP tool. Only the CLI and the phone can set this — the
model cannot reverse it.

## Run as a background service

```bash
sed "s|/Users/USERNAME|$HOME|g" apps/launchd/mcp.plist \
  > ~/Library/LaunchAgents/com.whatsvault.mcp.plist
launchctl load ~/Library/LaunchAgents/com.whatsvault.mcp.plist
```

Provision the keys **before** loading the unit. Without them the daemon reports
`{"status":"not_started","blocked_on":"keys_not_provisioned",…}` and exits
cleanly, which under `KeepAlive={SuccessfulExit: false}` means it stays stopped
rather than looping.

Logs land in `~/.whatsvault/logs/`. They are content-free by construction.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `KeyMissing: whatsvault.mcp.token.v1` | Run `whatsvault mcp-provision`. |
| `401` with the right-looking token | Check for a duplicate `Authorization` header — ambiguous credentials fail closed. |
| `421 Invalid Host header` | DNS-rebinding protection. Use `127.0.0.1:8765`. |
| A conversation is missing from `search` | It is probably `LOCAL_ONLY`; check with `doctor`. |
| `sqlcipher3` fails to build | `brew install sqlcipher` first; there is no prebuilt wheel. |
| A daemon restarts repeatedly | It is exiting non-zero. Read the log — the record names the blocker. |
