# Copy recovery

Observed client behavior (E): copying a holdings grid can open a security-code
dialog. Empty untitled auxiliary windows also exist; their existence alone is
not CAPTCHA evidence. A temporarily disabled main window can mean busy.

The worker persists its checkpoint before sending one copy request (U/design).
Resume requires the same process, window and account, a checkpoint no older than
five minutes, a changed clipboard sequence and clipboard ownership by the client.
Changing the clipboard during verification can invalidate provenance. A crash
before the copy was actually sent can leave an unresumable checkpoint: status is
honest uncertainty, not permission to copy again automatically.

If a CAPTCHA remains, wait for manual completion. If a valid operation remains,
resume it. If expired or invalid, explain that the old request cannot establish
freshness; explicit abandonment releases the gate but leaves the UI unchanged.
A new query after abandonment must wait until the client is ready.

Gap: synthetic tests cover resume without recopying; real CAPTCHA completion and
recovery must be verified on the deployed client before claiming unattended use.
