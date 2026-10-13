# THS window capture sizing

The Windows worker allocates the PrintWindow surface from the window rectangle
and the current GetDpiForWindow value, rounding pixel dimensions upward from
96-DPI layout units. It retains the native rendered pixels. Invalid DPI and
oversized surfaces fail closed. No desktop scaling or window placement is changed.

Regression coverage includes 100%, 125%, 150%, and 250% size calculations,
unavailable DPI, and allocation limits. A real macOS/Parallels Windows THS
holdings capture at 250% showed the full window, all holdings rows, rightmost
columns, and bottom totals. Other scale settings have calculation tests only;
visual review remains required. The host CLI and Windows worker retain the same capture/review contract.
