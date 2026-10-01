---
name: tradecli
description: Use tradecli to switch THS accounts, review holdings images, and run account-bound individual or batch orders in simulated accounts from Codex.
---

# tradecli

Codex-only, platform-specific Skill distributed with `@petercjl/tradecli`.
The CLI and bundled Windows worker are the execution source of truth.

## Input → strategy → output

Input: a query or simulated-order intent, account ID, and for orders side, code, price and shares. Default queries to the current account;
use multiple accounts only when the user requests that scope.
Strategy: inspect capabilities and readiness, resolve accounts, query serially,
handle operation states, check attribution and reconciliation.
Output: account-bound funds/holdings with acquisition time, displayed-data
freshness, warnings, operation ID and restoration state. Never infer server
freshness or a completed query from an incomplete operation.

## Main line

1. **Discover.** Run `tradecli version` and `tradecli capabilities --json`.
   Load [Codex adapter](adapters/codex.json) to resolve the execution contract.
   If missing, install the user-authorized npm package; use `tradecli skill source`
   for canonical instructions. This Skill requires protocol 1 and CLI 0.2.x (including 0.2.0 prereleases).
2. **Connect.** Run `tradecli doctor --json`. If configuration is missing, use
   `connections discover`, obtain the intended VM and THS executable location,
   and `config init --transport parallels --vm <vm> --exe <path>`.
   `runtime install` provisions an isolated Windows environment using an existing
   Python installation (`config init --python <path>`). An optional
   `--wheelhouse <Windows-path>` supports verified offline dependency wheels.
   The user logs into THS and opens its funds/holdings page manually.
3. **Resolve scope.** Run `accounts list --json`; use returned account IDs.
   Display labels can be masked and are not full brokerage identifiers.
   Ambiguous or missing identities require clarification before selecting.
4. **Query.** Use `funds get`, `positions list`, optionally `--account <id>`;
   use `snapshots create --accounts <id,id>` for an explicit multi-account scope.
   GUI operations serialize within the Windows desktop. Each query restores its
   initial account on completion. `accounts select --account <id>` intentionally
   keeps the selected account. A visible populated order form blocks navigation.
   For orders, use the individual or batch order branch below.
5. **Handle outcome.** Inspect `ok`, `status`, `error`, `results`, `restoration`
   and each result's `warnings`. For holdings images, complete the visual branch below before reporting rows.
   For a waiting legacy copy operation, read only the recovery
   route below. For inconsistent data, read only the interpretation route.
6. **Report.** Present a concise account-specific result. Report partial results
   and unresolved warnings explicitly. Report client-display timestamps and
   restoration status; keep private account data out of public files.

## Branches and return points

- `USER_VERIFICATION_REQUIRED`: ask the user to complete the visible verification.
  Preserve the operation ID. After confirmation, use `operations resume <id>`;
  return to step 5. Resume consumes the original copy, without issuing another.
- `OPERATION_PENDING`: inspect `operations status <id>` and follow the recovery
  route. Do not start a replacement copy to get around an unfinished operation.
- `WINDOW_BUSY`, `WINDOW_BLOCKED`, `HOLDINGS_PAGE_REQUIRED`, or failed doctor:
  explain the named condition, let the user restore the required desktop/page,
  then return to step 2. Do not dismiss dialogs or change credentials automatically.
- Expired, unresumable, or uncertain requests: report the operation state.
  `operations abandon <id> --yes` records abandonment and releases the query gate;
  it does not dismiss a dialog or restore the account. Use only when the user
  chooses to abandon that operation, then return to step 2.
- Unsupported capability: terminate with `FEATURE_UNSUPPORTED`. There is no
  real-order submission, cancellation or login implementation.

## On-demand knowledge

Do not read the knowledge layer merely upon Skill selection. At a corresponding
knowledge-dependent node, read [schema](references/SCHEMA.md),
[index](references/index.md), the recent [log](references/log.md), and the named
query route in one batch, then its topic before interpreting the evidence.
Later-node topics and maintenance provenance remain deferred.

- **Recovery node:** input is an unfinished operation. Question: can its original
  copy be resumed safely? Read [recovery route](references/queries/recover-copy.md).
  Output a resume/await/abandon decision with evidence; return to step 5.
- **Interpretation node:** input is returned data plus warnings. Question: what
  does this client snapshot actually establish? Read
  [interpretation route](references/queries/interpret-snapshot.md).
  Output attributed results and uncertainty; return to step 6.

## Execution and QA boundary

Use `tradecli --help` and `tradecli schema` for the current command/output contract.
CLI JSON uses protocol 1; exit 2 indicates a failed or waiting request. Windows
worker errors are string codes; host errors contain `error.code`.
The package manages configuration, runtime, operation records and Codex Skill
installation. Account passwords and CAPTCHA answers are never CLI inputs.
New holdings reads capture the window without copy/export. Legacy recovery can
consume an existing clipboard payload. Report restoration
failure even if some rows were retrieved. Never treat simulated UI interaction
with a funded account as a simulated-money trading account.

New failures enter a separately authorized development change to the worker,
CLI contract or relevant knowledge topic. Ordinary runs do not rewrite the Skill
or execute the development test suite. Clean-context regression is not claimed.

## Visual holdings branch → step 5

`positions list` and snapshots return `review_required` and private image paths.
Inspect each image with Codex image viewing. Verify account attribution, every row,
and that the entire holdings table fits visibly. If clipped, obscured, ambiguous,
or stale, report incomplete; never fill missing rows from memory or another image.
Do not fall back to copy/export. Capture again only after the page is readable.

Write a new private JSON file (outside the package) with:

```json
{"capture_id":"<returned-id>","image_sha256":"<returned-hash>","complete":true,"all_rows_visible":true,"rows":[{"code":"000001","name":"Example","quantity":"100","available":"100","market_value":"1000.00"}]}
```

Run `positions review --capture <id> --input <file>` and preserve reconciliation
warnings. The deterministic check validates the review, not the visual transcription
itself. Only report complete holdings after image review and reconciliation.
Return to step 5; use the interpretation knowledge route for disagreement.

## Simulated order branch → step 6

1. Resolve the intended account from `accounts list`; use `accounts select` when
   switching is requested. Verify the label explicitly identifies simulated trading
   and inspect its watermark before testing. Off-hours do not establish simulation.
2. Obtain side, six-digit code, limit price and shares from the authorized task.
   `orders open` and `orders inspect --side <side> --account <id>` inspect the form.
   If amount mode is active, `orders quantity-mode` switches a blank form to shares.
   `orders clear ... --yes` is only for explicitly authorized or task-owned drafts.
3. `orders prepare --side <buy|sell> --account <id> --code <code> --price <price>
   --quantity <shares>` fills and reads back the form, then returns a preview and
   `draft_id`. Inspect the preview and ensure it matches the authorized instruction.
4. For authorized simulated execution, run `orders submit-simulated --draft <id>
   --account <id>`. Inspect the confirmation; `orders confirm-simulated` binds its
   account, side, code, price and quantity before confirming once. Draft expiry is
   five minutes. Each stage persists its attempt before interacting with the UI.
5. `orders result --draft <id>` inspects current dialogs. A recognized success
   receipt may be closed using `orders acknowledge --draft <id> --account <id>`.
   `orders ledger --account <id>` captures refreshed current-day orders for visual
   comparison of contract number, side, code, shares, price and execution status.
6. Report preparation, submission acceptance and fill status separately, including
   contract number when visible. No receipt means `submission_unconfirmed`, not
   success. Do not resubmit an uncertain draft or make a replacement draft to retry.
   Report the unresolved result and return to step 6 of the main line.

`ORDER_READBACK_MISMATCH`, `ORDER_ACCOUNT_MISMATCH`, `ORDER_CONFIRMATION_MISMATCH`,
`FORM_DRAFT_PRESENT` or unknown dialogs stop submission. Inspect the named state;
preserve user-owned drafts and do not dismiss unknown dialogs. CAPTCHA is completed
by the user. `ORDER_ALREADY_ATTEMPTED` returns to result/ledger inspection only.

## Simulated batch branch → step 6

1. Resolve the intended simulated account from `accounts list`. Accept an authorized
   plan of 1–10 distinct securities with side, six-digit code, limit price and shares.
   Store the plan in a private JSON file as `{"orders":[{"side":"buy","code":"600001","price":"1.23","quantity":"100"}]}`.
2. Run `batches validate --input <file>`, then `batches prepare --input <file>
   --account <id>`. Compare the returned orders, estimated buy total, available
   funds and account with the authorized plan. Preparation expires in five minutes.
3. Execute once using `batches run-simulated --batch <batch_id> --account <id>
   --digest <digest>`. One Windows worker runs the batch serially. Each order is
   saved before submit and confirmation, matched to its confirmation dialog,
   then polled for an explicit success receipt with contract number. A recognized
   receipt is acknowledged before the next order.
4. Inspect `batches status --batch <batch_id>` and `orders ledger --account <id>`.
   Match accepted contract numbers to the visible ledger and distinguish accepted
   from filled. If a row is `unknown` or the batch `needs_attention`, report the
   last confirmed contract and unattempted rows. Do not rerun or replace uncertain
   orders. Return to step 6 of the main line.

Batch commands submit only in a currently selected simulated account. A real
account, changed form, verification dialog or unexpected response stops execution.
