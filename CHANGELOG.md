# Changelog

## Unreleased

- Raouf: open Phase 1a vault core (scaffold, deterministic SQLCipher install, capability gate).
- Raouf: Phase 1a vault core complete (rev 2) — 67 tests green. Deterministic SQLCipher source build (sqlcipher3 0.6.2 / cipher 4.12.0) + locked deps, prefixed ULIDs (full entity registry), validated interval time model + DST classification, provision/require keystore + versioned attachment AEAD, eager-validated connections with at-rest encryption proof, numbered transactional migrations, vault schema with explicit window_eligible + checks, deny-by-default evidence immutability, domain-tagged dedupe, status lattice, control schema aligned to the signed byte contract, and a doctor that rebuilds the window from evidence (repairs forged values downward). Real secret scan + pip check gate.
- Raouf: execution deviations from plan rev2 (folded back into the plan): (1) install drops `--no-binary=sqlcipher3` (that flag broke the build backend; the source build happens anyway as no wheel exists for macOS arm64); (2) capability gate probes connection-state pragmas (foreign_keys, secure_delete) BEFORE the FTS DDL probes, since foreign_keys cannot change once a transaction is open; (3) the migration runner lives in `db/migrations/__init__.py`, because a sibling `migrations.py` is shadowed by the `migrations/` package directory.
