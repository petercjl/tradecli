# Account-bound batch execution

`batches plan-market` accepts a private strategy file and a recent, reconciled
`positions review` result. Strategy input is either ordered buy/sell share deltas
(`orders`) or target holdings (`targets`). It calculates before/after shares,
checks sellable quantity, binds the account and writes a private executable order
file. The Codex Skill presents every row and the account in a confirmation table
before preparing or running the batch. The plan contains no prices.

`batches validate` checks a private JSON file of 1–15 orders. Buy codes must
be unique within a batch; sell orders may split one held security into multiple
rows. Each row has its own at-most-once checkpoint and receipt. Long requests
travel as private files over the configured Windows transport, with SHA-256
verification before the worker reads them.
`batches prepare` binds the ordered list to the selected account, checks displayed
available funds for buys and returns a batch ID plus SHA-256 digest. Execution
requires both values and begins within five minutes.

For THS's current form default price, use `batches validate-default` and
`batches prepare-default` with rows containing only `side`, `code` and `quantity`.
Preparation validates the list and account without touching each order form.
After the user confirms the whole list, the same `batches run-simulated`
command reads each default price at execution and binds that exact value to
the confirmation dialog. The price is taken from the client at execution time.
If the client leaves the price empty or changes a field, the batch stops.
The CLI requires `--yes` on execution after the user confirms the account,
order directions, stock codes and share quantities.

For market orders, use `batches validate-market`, `batches plan-market`, and
`batches prepare-market` (or `batches prepare-real-market` for a real account).
The worker opens 市价委托 for each row, enters the stock code, then reads the
available strategy selected by THS. The strategy differs by stock, exchange and
account. It reads the displayed 最新价格 as a reference but never types it. The
worker validates stock code, share count and exact strategy again before the
first click, then validates the market-order confirmation before the final click.
An unsupported strategy, changed form or unknown result stops the remaining rows.
The displayed reference is not a fixed execution price; the exchange may fill at
different prices, partially fill, or cancel the remainder according to the
selected market-order strategy.

`batches run-simulated` attaches one Windows worker to the THS desktop and handles
orders serially. For each row it fills the form, reads back account and fields,
records `submit_attempted`, clicks once, validates the confirmation dialog,
records `confirm_attempted`, sends the dialog accelerator, and polls for a success
receipt carrying a contract number. It acknowledges that receipt and checks the
form before advancing. The SQLite operation record is committed at each boundary.

For a real funded account, `batches prepare-real-market` verifies that the
currently selected THS account ID and type match the plan, then
`batches run-real` repeats that check before and during each order. A simulated
batch cannot be run through the real command or vice versa. Real execution has
the same at-most-once checkpoints, dialog validation, receipt polling, and
stop-on-uncertainty behavior as simulated execution. The real-account path has
automated tests and read-only Windows form inspection. A simulated market-order
confirmation was inspected and canceled before final submission. No live
funded-account market-order submission has been performed.

An ambiguous or absent receipt stops the batch with `needs_attention`; the
attempted row becomes `unknown`, later rows remain queued. A recognized contract
may remain `accepted` if a later cleanup step fails. There is no automatic retry
or resume of an attempted batch. `batches status` marks an interrupted `running`
record for manual attention. `orders ledger` provides independent visual evidence
of current-day acceptance and fill status. A client receipt establishes acceptance,
not execution. Passwords, account labels and order files stay outside the package.

The macOS → Parallels → Windows simulated-account smoke test completed two buys
in one worker in about 15 seconds; both receipt contract numbers appeared in the
current-day ledger as unfilled. This is a functional sample, not a throughput or
reliability guarantee. Native Windows remains untested.
