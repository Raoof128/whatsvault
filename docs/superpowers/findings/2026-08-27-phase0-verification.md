# WhatsVault Phase 0 — Provider/Platform Verification (FINDINGS SCAFFOLD)

> **This is a verification/finding scaffold, NOT an onboarding guide.** It records what must be *observed* before any live component is activated. **Do not press any Meta/Cloudflare/OpenAI activation control until the relevant prerequisite below is independently verified.** Its deliverable is this document, filled in with evidence — not code.

> **Spec/ledger:** design §0.1/§9/§6.6, INV-PROVIDER; Corrections Ledger #2, #3, #4, #18, #24, #44, #60; Deferred-Decision Register DD1/DD2/DD4.

## Exit rule (strict)

- **UNKNOWN is not YES.** A behaviour that protects a security boundary MUST NOT be activated from documentation inference alone when the design requires an *observed* provider behaviour.
- A gate is PASSED only when every blocking item in it is `YES` with recomputable evidence. A `FALLBACK REQUIRED` item does not block its gate if the fallback is the design's stated conservative path (e.g. V8 → manual reconciliation).
- Every figure taken from a secondary source is **reported**, not confirmed, until the primary provider doc is pinned with a verbatim quote and a date.

## Phase-0 assumptions registry (everything here is `PROVISIONAL` until its V-item is `YES`)

Downstream plans MUST treat each of these as `PROVISIONAL` — never silently assume true:

- `PROVISIONAL` — Meta webhook payload shapes for inbound/echo/history/status (V4/V5/V6/V7); current fixtures are marked `PROVISIONAL` in Phase 3.
- `PROVISIONAL` — inbound timestamp unit is **seconds** (V4); the seconds→ms conversion depends on it.
- `PROVISIONAL` — `biz_opaque_callback_data` is accepted on send and echoed into the status webhook (V8); until confirmed, status reconciliation is **manual-only** (conservative INDETERMINATE + POSSIBLE_MATCH, #59).
- `PROVISIONAL` — pinned `META_GRAPH_VERSION` (V4/V12, ledger #44, DD1); no live send until a tested version is recorded here.
- `PROVISIONAL` — Cloudflare Queues 128 KB per-message cap, ~4-day no-consumer DLQ retention, 14-day paid main retention, realtime metric field names (V14.1–V14.6).
- `PROVISIONAL` — OpenAI/ChatGPT supported private-MCP connection route, its auth, and tool support (O1–O3, DD4).
- **reported** — Meta Cloud-API content retention ~30 days (V13); Cloudflare paid retention ~14 days (V14.4) — pin both.

---

## GATE 1 — Coexistence (V1–V3)
*Blocks the entire write path. A NO here pauses Phases 3/4/5 activation; the read/vault half proceeds regardless.*

### V1 — Is the existing WhatsApp Business App number eligible for Coexistence onboarding?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** eligibility gates activation of the entire write path (Phases 3/4/5). Without it there is no Coexistence + direct Cloud API.
**Required evidence:** provider eligibility screen or API response; account age; messaging-quality state; any provider-stated prerequisite (e.g. the *reported* 7-day active-use requirement); exact date checked. (No Graph version applicable yet.)
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** proceeding on an ineligible number risks resorting to the ordinary Cloud API `/register`, which can change the number's registration and jeopardise the Business App.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Meta changes Coexistence eligibility criteria, or this number's quality rating changes.

### V2 — What is the exact, current, self-managed onboarding path (Business App → Coexistence)?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** activation of the write path; a wrong step can migrate the number one-way.
**Required evidence:** primary Meta doc with the exact end-to-end steps, quoted verbatim; a screenshot of the flow captured **before** performing any step; date. If the official path is not documented clearly enough to execute safely → STOP and record that as the finding.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** an unclear path invites improvising, risking ordinary `/register` on the personal number.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Meta changes the onboarding flow.

### V3 — Does Coexistence keep the WhatsApp Business App usable simultaneously with API access (not a one-way migration)?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** the design assumes the phone app remains usable alongside the API; a one-way migration breaks the user's normal usage.
**Required evidence:** Meta doc quote + a post-onboarding test on a throwaway/secondary number if available; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** an irreversible migration of the personal number is a non-recoverable operational loss.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Meta changes Coexistence behaviour.

---

## GATE 2 — Meta behavioural contract (V4–V13)
*Blocks activation of the ingest and send paths (Phase 3/4/5 live). Each item pins a behaviour a local invariant depends on.*

### V4 — Is a live inbound 1:1 message delivered to the webhook, and what is the exact payload shape (including the timestamp UNIT)?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** activates `MESSAGE_INBOUND` ingest; the Mac-side fan-out normaliser (#2) and `window_eligible` depend on the real nested shape; the seconds→ms conversion (§3.3) depends on the unit.
**Required evidence:** captured (redacted) payload; confirm the nested `entry[].changes[].value.messages[]`/`statuses[]` structure (multi-event fan-out, #2); confirm the message `timestamp` is in **seconds**; the Graph API version used; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** a wrong shape/unit yields mis-parsed evidence and a wrong 24h-window computation (INV-SENDPOLICY).
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Meta bumps the webhook schema or the Graph API version.

### V5 — Are Business-App-typed messages mirrored to the webhook as echoes (`smb_message_echoes`)?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** the "read your own sent messages" feature; the `MESSAGE_ECHO` family (which is `window_eligible=0`, never inbound).
**Required evidence:** captured echo payload shape and its distinguishing marker, or explicit confirmation that none are delivered; Graph version; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** if an echo is mislabelled as inbound it could set `window_eligible=1` and wrongly open the send window — the echo detector must be verified against the real marker (the current `_wv_echo` fixture flag is `PROVISIONAL`).
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Meta changes Coexistence echo behaviour.

### V6 — Is any historical-message sync delivered on onboarding, and what is its volume + shape (`HISTORY_EVENT`)?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** sizes the backfill gap (the export importer covers it); the design must **not** depend on this.
**Required evidence:** captured `HISTORY_EVENT` shape + volume, or confirmation that none is delivered; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** history events must never set `window_eligible=1` (they are not live inbound).
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Meta changes history-sync behaviour.

### V7 — Are `sent`/`delivered`/`read`/`failed`/`deleted` status notifications delivered, in what ordering, and what is the payload shape?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** status reconciliation (#59) and the monotonic delivery-rank lattice; the callback column (#60).
**Required evidence:** captured status events for a test send; observed ordering behaviour; whether `biz_opaque_callback_data` appears here; Graph version; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** mis-ordered/mis-parsed status could distort delivery state, but the monotonic lattice already tolerates reordering; confidentiality is unaffected.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Meta changes the status schema.

### V8 — Does the direct Cloud API accept `biz_opaque_callback_data` on a send AND echo it back into the status webhook?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters (REVISED):** this gates the **deterministic status-reconciliation UX only** (#60). **V8 does NOT block Phase 4 approval correctness.** If callback correlation fails, WhatsVault still operates safely with conservative `INDETERMINATE` + manual reconciliation (`POSSIBLE_MATCH`, #59). V8 blocks the *deterministic reconciliation UX*, not *approval security*.
**Required evidence:** the send response + the correlated status webhook showing the field; Graph version; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** none to approval security. A NO degrades only reconciliation determinism; the fallback is manual-only reconciliation (residual R7).
**Decision:** PROCEED (deterministic reconciliation) / **FALLBACK REQUIRED (manual-only reconciliation)** — **never BLOCK the whole write path on V8.**
**Reverification trigger:** Meta changes callback-data support on the direct API.

### V9 — Does `GET /{media-id}` return a fresh temporary URL after the first URL expires?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** a sleeping Mac must not permanently lose media within the retention window; `materialise_media` (#43 daemon).
**Required evidence:** two `GET`s of the same media id minutes apart showing a refreshed URL; Graph version; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** media availability (not confidentiality) — a NO tightens the media-materialisation deadline.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Meta changes the media URL lifetime.

### V10 — Does free-form send fail outside the 24h window and require an APPROVED template, and does the templates endpoint list status?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** P2 policy (#11), template send (#17); the window is send-authoritative (INV-SENDPOLICY).
**Required evidence:** a rejected free-form send outside the window with the exact error; a `message_templates` list response showing status; Graph version; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** if Meta does not enforce the window, the local `control.db` projection remains the sole gate (it already is) — verify it is never bypassed.
**Classification:** compatibility/fallback (P1/P2 policy is deliberately local + send-authoritative).
**Decision:** FALLBACK REQUIRED — revise the Meta adapter/policy compatibility before affected free-form/template sends; may block free-form/template **production use** until understood, but does NOT block the Meta contract or invalidate approval cryptography _(unfilled)_
**Reverification trigger:** Meta changes the window/template policy.

### V11 — Confirm Coexistence numbers cannot send to / are not delivered group messages via the API.
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** P7 recipient policy (no group); the design excludes groups from the send path.
**Required evidence:** provider doc quote; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** none to activation. Groups are excluded and enforced **locally** regardless of Meta: `write_capable=false` + `conversation_type=group` → deny. Unexpected Meta group support is a useful compatibility finding, not a dependency.
**Classification:** compatibility (non-blocking).
**Decision:** PROCEED — record the finding; keep enforcing the local group-deny _(unfilled)_
**Reverification trigger:** Meta adds group support to Coexistence.

### V12 — Is the runtime messaging scope (`whatsapp_business_messaging`) separable from the management scope (`whatsapp_business_management`)?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** the `whatsvault-meta` daemon must hold ONLY the messaging scope (#43, topology invariant: one process holds the token, no management authority).
**Required evidence:** the token/scope configuration screen showing the split; the exact `META_GRAPH_VERSION` in use (pin it here for DD1/#44); date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** if inseparable, the daemon would hold management authority — a least-privilege violation.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Meta changes the scope/permission model or deprecates the Graph version.

### V13 — Pin Meta's current Cloud-API message-content retention.
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** sizes how promptly media must be materialised; feeds ingest retention alerting (#39, `retention.assess`).
**Required evidence:** primary Meta doc quote with the exact figure (reported ~30 days); date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** operational (media availability), not confidentiality — a shorter figure tightens the media-materialisation deadline, not send safety.
**Classification:** operational (non-blocking for Meta activation).
**Decision:** PROCEED — feed the figure into `retention.assess`/materialisation policy; does not gate signed sends _(unfilled)_
**Reverification trigger:** Meta changes content retention.

---

## GATE 3 — Cloudflare (V14.1–V14.6)
*Blocks activation of the sealed edge relay + queue (Phase 3b live). Expanded to cover the corrections from the gauntlet.*

### V14.1 — Confirm the current Cloudflare Queues per-message size cap (target: 128 KB).
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** #3 — the Worker admits bodies ≤1 MB but a queue message caps at ~128 KB, so an oversized sealed body must spill to R2 (V14.5). A wrong assumption silently drops events.
**Required evidence:** current Cloudflare Queues limits doc quote; date.
**Observed result:** PRIMARY-DOC VERIFIED (WebFetch 2026-08-28) — doc-level fact = **YES**: max message size «128 KB»; max retries «100»; free retention «24 hours» (non-configurable); paid retention «Configurable up to 14 days». Account-independent, so the R2 oversized-ciphertext spill (#3) is mandatory.
**Raw evidence reference:** https://developers.cloudflare.com/queues/platform/limits/ (WebFetch-verified 2026-08-28).
**Security consequence:** silent event loss if a sealed body exceeds the cap without the R2 path.
**Decision:** PROCEED (R2 spill implemented) / BLOCK (no spill) / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Cloudflare changes queue message limits.

### V14.2 — Confirm how HTTP pull-consumer retry/DLQ configuration attaches (consumer, not producer).
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** #4 — retry/DLQ config belongs to the consumer configuration.
**Required evidence:** current pull-consumer configuration doc; date.
**Observed result:** PRIMARY-DOC VERIFIED (WebFetch 2026-08-28): «Enabling HTTP pull from a Wrangler configuration file is no longer supported» — enable «via the wrangler CLI or via the Cloudflare dashboard». (The DLQ-belongs-to-consumer fact lives on the DLQ page → recorded under V14.3, not here.) ACCOUNT-SPECIFIC PENDING: pull enabled on THIS queue.
**Raw evidence reference:** https://developers.cloudflare.com/queues/configuration/pull-consumers/ (WebFetch-verified 2026-08-28).
**Security consequence:** mis-placed config could disable retries/DLQ, losing transient-failure events.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Cloudflare changes consumer configuration.

### V14.3 — Confirm an edge DLQ with NO active consumer retains only ~4 days.
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** #4 — a DLQ is itself a queue; naming one is insufficient. An explicit edge-DLQ **consumption/recovery design is required, with the DLQ's own configured retention independently verified** — do not assume a drainer/consumer implies infinite (or 14-day) retention.
**Required evidence:** DLQ retention doc quote; date.
**Observed result:** PRIMARY-DOC VERIFIED (WebFetch 2026-08-28): «A Dead Letter Queue (DLQ) is defined within your consumer configuration»; «Messages delivered to a DLQ without an active consumer will persist for four (4) days before being deleted from the queue». DESIGN/ACCOUNT PENDING: the edge-DLQ consumption/recovery design + its own configured retention (a drainer alone does not extend retention).
**Raw evidence reference:** https://developers.cloudflare.com/queues/configuration/dead-letter-queues/ (WebFetch-verified 2026-08-28).
**Security consequence:** silent loss of quarantined events past ~4 days without a drainer.
**Decision:** PROCEED (drainer built) / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Cloudflare changes DLQ retention.

### V14.4 — Confirm the paid-tier main-queue retention (target 14 days; Free tier 24h).
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** the INV-ACK durability window; `retention.assess` bands (#39).
**Required evidence:** Queues retention doc quote + the account's plan tier; date.
**Observed result:** DOC-CONFIRMED (2026-08-28): Free tier retention = 24h; **paid retention configurable up to 14 days**. ACCOUNT-SPECIFIC UNCONFIRMED: whether THIS account's queue is actually configured for 14 days.
**Raw evidence reference:** https://developers.cloudflare.com/queues/platform/limits/ (verified 2026-08-28); account queue config pending.
**Security consequence:** a shorter-than-assumed window shortens the offline-Mac tolerance before loss.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Cloudflare changes retention or the account plan changes.

### V14.5 — Confirm the R2 oversized-ciphertext spill path (put/get, scoped credentials, lifecycle).
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** #3 — an oversized sealed body is stored as an encrypted R2 object; a pointer is enqueued; the Mac fetches, verifies `ciphertext_sha256`, commits, ACKs, deletes.
**Required evidence:** R2 API + lifecycle doc; a test put/get of a ciphertext object; the scoped-credential configuration; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** R2 must hold **ciphertext only** (INV-CIPHERTEXT); verify the Worker seals *before* the put — a misconfiguration that stored plaintext would be a confidentiality breach.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Cloudflare changes R2 API/lifecycle, or the sealing order regresses.

### V14.6 — Confirm the realtime metrics field for oldest-message age + backlog (best-effort).
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** retention monitoring (#50). **These metrics are best-effort/approximate — NOT proof that an already-expired event never existed.**
**Required evidence:** Queues metrics doc naming the field (e.g. `oldest_message_timestamp_ms`); date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** over-relying on approximate metrics would produce a false "no loss" claim; Phase 6 C5 must claim only impending-loss warning + honest post-expiry incompleteness (#50).
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** Cloudflare changes the metrics surface.

---

## GATE 4 — 2b OpenAI/ChatGPT connectivity (O1–O4)
*Kept adjacent but SEPARATE from Meta activation. Blocks the live ChatGPT integration only; the local MCP (Phase 2a) is already shipped and testable without it. Resolves DD4.*

### O1 — What is the actual supported route to connect a private/local MCP to ChatGPT?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** 2b activation (#18). ChatGPT does not simply connect to arbitrary local MCP servers; a supported route (Developer Mode / Secure MCP Tunnel / remote MCP) is required, and product-plan support varies.
**Required evidence:** OpenAI help/doc quote naming the supported route; **the intended account's actual plan tested against the currently-supported MCP modes** (not merely proof that the route exists); date. If the account's plan is not currently listed as supporting the required MCP mode, O1 is `BLOCKED` even though the technical route exists.
**Observed result:** DOC-CONFIRMED (2026-08-28, OpenAI Help): ChatGPT cannot connect directly to a local MCP; **Secure MCP Tunnel** is the documented private/local/developer-machine route; full MCP incl. modify/write actions is currently rolling out for **Business/Enterprise/Edu**; **Pro** can use custom MCPs with **read/fetch** permissions in Developer Mode. ACCOUNT-SPECIFIC UNCONFIRMED: whether the intended account's plan supports the required MCP mode (if read-only Pro but write tools are needed later → BLOCKED for write; read surface may still proceed).
**Raw evidence reference:** https://help.openai.com/en/articles/12584461 — per Raouf's 2026-08-28 primary-doc verification; an independent WebFetch (2026-08-28) returned HTTP 403 (help.openai.com is login/bot-gated), so re-confirm the wording + the account's plan capabilities in-session before O1 is ticked.
**Security consequence:** an unsupported or insecure route could expose the loopback MCP surface (private message history) beyond the intended boundary.
**Decision:** PROCEED (supported route) / FALLBACK REQUIRED (OpenAI Responses API remote-MCP) / BLOCK _(unfilled)_
**Reverification trigger:** OpenAI changes MCP connectivity or product-plan support.

### O2 — How is the connection authenticated, and does it satisfy the loopback-auth requirement (#19)?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters (requirement, mechanism-agnostic):** the selected route MUST provide an authenticated binding from the authorised ChatGPT connection to the local WhatsVault MCP, and MUST prevent unauthorised local or tunnel clients from invoking it. The existing Keychain-backed bearer token MAY be used where the selected route supports it; otherwise the route's authenticated identity MUST be mapped to the same local access decision (#19). Verify the *actual* mechanism the route provides — do not assume the local bearer token literally traverses it.
**Required evidence:** OpenAI doc on the chosen route's authentication model; a test proving an unauthorised local/tunnel client cannot invoke the MCP; the mapping used (bearer token, or route-identity → local access decision); date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** an unauthenticated route would let any party reaching the tunnel read message history.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** OpenAI changes the auth model for the route.

### O3 — Does the route support the read tool surface (and later the write/prepare tools)?
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** the Phase 2a MCP surface must be callable; tool-annotation support determines what ChatGPT can invoke.
**Required evidence:** OpenAI doc on tool support for the route; a test tool call against the loopback surface; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** none direct; a gap here limits functionality, not safety.
**Decision:** PROCEED / BLOCK / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** OpenAI changes tool support.

### O4 — Confirm and document the selected-plaintext disclosure boundary (#24).
**Status:** `[ ] YES  [ ] NO  [ ] UNKNOWN  [ ] BLOCKED`
**Why it matters:** INV-CONTENT / #24 — using ChatGPT with WhatsVault intentionally discloses the selected plaintext excerpts to the configured LLM service. The user must consent to this boundary before it goes live.
**Required evidence:** the disclosure invariant recorded in the spec + a written user acknowledgement; OpenAI data-use terms quote; date.
**Observed result:** _(unfilled)_
**Raw evidence reference:** _(unfilled)_
**Security consequence:** selected plaintext excerpts leave the Mac and reach OpenAI — intentional, but it must be explicit and acknowledged, not implicit.
**Decision:** PROCEED (user acknowledges the disclosure) / BLOCK (if not acceptable) / FALLBACK REQUIRED _(unfilled)_
**Reverification trigger:** OpenAI changes its data-use terms, or the disclosure scope widens.

---

## Gate decision summary (fill at closeout)

| Gate | Blocking items | Status | Decision |
|------|----------------|--------|----------|
| 1 — Coexistence | V1, V2, V3 | _(unfilled)_ | PROCEED / BLOCK |
| 2 — Meta contract | **Blocking:** V4, V7, V12. **Compatibility/fallback:** V5, V6, V8, V9, V10, V11, V13 — V10 may still block free-form/template *production use* until understood (not the whole contract); V8 → manual-only fallback | _(unfilled)_ | PROCEED / BLOCK |
| 3 — Cloudflare | V14.1, V14.3, V14.4, V14.5 (V14.2/V14.6 non-blocking) | _(unfilled)_ | PROCEED / BLOCK |
| 4 — OpenAI (2b) | O1, O2, O4 (O3 non-blocking) | _(unfilled)_ | PROCEED / FALLBACK / BLOCK |

**Activation is permitted only per-gate, only when that gate's blocking items are `YES` with evidence.** A NO on Gate 1 pauses the entire write path; the read/vault half (already shipped) is unaffected. Gate 4 is independent of Gates 1–3.
