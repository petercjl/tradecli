# Validation and compatibility

## Scope

Codex-only first release. Node CLI, Python Windows worker, protocol 1.
macOS + Parallels is the primary runtime. Native Windows transport is implemented
but not live-tested. No order execution is implemented.

## Development evidence

- 5 Node tests: CLI boundaries, safe quoting, private/non-overwriting config,
  Codex Skill installation/conflict preservation, read-only capability discovery.
- 15 Python tests: visible-control selection, dialog classification, resume guards,
  durable operation records, no duplicate copy, account mismatch, restoration,
  explicit abandonment and strict holdings parsing.
- Current base Skill creator scaffold and validator used.
- Platform portability, hybrid knowledge and capability-contract validators pass.
- No isolated clean-context regression requested or claimed.

## Evidence boundaries

The preceding adapter prototype demonstrated two-account funds, holdings and
selection on Windows 11 ARM using Python 3.11 x64 with a 32-bit THS client.
Those observations do not constitute end-to-end acceptance of this package.
Real CAPTCHA completion/resume, equal-value account transitions, native Windows
host execution, lock-screen recovery and server-side freshness remain unverified.

## Skill knowledge read-set audit

Ordinary successful query: Skill and Codex adapter, no topic reads.
Interrupted copy interpretation: references/SCHEMA.md, index.md, recent log.md,
queries/recover-copy.md, then topics/copy-recovery.md before choosing recovery.
Snapshot interpretation topic and maintenance source-manifest stay deferred.
Development evidence is separate from the runtime Skill.

## Package main run (2026-10-01)

The new CLI installed its own isolated Windows dependencies, deployed the
content-addressed worker, attached to the current THS client and discovered two
accounts. A funds query selected the other account, obtained data and restored
the original account. A holdings query reached a real manual-verification dialog
and persisted an operation checkpoint. Completion of that request is pending.

The host uses Parallels home sharing to transfer the bundled worker as a file;
this avoids large encoded-command payload limits. Uploaded content is verified
by SHA-256. Runtime and client operations execute in the current Windows session.
