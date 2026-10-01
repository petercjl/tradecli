# Validation and compatibility

## Scope

Codex-only first release. Node CLI, Python Windows worker, protocol 1.
macOS + Parallels is the primary runtime. Native Windows transport is implemented
but not live-tested. The released 0.1.0 supports queries. The current 0.2.0-dev.4
checkout includes visual holdings, strategy planning, simulated orders, and
single-worker simulated or real-account batches. Real-account submission has
automated tests but no live funded-account validation.

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

## Client-default-price batch (2026-10-01)

Unreleased 0.2.0-dev.3 adds `batches validate-default` and
`batches prepare-default`. An authorized three-order simulated test used the
client's automatically filled price field: buy 600221 for 100 shares, buy
600010 for 100 shares, and sell 300359 for 100 shares. No price was typed by
the worker. The confirmation dialogs identified the two buy prices as 卖一 and
the sell price as 买一. One Windows worker submitted and confirmed all three in
about 17 seconds. Each receipt contract appeared in the refreshed current-day
ledger with matching side, code, quantity and limit price; all had zero filled
at inspection. The preview logic initially saw a transient nonblank field after
clearing a sell quote; a bounded wait fixed it before submission testing.

The final CLI requires a user-confirmed plan plus `--yes` at execution. Unit
tests verify that default-price execution types only the code and quantity,
and that a missing confirmation flag prevents dispatch. This is a small
simulated-client sample, not a guarantee that prices or fills remain unchanged.

## Fifteen-order simulated batch (2026-10-01)

Unreleased 0.2.0-dev.4 increased the batch limit to 15 and permits separate
sell rows for the same held stock. A 15-row plan exceeded the Parallels command
payload path; requests now travel through a private, SHA-256-verified file.
The default-price planning command validates the list without entering each
order form. A confirmed simulated batch of ten buys and five sells completed
in one worker in 71.499 seconds. Fifteen distinct receipts matched the refreshed
current-day ledger for side, code, 100-share quantity and limit price. All
fifteen showed zero filled at inspection. The five sell orders covered three
held securities, with two securities split into two orders each. No funded
account was used for submission.

## Strategy and real-account batch update (2026-10-01)

The source checkout now converts order deltas or target holdings into an exact
per-row before/after share table using a recent reconciled holdings review.
Tests cover repeated sell rows, target arithmetic, unavailable shares, missing
names, account mismatch, stale evidence, and private output files. The real
default-price batch path binds the account type and ID, rejects cross-kind run
commands, and persists each order before confirmation. The full Node and Python
test suites pass, as do Skill format, portability, capability-contract, package
dry-run, and syntax checks. No new market order or funded-account submission was
performed in this update.

## Eight-row simulated strategy trial (2026-10-01)

The holdings-based Skill generated a table for five buys and three sells in the
simulated account. The user confirmed the complete table. The first buy returned
a contract number; the second buy lost its success receipt and did not appear
in two refreshed order-ledger captures. The worker marked that row `unknown`
and left six rows unattempted. A fresh, separately confirmed six-row plan
stopped before any submit because the previous buy form still held the second
order. After identifying that task-owned draft, the form was cleared without
resubmitting the unknown row. A fix now permits preparing an identical plan
again only when all rows of the failed batch remain `queued`. The rerun
completed all six. Seven distinct contracts across both runs appeared
in the current-day ledger, all unfilled at inspection. The missing-receipt buy
remains unresolved. Refreshed holdings showed unchanged actual share counts.

## Real-account rejected order trial (2026-10-01)

A user-confirmed two-row plan targeted one funded account: buy 100 shares of
600221, then sell 100 shares of a held security. The worker matched the real
account and the full THS confirmation for the buy, sent confirmation once, and
received no success contract within its receipt window. It marked the buy
`unknown` and left the sell `queued`. Two refreshed current-day order views
showed no accepted order. The user subsequently supplied a THS error screenshot
stating that orders were not allowed during a system pre-initialization backup
(`-150906060`, status `5`). This evidence establishes a client-side rejection
for that attempt, while the persisted batch record conservatively remains
`unknown`. The task-owned buy form was left for manual inspection. No funded
account acceptance or fill was verified.
