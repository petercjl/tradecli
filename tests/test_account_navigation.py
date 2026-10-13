"""Account switching must navigate safely before reading cached funds controls."""
import unittest
from unittest.mock import Mock
from test_worker import Guards


class AccountNavigation(unittest.TestCase):
    def client(self):
        c = Guards().client()
        state = {"current_account": "original", "accounts": [
            {"label": "original", "index": 0}, {"label": "target", "index": 1}]}
        c.accounts = Mock(return_value=state)
        c.open_page = Mock()
        c.funds = Mock(side_effect=RuntimeError("TEST_FUNDS_REACHED"))
        return c

    def test_navigation_precedes_funds_read(self):
        c = self.client()
        c.funds.side_effect = lambda: self.assertEqual(c.open_page.call_args.args, ("holdings",)) or (_ for _ in ()).throw(RuntimeError("TEST_FUNDS_REACHED"))
        with self.assertRaisesRegex(RuntimeError, "TEST_FUNDS_REACHED"):
            c.switch("target")
        c.open_page.assert_called_once_with("holdings")

    def test_draft_and_dialog_failures_prevent_switch(self):
        for error in ("FORM_DRAFT_PRESENT", "WINDOW_BLOCKED", "USER_VERIFICATION_REQUIRED"):
            c = self.client()
            c.open_page.side_effect = RuntimeError(error)
            with self.assertRaisesRegex(RuntimeError, error):
                c.switch("target")
            c.funds.assert_not_called()

    def test_account_change_during_navigation_stops_read(self):
        c = self.client()
        before = c.accounts.return_value
        c.accounts.side_effect = [before, dict(before, current_account="other")]
        with self.assertRaisesRegex(RuntimeError, "ACCOUNT_CHANGED_DURING_READ"):
            c.switch("target")
        c.funds.assert_not_called()

    def test_same_or_unknown_account_does_not_navigate(self):
        c = self.client()
        c.switch("original")
        c.open_page.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "ACCOUNT_NOT_FOUND_OR_AMBIGUOUS"):
            c.switch("missing")
        c.open_page.assert_not_called()
