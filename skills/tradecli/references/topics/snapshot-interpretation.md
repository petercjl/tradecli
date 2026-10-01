# Snapshot interpretation

Observed behavior (E): switching a dropdown label can precede refresh of the
holdings page. Some account totals can briefly show zero while rows remain.
The adapter requires explicit selection notifications and a changed, stable funds
display when switching. Equal displays fail closed rather than proving a switch.
This is client-level evidence, not broker account authentication.

Compare row market value with displayed stock value, then row market value plus
cash with displayed total assets. Preserve warnings on disagreement; do not edit
values to force a match or silently reuse an older successful read.

Accounts are addressed by hashes of discovered labels. Labels may be masked;
duplicate labels are ambiguous. Six-digit security codes and decimal strings are
preserved. A window screenshot and stable account attribution establish displayed evidence,
not server freshness. Legacy clipboard recovery also checks the emitting process. Use the timestamps and client_display_only freshness label.

Multi-account snapshots are sequential, not simultaneous. Partial results retain
their own account attribution. Report restoration failure independently of rows.
