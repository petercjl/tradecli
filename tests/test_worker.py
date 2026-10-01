"""Offline checks for the read-only adapter's fail-closed guards."""
import unittest
import time
from types import SimpleNamespace
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from ths import ReadOnlyTHS


def window(handle, title="", children=(), enabled=True):
    return SimpleNamespace(handle=handle, window_text=lambda: title,
                           descendants=lambda: list(children),
                           is_enabled=lambda: enabled)


class Guards(unittest.TestCase):
    def client(self, enabled=True, extras=()):
        c = ReadOnlyTHS.__new__(ReadOnlyTHS)
        c.window = window(1, "main", enabled=enabled)
        c.app = SimpleNamespace(windows=lambda **kwargs: [c.window, *extras])
        return c

    def test_empty_helper_does_not_block_logged_in_window(self):
        self.client(extras=[window(2)]).check_ready()

    def test_disabled_main_blocks_queries(self):
        with self.assertRaisesRegex(RuntimeError, "WINDOW_BUSY"):
            self.client(enabled=False).check_ready()

    def test_titled_or_populated_dialog_blocks_queries(self):
        child = SimpleNamespace(class_name=lambda: "Static", window_text=lambda: "Notice")
        for popup in [window(2, "notice"), window(2, children=[child])]:
            with self.subTest(popup=popup):
                with self.assertRaisesRegex(RuntimeError, "WINDOW_BLOCKED"):
                    self.client(extras=[popup]).check_ready()

    def test_verification_requires_explicit_visible_evidence(self):
        child = SimpleNamespace(class_name=lambda: "Static", window_text=lambda: "请输入验证码")
        with self.assertRaisesRegex(RuntimeError, "USER_VERIFICATION_REQUIRED"):
            self.client(extras=[window(2, children=[child])]).check_ready()

    def test_resume_consumes_existing_request_without_copying(self):
        c = self.client()
        c.app.process = 42
        c.accounts = lambda: {"current_account": "test-account"}
        c.control = lambda *args: self.fail("Resume must not operate any grid")
        checkpoint = {"schema_version": 1, "requested_at": time.time(),
                      "process_id": 42, "window_handle": 1, "account": "test-account",
                      "clipboard_sequence": 10}
        c._collect_copy = lambda pending: pending
        self.assertIs(c.resume(checkpoint), checkpoint)

    def test_resume_rejects_changed_account_or_expired_request(self):
        c = self.client()
        c.app.process = 42
        c.accounts = lambda: {"current_account": "test-account"}
        c._collect_copy = lambda pending: self.fail("Invalid request must not read clipboard")
        checkpoint = {"schema_version": 1, "requested_at": time.time(),
                      "process_id": 42, "window_handle": 1, "account": "different-account",
                      "clipboard_sequence": 10}
        with self.assertRaisesRegex(RuntimeError, "ACCOUNT_MISMATCH"):
            c.resume(checkpoint)
        checkpoint["requested_at"] -= 301
        with self.assertRaisesRegex(RuntimeError, "EXPIRED"):
            c.resume(checkpoint)

    def test_duplicate_visible_controls_are_not_silently_selected(self):
        c = self.client()
        ctrl = SimpleNamespace(class_name=lambda: "Static", control_id=lambda: 1012,
                               is_visible=lambda: True)
        c.window.descendants = lambda: [ctrl, ctrl]
        with self.assertRaisesRegex(RuntimeError, "VISIBLE_CONTROL_AMBIGUOUS"):
            c.control("Static", 1012)

    def test_hidden_duplicate_is_excluded(self):
        c = self.client()
        visible = SimpleNamespace(class_name=lambda: "Static", control_id=lambda: 1012,
                                  is_visible=lambda: True)
        hidden = SimpleNamespace(class_name=lambda: "Static", control_id=lambda: 1012,
                                 is_visible=lambda: False)
        c.window.descendants = lambda: [hidden, visible]
        self.assertIs(c.control("Static", 1012), visible)


if __name__ == "__main__":
    unittest.main()
