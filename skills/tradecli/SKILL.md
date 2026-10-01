---
name: tradecli
description: Use tradecli in Codex to query THS accounts, synchronize a JoinQuant simulated portfolio by selling absent stocks before equal-cash buys, plan holdings changes, execute confirmed simulated or real-account batches, and reconcile orders.
---

# tradecli

Codex-only, platform-specific Skill distributed with `@petercjl/tradecli`.
The CLI and bundled Windows worker are the execution source of truth.

## Input → strategy → output

Input: a query or trading strategy, with an optional account (default: the currently
selected THS account). A trading strategy can specify per-security buy/sell shares
or target holdings; resolve ambiguous quantities before planning.
Strategy: inspect readiness, bind one account, review fresh holdings, calculate
an exact share-change table, obtain confirmation of that table, execute the
account-specific batch once, then reconcile contracts and fills.
Output: account-bound query data or a per-order batch report. Distinguish the
planned post-trade shares from actual holdings and distinguish accepted orders
from filled orders. Never infer a successful submission from an incomplete receipt.

## Main line

1. **Discover.** Run `tradecli version` and `tradecli capabilities --json`.
   Load [Codex adapter](adapters/codex.json) to resolve the execution contract.
   If missing, install the user-authorized npm package; use `tradecli skill source`
   for canonical instructions. This Skill requires protocol 1 and CLI 0.4.0-dev.0 or newer for the JoinQuant synchronization branch; other branches remain available in 0.3.x.
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
- Unsupported capability: terminate with `FEATURE_UNSUPPORTED`. Real-account
  orders use confirmed market-order batches; individual real-order submission,
  cancellation and login are not implemented.

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

## Strategy-to-batch branch → step 6

Use this branch when the user supplies a buy/sell list, target holdings, or a
portfolio adjustment strategy. It applies to simulated and real accounts.

1. Run `accounts list` and bind exactly one account. If none is specified, use its
   `account_id` for the currently selected account. A masked label is an identity
   aid, not proof of account type. Select a different account only when requested.
   Verify whether the bound account is simulated or real from the current THS
   account label; state the type prominently in the confirmation.
2. Obtain fresh holdings through `positions list --account <id>` and complete the
   visual holdings branch, including `positions review`. Use its `review_path`.
   If the user gives a general strategy, convert it to concrete six-digit codes
   and integer share quantities. Resolve missing stock names from a reliable,
   current source and verify held names against the reviewed holdings. A code
   without a verified name cannot enter the confirmation table. If the strategy
   uses weights, budgets, or phrases that do not determine exact share counts,
   resolve them before planning. The plan changes only named securities; other
   holdings stay as they are.
3. Write a private strategy JSON outside the package. Choose one form:

   ```json
   {"orders":[{"code":"600221","name":"海航控股","side":"buy","quantity":"100"}]}
   ```

   ```json
   {"targets":[{"code":"300359","quantity":"300"},{"code":"600221","name":"海航控股","quantity":"100"}]}
   ```

   Held-stock names come from the holdings review and may be omitted. In
   `orders`, repeated sell rows are allowed; each row's current shares are the
   shares immediately before that row in plan order. Run `batches plan-market
   --strategy <file> --review <review_path> --account <id>`. This command rejects
   stale or inconsistent holdings, account/name mismatches, unavailable sell
   shares, empty target changes, and invalid batches. It returns `orders_path`,
   `plan_path`, and rows with before and planned-after quantities. The strategy
   does not contain prices.
4. Show the user the account label/type and a table with these columns in order:
   **序号、股票代码、股票名称、当前持股数、方向、买卖股数、操作后持股数**.
   Include all rows in execution order. The last column is the planned holding
   count after that row's order fills, not a guarantee of execution. Ask for one
   explicit confirmation of this account and complete table. A changed strategy,
   account, holdings, or row order requires a new plan and confirmation. Do not
   treat `--yes` as a substitute for the user's confirmation.
5. After confirmation, use `batches prepare-market --input <orders_path>
   --account <id>` for a simulated account, or `batches prepare-real-market`
   for a real account. Compare its returned account, order sequence, quantities,
   mode, and digest with the confirmed plan. Preparation expires in five minutes.
   Ensure THS has the bound account selected. Run the matching `batches
   run-simulated` or `batches run-real --batch <id> --account <id> --digest
   <digest> --yes` once. The Windows worker submits orders serially through
   市价委托. For each stock it reads the available market strategy after entering
   the code, leaves the THS reference-price field untouched, checks the full
   confirmation, and stops on an unavailable market strategy, unexpected
   dialog, account change, or unknown receipt. It never retries an attempted row.
6. Run `batches status --batch <id>`, then `orders ledger --account <id>` and
   visually match every accepted contract number to code, side, quantity, and
   status in the same account. If the ledger is clipped, ambiguous, or blocked,
   report verification as incomplete. Report every planned row as accepted,
   rejected, unknown, or unattempted, with contract number and actual fill count
   when verified. Compute actual post-batch holdings only from refreshed reviewed
   holdings or verified fills; label unfilled orders as pending. If a row is
   `unknown` or the batch needs attention, report the last verified contract and
   remaining unattempted rows. The final output has an account/batch summary and
   a row table with **序号、代码、名称、方向、委托股数、合同编号、委托状态、已成交股数、实际持股数**.
   Use `待核实` when fills or actual holdings cannot be independently verified.
   Never rerun or replace uncertain orders. Return to step 6 of the main line.

If a batch stops with `FORM_DRAFT_PRESENT` while every row is still `queued`,
no order in that batch was submitted. Inspect the currently visible form with
`orders inspect` and identify its owner. For a draft created by this task,
check the current-day ledger first, then use `orders clear --side <side>
--account <id> --yes` and verify all fields are blank. A prior row with no
receipt remains `unknown` even if the ledger has no matching entry; never
resubmit it. Once the form is blank, a batch with zero attempted rows may be
prepared again from the same confirmed plan while the account and holdings
evidence remain current. Any batch with an attempted row stays terminal and
requires a newly confirmed plan for different, unattempted orders. Return to
step 5 of this branch.

For real accounts, the confirmation table is authorization for this exact batch
only. Read-only planning and preparation do not authorize another batch. The
worker checks the real-account identity immediately before and during every
order. Any verification prompt is handled manually by the user; stop rather than
clicking through it. The Codex Skill and CLI may be tested on macOS with a
Parallels Windows client. A real-account order attempt exercised the ordinary
order confirmation path and was rejected by THS before acceptance. A market
order confirmation was inspected in a simulated account and canceled before
final submission. Market-order acceptance and fill in a funded account remain
untested. If THS shows a later rejection outside the worker's receipt window,
report that client evidence alongside the batch's `unknown` state and leave
subsequent rows unattempted.

## Legacy simulated batch branch → step 6

1. Resolve the intended simulated account from `accounts list`. Accept an authorized
   plan of 1–15 orders with side, six-digit code, limit price and shares.
   Buy codes are unique; a held security can appear in multiple sell rows
   when the user confirms those separate quantities.
   Store the plan in a private JSON file as `{"orders":[{"side":"buy","code":"600001","price":"1.23","quantity":"100"}]}`.
2. Run `batches validate --input <file>`, then `batches prepare --input <file>
   --account <id>`. Compare the returned orders, estimated buy total, available
   funds and account with the authorized plan. Preparation expires in five minutes.
   Confirm the complete account, side, code, price and quantity list with the
   user before running.
3. After explicit user confirmation, execute once using `batches run-simulated
   --batch <batch_id> --account <id> --digest <digest> --yes`. One Windows worker runs the batch serially. Each order is
   saved before submit and confirmation, matched to its confirmation dialog,
   then polled for an explicit success receipt with contract number. A recognized
   receipt is acknowledged before the next order.
4. Inspect `batches status --batch <batch_id>` and `orders ledger --account <id>`.
   Match accepted contract numbers to the visible ledger and distinguish accepted
   from filled. If a row is `unknown` or the batch `needs_attention`, report the
   last confirmed contract and unattempted rows. Do not rerun or replace uncertain
   orders. Return to step 6 of the main line.

This legacy branch remains for explicitly priced simulated tests. The ordinary
form's automatic default-price path remains available through `batches
plan-default`, `batches prepare-default`, and `batches prepare-real-default`.
Use the strategy-to-batch branch for market-order strategies on either account type.

## JoinQuant simulated-portfolio synchronization → step 6

Use this branch for a request such as “根据聚宽模拟策略‘小市值周策略’同步当前账户”. The exact nested Skill dependency is `jqcli` (installed and advertised by the host); read its current complete `SKILL.md` and relevant `live` command reference at execution time. Require `jqcli` 0.1.0 or newer with JSON `live positions --name` output. If unavailable, return `JQCLI_QUERY_FAILED` and stop; do not substitute a remembered portfolio. After the JoinQuant query, return here at step 2.

1. Bind one THS account with `accounts list`. The default is the currently selected account. Show whether it is a simulated or real account. Obtain a fresh `positions list --account <id>` screenshot and complete the visual holdings branch. Compare six-digit stock codes, not target share counts or portfolio weights. The review records quantities internally because full exits require sellable shares; show the user only the fields needed for the plan. Require all rows visible and the account-bound `review_path`.
2. Run `sync plan --strategy-name <exact JoinQuant live name> --review <review_path> --account <id>`. It invokes `jqcli live positions`, checks the exact strategy name, complete stock list and common strategy timestamp, and writes a private account-bound plan and sell orders. An incomplete or ambiguous JoinQuant result, stale THS review, or position with unavailable shares stops the plan. Requery the strategy on the trading day if its as-of date has changed.
3. Display the **entire two-stage plan** before any order: account and type, JoinQuant strategy/as-of time; for each sell, code, name, current and available shares, sell quantity and planned remaining shares; for each buy, code, name, current shares and one equal share of the *post-sale usable cash*. Explain that exact buy shares depend on later cash and fresh THS reference prices, and that the execution price of a market order can differ. Ask for explicit confirmation of this plan and account. Changed holdings, strategy target, or account require a new plan and confirmation.
4. Only after confirmation, prepare and run the sell orders as a separate account-bound market batch using the matching simulated or real commands. Inspect `batches status` and a fresh `orders ledger` screenshot. Treat acceptance as pending, not filled. Record every contract number, submitted and filled quantity in a private JSON file of the form `{"account_id":"<bound-account-id>","batch_id":"<sell-batch-id>","ledger_capture_id":"<captured-ledger-id>","orders":[{"code":"002051","status":"filled","filled_quantity":"100","contract_number":"123"}]}`. The visual evidence must show that every sell is fully filled. Unknown, rejected, partly filled or unattempted sells stop this sync; do not retry them automatically. If there are no sells, use an empty `orders` array and proceed to fresh holdings and cash.
5. After all sells fill, read a new holdings image and complete `positions review` again. All sold codes must be absent, and `可用金额` must be displayed in the same refreshed account snapshot. `sync quotes --plan <plan_path> --account <id>` reads each buy stock's displayed 市价委托 reference field after entering its code; it does not submit an order. It saves a private quote file. Run `sync allocate --plan <plan_path> --review <fresh_review_path> --fills <verified_fills.json> --quotes <quotes_path> --sell-batch <sell-batch-id>` (omit the batch option only when the plan has no sells). This deterministic gate checks the persisted sell-batch contracts against the visually verified fills, then rejects still-held sell codes, account changes, stale quotes, or insufficient cash for a minimum lot. It divides current usable cash evenly among only the absent strategy stocks, reserves 2% plus ¥5 per order, and rounds each estimated buy to 100 shares. Display the exact new share quantities for confirmation. The original approval covers the portfolio method; exact-share confirmation is needed because these quantities become known only after settlement and may differ materially from the earlier estimate.
6. After exact-share confirmation and a final account/strategy/quote check, prepare the returned buy `orders_path` as a *new* market batch and run it once. Refresh available cash if execution is delayed or the client price changes; if quantities change, regenerate and reconfirm the table. Reconcile each contract and fill against the current-day ledger and a refreshed holdings image. Report planned, accepted, filled, pending and unknown states separately. Leave unknown outcomes to manual handling; never issue a replacement order automatically. Return to the main line's report step.

The current market reference field estimates quantity; it does not lock execution price. The broker may reject an order for insufficient funds or unsupported market strategy. The 2% reserve is a sizing buffer, not a guarantee. On a market holiday or outside an accepted order window, complete read-only planning and wait for a fresh strategy and account snapshot when trading resumes. No execution is scheduled by this Skill.
