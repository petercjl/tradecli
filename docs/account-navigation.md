# Account switching from another page

Account-bound queries and `accounts select` can start on a different client page.
When the requested account differs from the current account, the worker first
opens the funds/holdings page, checks that the account stayed unchanged, reads its
funds, then switches and verifies the destination label and refreshed funds.

Visible order drafts, verification dialogs and unknown blocking windows stop
navigation. Identical or unrefreshed destination funds still fail closed. Queries
restore the original account; `accounts select` intentionally keeps the target.
This navigation does not submit orders.
