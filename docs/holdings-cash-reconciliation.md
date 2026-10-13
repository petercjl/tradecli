# Available funds and holdings review

The displayed 可用金额 (available funds) is the sole buying-budget field. It must be present, finite, nonnegative and a valid decimal string. Zero is valid and grants no buying budget. There is no fallback to 资金余额, 可取金额 or 总资产.

Visual review preserves original fund values. Balance-plus-stock versus total-assets discrepancies are informational reconciliation notes, independent of buying power. Lower available funds are retained when funds are frozen. Stock-row market values must still match displayed stock value; account, evidence, completeness and share checks remain blocking.

Signed decimal zero is accepted as numeric zero. This is client-display evidence, not broker-server verification. Query fresh available funds when preparing a budget; a historical review is not current spending authority.
