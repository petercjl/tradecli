"""Regression coverage for the embedded browser helper readiness check."""
import unittest
from types import SimpleNamespace as NS
from test_worker import Guards, window

class HiddenBrowserGuard(unittest.TestCase):
    def helper(self, cls="Internet Explorer_Hidden", size=0, visible=False, title="", child_cls="Internet Explorer_Server"):
        child = NS(class_name=lambda: child_cls, window_text=lambda: "", is_visible=lambda: visible)
        w = window(2, title, [child])
        w.class_name = lambda: cls
        w.rectangle = lambda: NS(left=0, top=0, right=size, bottom=size)
        return w

    def test_zero_area_invisible_browser_helper_is_nonblocking(self):
        Guards().client(extras=[self.helper()]).check_ready()

    def test_only_exact_helper_shape_is_exempt(self):
        for params in [dict(cls="OtherWindow"), dict(size=10), dict(visible=True),
                       dict(title="Notice"), dict(child_cls="Static")]:
            with self.subTest(params=params):
                with self.assertRaisesRegex(RuntimeError, "WINDOW_BLOCKED"):
                    Guards().client(extras=[self.helper(**params)]).check_ready()

    def test_disabled_main_still_blocks_with_helper(self):
        with self.assertRaisesRegex(RuntimeError, "WINDOW_BUSY"):
            Guards().client(enabled=False, extras=[self.helper()]).check_ready()
