# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries record *what changed and why it mattered*. Where a change closes a
security hole or corrects an earlier mistake, it says so — the detailed reasoning
lives in the commit message, and the design rationale in
[`docs/internal/`](docs/internal/).

## [Unreleased]

Running the documented commands end to end — rather than reading them — found six
defects that the 397-test suite could not see, because every one of them lived in
a seam between layers that were each individually correct and individually tested.

### Added

- `whatsvault accounts-add`, `accounts-list`, `conversations-add` and
  `conversations-list`. `import` refuses to guess its target, but a fresh vault
  had no accounts and no conversations and no verb created either — so the
  `--conversation-id` and `--account-id` it demands could not be obtained by any
  means, and the documented import was unreachable on every new vault.
- `tests/conftest.py`: an autouse guard that points `$WHATSVAULT_HOME` at a
  per-test directory and fails any test that writes to the operator's real vault.
- `tests/test_mcp_transport_tools_live.py`: tool calls over a real socket. The
  existing live suite stopped at `initialize`, so no test had ever executed a
  handler that touches SQLCipher.

### Fixed

- **Every database-backed MCP tool failed on the running server.** Connections are
  opened once on the main thread; the SDK dispatches synchronous handlers onto a
  worker thread, so each call raised `SQLite objects created in a thread can only
  be used in that same thread`. Connections for the daemon are now opened with
  `check_same_thread=False` and every handler is serialised on one lock. A wrong
  flag is refused at startup, with the fix in the message, instead of turning each
  call into an opaque 500.
- **`search` had never worked over MCP.** The registered handler declared a
  `SearchQuery` parameter and passed it straight through; a client sends JSON, so
  the value arrived as a string and every call raised `AttributeError`. The unit
  tests missed it because they construct a `SearchQuery` in Python and call
  `reads.search` directly, bypassing the handler that is actually registered.
- **`whatsvault init` could not run.** `cli.main` opened both databases before
  dispatching, so on a fresh machine — the only place anyone runs `init` — it died
  with `KeyMissing` before argparse's verb reached the command table. Bootstrap
  verbs now run without connections, and a missing key reports `run
  \`whatsvault init\` first` rather than a traceback.
- **`cmd_init` resolved the vault layout from the environment**, not from the
  context it was handed, so a test injecting a temporary path still created a real
  `~/.whatsvault` — with keys in a keystore that vanished, leaving unreadable
  ciphertext that then blocked a genuine `init`. The layout now travels with the
  context.
- The console scripts `whatsvault` and `whatsvault-mcp` are asserted to resolve,
  and `main()` returns its exit code rather than raising `SystemExit` — setuptools
  wraps it in `sys.exit()`, so a `None` return reported success for every failure.

### Security

- **The MCP result cap could be lifted by asking for `limit: -1`.** SQLite treats
  `LIMIT -1` as unbounded, so `min(limit, MAX_LIMIT)` was not a cap and a single
  call could drain the whole table through the read surface. Clamped at both ends.
- **`get_conversation_window` took `now_ms` from the caller**, letting the model
  assert the time that decides whether a send window is open. The tool now takes
  `conversation_id` only and reads the server clock (INV-SENDPOLICY).

## [0.1.0] — 2026-08-28

First public release. The vault, search, and read-only MCP surface are complete
and tested. The write path is implemented but deliberately inert, gated behind
[Phase-0 verification](docs/internal/findings/2026-08-27-phase0-verification.md).

### Added

**Vault core**
- SQLCipher-encrypted `vault.db` (evidence) and `control.db` (control plane), keyed
  from the macOS Keychain, with eager key validation — `PRAGMA key` is lazy, so a
  wrong key would otherwise fail only on first page read.
- Forward-only migrations applied atomically; a failure rolls back and leaves the
  schema version unchanged.
- ULID-based prefixed identifiers, and triggers enforcing immutability of evidence
  fields.

**Import**
- WhatsApp text-export parser with an explicit grammar, provenance tracking, and
  exact undo by batch.
- Time modelled as **uncertainty intervals** rather than instants: a `14:32` line
  has minute precision in an unknown second, and DST-ambiguous or skipped local
  times are classified rather than silently resolved.
- Zip-bomb and path-traversal guards on archive input.

**Search**
- FTS5 over a normalised representation, tuned for mixed English/Persian text —
  ZWNJ handling and Arabic/Persian character folding.
- Two-tier ranking (lexical and compact) with snippet extraction.
- The index is explicitly derived and disposable: it can be dropped and rebuilt
  without affecting evidence, deduplication identity, or display.

**Read-only MCP surface**
- Six read tools over Streamable HTTP on loopback, each annotated
  `readOnlyHint: true`, `openWorldHint: false`.
- A **provably empty write surface**: CI asserts the registered tool set is
  disjoint from a named forbidden set, checked against plain module constants so
  the guarantee survives SDK changes.
- Bearer-token authentication in ASGI middleware, constant-time compared;
  DNS-rebinding protection with a pinned `Host`.
- Redaction (no full phone number ever leaves the boundary) and untrusted-content
  wrapping of every WhatsApp-originated string.
- A server-side `LOCAL_ONLY` visibility fence, settable only from the CLI or phone.
- Keyed-HMAC audit log — not a bare SHA-256, which would make a low-entropy query
  such as a contact name trivially recoverable by dictionary attack.

**Approval chain**
- Immutable drafts with single-use nonces and expiry; a shared policy engine runs
  at prepare and again authoritatively at send.
- Two-key device enrolment with mutual challenge, binding signing and agreement
  keys; P-256 ECDH device sealing for draft detail served to the phone.
- A display guard for bidi overrides, zero-width characters, and confusables —
  the signature binds bytes, but a human approves rendered glyphs.
- Crash-durable send state machine: a stranded `SUBMITTING` attempt resolves to
  `INDETERMINATE`, never a blind resend.

**Ingest**
- Sealed envelopes authenticating their own header as AEAD associated data, so
  metadata cannot be swapped or downgraded without failing the tag.
- Pull-consumer loop that acknowledges only after durable local disposition, with
  decrypt failures classified by key health — an isolated AEAD failure is poison
  and quarantined, a systemic one trips a circuit breaker.
- Dead-letter queue with sanitised metadata and no payload retention.

**Operations and CLI**
- `whatsvault init` — creates the runtime layout, both encrypted databases, all
  migrations, and every Keychain key.
- `import`, `import-undo`, `mcp-visibility`, `mcp-provision`, `doctor`, `health`,
  and device, DLQ, template, reconciliation, and scheduler verbs.
- A CLI surface with **no** approve, send, sign, or dispatch verb, asserted by test.
- Four launchd units, content-free structured logging, filesystem hardening
  (`0700` directories, `0600` secret files), and conservative startup recovery.

**Project infrastructure**
- README, architecture overview, usage guide, MCP reference, security policy,
  contribution guide, and code of conduct.
- CI running lint and format on Linux, the full suite on macOS across Python
  3.11–3.13, secret scanning over full history, and a build job that verifies the
  wheel ships both packages and both console scripts.
- ruff, coverage, pre-commit, EditorConfig, and a Makefile whose targets are the
  same commands CI runs.

### Fixed

- **Imported messages were never indexed**, so search over them silently returned
  nothing. With live ingest gated, import is the only way data enters the vault,
  meaning the primary read path had never worked end to end. `doctor` had been
  asserting this all along; unit tests masked it by indexing by hand in fixtures.
- **No way to create a vault existed.** `provision_db()` and the migration runner
  were tested but uncalled, while every entry point required databases nothing
  could produce.
- **All four launchd units were silent restart loops** — well-formed plists
  pointing at modules with no entry point, which under `KeepAlive: true` were
  imported, exited instantly, and restarted forever.
- MCP transport authentication was a *tool parameter*, publishing the server's own
  secret in every tool's JSON schema and unreachable over HTTP, where the token
  arrives in a header.
- A latent crash in the audit path: hashing a structured `SearchQuery` argument
  would raise mid-request. Only the no-argument tool had ever been exercised.
- Roughly twenty leaked file handles across the test suite, surfaced by promoting
  warnings to errors.

### Security

Findings from a red-team pass over the read surface, each now pinned by a
regression test in [`tests/adversarial/`](tests/adversarial/):

- **Privacy-fence bypass (high).** `get_conversation_window` ignored the
  `LOCAL_ONLY` fence, leaking exact last-inbound timestamps for conversations
  explicitly marked private. Activity timing is content.
- **Phone numbers recoverable through redaction (high).** Raw `wamid` values were
  returned unredacted, and a `wamid` base64-decodes to the counterparty's full
  E.164 — defeating contact masking for every reply. Replaced with opaque,
  correlatable handles.
- **Row-limit escape (medium).** `min(limit, MAX_LIMIT)` admits negatives, and
  SQLite reads `LIMIT -1` as unbounded, so a negative limit returned entire tables.
- **Audit log recorded every call as a success (medium).** The outcome was
  hardcoded and written before execution, so a failed probe left a clean trail.
- **Ambiguous credentials accepted (low).** Duplicate `Authorization` headers were
  first-wins rather than failing closed.

Hardening applied alongside:

- SQL identifier interpolation is allowlisted at runtime rather than trusted to
  caller discipline. Every site was safe by inspection; none was safe by
  construction.
- A secret-tracking gate fails the build if a key literal, PEM block, or database
  file is ever tracked, alongside `gitleaks` in pre-commit and CI.

[Unreleased]: https://github.com/Raoof128/whatsvault/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Raoof128/whatsvault/releases/tag/v0.1.0
