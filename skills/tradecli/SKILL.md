---
name: tradecli
description: Query logged-in Windows THS accounts, funds and holdings from Codex using tradecli; diagnose the local connection and resume interrupted holdings copies.
---

# tradecli

Codex-only, platform-specific Skill distributed with `@petercjl/tradecli`.
The CLI and bundled Windows worker are the execution source of truth.

## Input → strategy → output

Input: a query intent and optional account IDs. Default to the current account;
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
   for canonical instructions. This Skill requires protocol 1 and CLI 0.1.x.
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
   initial account on completion; pending copies keep the target selected.
5. **Handle outcome.** Inspect `ok`, `status`, `error`, `results`, `restoration`
   and each result's `warnings`. For a waiting operation, read only the recovery
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
- Unsupported capability: terminate with `FEATURE_UNSUPPORTED`. This version
  supplies queries only; it has no buy, sell, cancel or login implementation.

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
Holdings reads change Windows clipboard and table selection. Report restoration
failure even if some rows were retrieved. Never treat simulated UI interaction
with a funded account as a simulated-money trading account.

New failures enter a separately authorized development change to the worker,
CLI contract or relevant knowledge topic. Ordinary runs do not rewrite the Skill
or execute the development test suite. Clean-context regression is not claimed.
