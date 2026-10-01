# Validation and compatibility

## Scope

Codex-only first release. Node CLI, Python Windows worker, protocol 1.
macOS + Parallels is the primary runtime. Native Windows transport is implemented
but not live-tested. The released 0.1.0 supports queries; the 0.2.0-dev.2 source adds visual holdings, simulated orders and single-worker simulated batches.

## Development evidence

- 5 Node tests: CLI boundaries, safe quoting, private/non-overwriting config,
  Codex Skill installation/conflict preservation, read-only capability discovery.
- 17 Python tests: visible-control selection, dialog classification, resume guards,
  durable operation records, no duplicate copy, account mismatch, restoration,
  explicit abandonment and strict holdings parsing.
- Current base Skill creator scaffold and validator used.
- Platform portability, hybrid knowledge and capability-contract validators pass.
- No isolated clean-context regression requested or claimed.

## Evidence boundaries

The preceding adapter prototype demonstrated two-account funds, holdings and
selection on Windows 11 ARM using Python 3.11 x64 with a 32-bit THS client.
Those observations do not constitute end-to-end acceptance of this package.
One real CAPTCHA completion/resume passed with nine holdings rows, no reconciliation
warnings and restoration of the original account. Equal-value account transitions,
native Windows host execution, lock-screen recovery and server-side freshness remain
unverified. One successful recovery does not establish unattended reliability.

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
and persisted an operation checkpoint. After manual completion, the same request
returned nine rows without a new copy request and restored the original account.

The host uses Parallels home sharing to transfer the bundled worker as a file;
this avoids large encoded-command payload limits. Uploaded content is verified
by SHA-256. Runtime and client operations execute in the current Windows session.

## Desktop actions development (2026-10-01)

Unreleased 0.2.0-dev.1, Codex + macOS Parallels + Windows 11 ARM.
- No-copy capture and image review reconciled simulated holdings. A real account
  was also captured without a copy request. Clipboard sequence stayed unchanged.
- Account selection and query restoration were exercised against logged-in accounts.
- Simulated sell and buy each returned an accepted contract; both appeared in the
  refreshed current-day order ledger with matching code, price and 100-share amount.
  Both were unfilled at inspection. Real-account submission was not performed.
- Earlier buy attempts returned no receipt and no matching ledger row. Their cause
  remains unresolved; no successful execution is inferred from those attempts.
- Input uses easytrader's select/type approach with explicit full-range selection;
  GetWindowText is empty in this client, so default selection and readback are
  insufficient. EM_GETLINE provides actual values. Submission requires exact readback.
- Navigation uses the upstream current-day-order tree path and F5 refresh.
  Confirmation uses the upstream Alt+Y approach, after exact dialog validation.
- Test orders remain in the simulated account. Cancellation is outside this version.
- Large scrolling holdings tables and native Windows host transport are unverified.
- Skill update uses portable-skill-creator with the current base skill-creator.
  Existing hybrid interpretation/recovery references are retained; new visual and
  simulated-order contracts derive from authorized requirements and live evidence.
  Clean-context regression was not requested and has not run.

Current development checks: 10 Node tests and 32 Python tests passed. The same
32 Python tests passed in the Windows worker runtime. Syntax and package checks,
base Skill format, platform portability, hybrid knowledge, capability contract
and Codex adapter-gap checks passed. Visual holdings review reconciled all visible
rows after simulated orders; clipboard sequence was unchanged. Ordinary order
execution loads the Skill and Codex adapter only; recovery/interpretation routes
and maintenance provenance remain deferred until their respective nodes.

## Batch development (2026-10-01)

Unreleased 0.2.0-dev.2 extends the same Codex and Parallels environment.
The worker now sends Alt+Y to the validated confirmation modal and polls briefly
for a success receipt. A first single-order smoke test received a contract but
stopped during cleanup because the client had already cleared the form; the
accepted contract was independently visible in the current-day ledger. The
cleanup guard was updated to accept a fully blank form. A subsequent two-order
batch finished in one worker in about 15 seconds. Both contract numbers matched
the ledger, with 100 shares each and zero filled at inspection.

The batch tests cover a single worker, exact receipt matching, an absent receipt
stopping later rows, a real-account guard, digest and duplicate-plan guards,
interrupted state, and automatic client form clearing. The prior no-receipt
case was not repeated; its underlying cause is still unknown. The new polling
path recovered receipts in this small sample and preserves uncertain outcomes
without retry.
