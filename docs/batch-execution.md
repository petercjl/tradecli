# Simulated batch execution

`batches validate` checks a private JSON file of 1–10 distinct securities.
`batches prepare` binds the ordered list to the selected account, checks displayed
available funds for buys and returns a batch ID plus SHA-256 digest. Execution
requires both values and begins within five minutes.

For THS's current form default price, use `batches validate-default` and
`batches prepare-default` with rows containing only `side`, `code` and `quantity`.
Preparation reads and previews the default price for each code, then clears its
form. After the user confirms the whole list, the same `batches run-simulated`
command re-reads each default price at execution and binds that exact value to
the confirmation dialog. The execution price can differ from the preview.
If the client leaves the price empty or changes a field, the batch stops.
The CLI requires `--yes` on execution after the user confirms the account,
order directions, stock codes and share quantities.

`batches run-simulated` attaches one Windows worker to the THS desktop and handles
orders serially. For each row it fills the form, reads back account and fields,
records `submit_attempted`, clicks once, validates the confirmation dialog,
records `confirm_attempted`, sends the dialog accelerator, and polls for a success
receipt carrying a contract number. It acknowledges that receipt and checks the
form before advancing. The SQLite operation record is committed at each boundary.

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
