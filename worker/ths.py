"""THS queries and explicitly bound simulated-account order operations."""
import argparse
import json
import sys
import time
from decimal import Decimal


class PendingCopy(RuntimeError):
    def __init__(self, code, checkpoint):
        super().__init__(code)
        self.checkpoint = checkpoint


class ReadOnlyTHS:
    def __init__(self, exe_path, allow_dialogs=False):
        import pywinauto
        self.app = pywinauto.Application(backend="win32").connect(path=exe_path, timeout=5)
        candidates = [w for w in self.app.windows(visible_only=True)
                      if any(c.class_name() == "ComboBox" and c.control_id() == 2322
                             for c in w.descendants())]
        if len(candidates) != 1:
            raise RuntimeError("ACCOUNT_WINDOW_AMBIGUOUS")
        self.window = candidates[0]
        if not allow_dialogs:
            self.check_ready()

    def check_ready(self):
        blocked = False
        for w in self.app.windows(visible_only=True):
            if w.handle == self.window.handle:
                continue
            # THS creates an empty, enabled helper dialog even after login.
            # Any titled or populated extra window remains a blocker.
            children = w.descendants()
            labels = [w.window_text()] + [c.window_text() for c in children
                                          if c.class_name() == "Static"]
            if any("验证码" in text for text in labels):
                raise RuntimeError("USER_VERIFICATION_REQUIRED")
            if w.window_text().strip() or children:
                blocked = True
        if blocked:
            raise RuntimeError("WINDOW_BLOCKED")
        if not self.window.is_enabled():
            raise RuntimeError("WINDOW_BUSY")

    def control(self, class_name, control_id):
        matches = [c for c in self.window.descendants()
                   if c.class_name() == class_name and c.control_id() == control_id
                   and c.is_visible()]
        if len(matches) != 1:
            raise RuntimeError("VISIBLE_CONTROL_AMBIGUOUS")
        return matches[0]

    def accounts(self):
        combo = self.control("ComboBox", 2322)
        labels = combo.item_texts()
        active = [label for label in labels if label and not any(x in label for x in ("编辑账户", "添加账户", "添加账号"))]
        if len(active) != len(set(active)):
            raise RuntimeError("ACCOUNT_LABEL_AMBIGUOUS")
        index = combo.selected_index()
        if index < 0 or index >= len(labels) or "编辑账户" in labels[index]:
            raise RuntimeError("NO_ACCOUNT_SELECTED")
        return {"current_index": index, "current_account": labels[index],
                "accounts": [{"index": i, "label": label}
                             for i, label in enumerate(labels)
                             if label and not any(x in label for x in ("编辑账户", "添加账户", "添加账号"))]}

    def funds(self):
        self.check_ready()
        before = self.accounts()
        if self.control("Static", 2388).window_text().strip() != "资金余额":
            raise RuntimeError("HOLDINGS_PAGE_REQUIRED")
        values = {key: str(Decimal(self.control("Static", cid).window_text().replace(",", "")))
                  for key, cid in {"资金余额":1012,"可用金额":1016,"可取金额":1017,"股票市值":1014,"总资产":1015}.items()}
        self.check_ready()
        if self.accounts() != before:
            raise RuntimeError("ACCOUNT_CHANGED_DURING_READ")
        if not all(Decimal(v).is_finite() for v in values.values()):
            raise RuntimeError("FUNDS_INVALID")
        return dict(before, funds=values, source="visible_client_controls",
                    freshness="client_display_only_not_server_verified")

    def switch(self, account):
        self.check_ready()
        before = self.accounts()
        matches = [a for a in before["accounts"] if a["label"] == account]
        if len(matches) != 1:
            raise RuntimeError("ACCOUNT_NOT_FOUND_OR_AMBIGUOUS")
        if before["current_account"] != account:
            before_funds = self.funds()["funds"]
            import ctypes
            from ctypes import wintypes
            import win32gui

            class ComboInfo(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.DWORD),
                            ("rcItem", wintypes.RECT), ("rcButton", wintypes.RECT),
                            ("stateButton", wintypes.DWORD),
                            ("hwndCombo", wintypes.HWND), ("hwndItem", wintypes.HWND),
                            ("hwndList", wintypes.HWND)]

            combo = self.control("ComboBox", 2322)
            info = ComboInfo()
            info.cbSize = ctypes.sizeof(info)
            get_info = ctypes.windll.user32.GetComboBoxInfo
            get_info.argtypes = [wintypes.HWND, ctypes.POINTER(ComboInfo)]
            get_info.restype = wintypes.BOOL
            if not get_info(combo.handle, ctypes.byref(info)):
                raise RuntimeError("ACCOUNT_LIST_UNAVAILABLE")
            height = win32gui.SendMessage(combo.handle, 0x154, 0, 0)
            if height <= 0:
                raise RuntimeError("ACCOUNT_ITEM_HEIGHT_INVALID")
            index = matches[0]["index"]
            win32gui.SendMessage(combo.handle, 0x14F, 1, 0)
            try:
                win32gui.SendMessage(info.hwndList, 0x197, index, 0)
                top = win32gui.SendMessage(info.hwndList, 0x18E, 0, 0)
                y = int((index - top + 0.5) * height)
                left, upper, right, lower = win32gui.GetWindowRect(info.hwndList)
                if not 0 <= y < lower - upper or right - left <= 10:
                    raise RuntimeError("ACCOUNT_ITEM_NOT_VISIBLE")
                point = 10 | (y << 16)
                win32gui.PostMessage(info.hwndList, 0x200, 0, point)
                win32gui.PostMessage(info.hwndList, 0x201, 1, point)
                win32gui.PostMessage(info.hwndList, 0x202, 0, point)
                time.sleep(0.6)
            finally:
                win32gui.SendMessage(combo.handle, 0x14F, 0, 0)
            # This client updates the combo label without switching its data
            # page until the parent receives the selection notifications.
            parent = win32gui.GetParent(combo.handle)
            win32gui.PostMessage(parent, 0x111, (1 << 16) | 2322, combo.handle)
            win32gui.PostMessage(parent, 0x111, (9 << 16) | 2322, combo.handle)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                time.sleep(0.5)
                self.check_ready()
                first = self.funds()["funds"]
                if first != before_funds and self.accounts()["current_account"] == account:
                    time.sleep(0.5)
                    if self.funds()["funds"] == first:
                        break
            else:
                raise RuntimeError("ACCOUNT_CONTENT_NOT_REFRESHED")
        self.check_ready()
        result = self.accounts()
        if result["current_account"] != account:
            raise RuntimeError("ACCOUNT_SWITCH_FAILED")
        return result

    def capture_positions(self):
        import win32clipboard
        self.open_page("holdings")
        self.check_ready()
        sequence = win32clipboard.GetClipboardSequenceNumber()
        result = self.funds()
        self.control("CVirtualGridCtrl", 1047)
        image = capture_window_png(self.window.handle)
        self.check_ready()
        if self.accounts() != {k: result[k] for k in ("current_index", "current_account", "accounts")}:
            raise RuntimeError("ACCOUNT_CHANGED_DURING_READ")
        unchanged = sequence == win32clipboard.GetClipboardSequenceNumber()
        if not unchanged:
            raise RuntimeError("CLIPBOARD_CHANGED_EXTERNALLY")
        return dict(result, image_base64=base64.b64encode(image).decode("ascii"),
                    captured_at=time.time(), source="window_image", review_required=True,
                    clipboard_unchanged=True)

    def open_page(self, page):
        if page not in ("buy", "sell", "holdings"):
            raise RuntimeError("PAGE_UNSUPPORTED")
        self.check_ready()
        # Navigation must preserve any draft already visible on the desktop.
        edits = [c for c in self.window.descendants() if c.class_name() == "Edit"
                 and c.control_id() in (1032, 1034) and c.is_visible()]
        if any(read_edit(c) for c in edits):
            raise RuntimeError("FORM_DRAFT_PRESENT")
        import win32gui
        key = {"buy": 0x70, "sell": 0x71, "holdings": 0x73}[page]
        win32gui.PostMessage(self.window.handle, 0x100, key, 0)
        win32gui.PostMessage(self.window.handle, 0x101, key, 0)
        time.sleep(0.4)
        self.check_ready()
        if page == "holdings":
            if self.control("Static", 2388).window_text().strip() != "资金余额":
                raise RuntimeError("HOLDINGS_PAGE_REQUIRED")
        else:
            self.order_fields(page)

    def order_fields(self, side):
        self.check_ready()
        if side not in ("buy", "sell"):
            raise RuntimeError("ORDER_SIDE_INVALID")
        button = self.control("Button", 1006)
        expected = "买入" if side == "buy" else "卖出"
        if expected not in button.window_text():
            raise RuntimeError("ORDER_SIDE_MISMATCH")
        values = {key: read_edit(self.control("Edit", cid))
                  for key, cid in (("code",1032),("price",1033),("quantity",1034))}
        label = self.control("Static",1399).window_text()
        unit = "amount" if "金额" in label else "shares" if "数量" in label or "股数" in label else "unknown"
        return dict(side=side, unit=unit, **values)

    def prepare_order(self, request):
        order = validate_order(request)
        def check_account():
            self.check_ready()
            if account_id(self.accounts()["current_account"]) != order["account"]:
                raise RuntimeError("ORDER_ACCOUNT_MISMATCH")
        check_account()
        self.open_page(order["side"])
        if any(self.order_fields(order["side"])[k] for k in ("code","quantity")):
            raise RuntimeError("FORM_DRAFT_PRESENT")
        if self.order_fields(order["side"])["unit"] != "shares":
            raise RuntimeError("ORDER_QUANTITY_MODE_REQUIRED")
        for key, cid in (("code",1032),("price",1033),("quantity",1034)):
            check_account()
            self.order_fields(order["side"])
            control = self.control("Edit",cid)
            if not control.is_enabled():
                raise RuntimeError("ORDER_FIELD_DISABLED")
            # Use easytrader's select/type strategy; verify through EM_GETLINE.
            type_numeric_edit(control, order[key])
            time.sleep(2.0 if key == "code" else 0.3)
        check_account()
        actual = self.order_fields(order["side"])
        if not order_fields_match(actual, order):
            raise RuntimeError("ORDER_READBACK_MISMATCH")
        return dict(actual, account_id=order["account"], submitted=False,
                    status="prepared_for_manual_submission", captured_at=time.time(),
                    image_base64=base64.b64encode(capture_window_png(self.window.handle)).decode("ascii"))

    def default_price_order(self, request, preview=False):
        """Read THS's own price after entering a code; optionally fill shares."""
        side, code, account = (request[key] for key in ("side", "code", "account"))
        self.assert_trading_account(account, request.get("account_kind", "simulated"))
        self.open_page(side)
        fields = self.order_fields(side)
        if any(fields[key] for key in ("code", "price", "quantity")):
            raise RuntimeError("FORM_DRAFT_PRESENT")
        if fields["unit"] != "shares":
            raise RuntimeError("ORDER_QUANTITY_MODE_REQUIRED")
        code_control = self.control("Edit", 1032)
        if not code_control.is_enabled():
            raise RuntimeError("ORDER_FIELD_DISABLED")
        type_numeric_edit(code_control, code)
        time.sleep(2.0)
        self.assert_trading_account(account, request.get("account_kind", "simulated"))
        fields = self.order_fields(side)
        if fields["code"] != code or fields["quantity"]:
            raise RuntimeError("ORDER_DEFAULT_PRICE_UNAVAILABLE")
        price = fields["price"]
        if not isinstance(price, str) or not re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,3})?", price) or Decimal(price) <= 0:
            raise RuntimeError("ORDER_DEFAULT_PRICE_UNAVAILABLE")
        if preview:
            result = {"side":side,"code":code,"price":price,
                      "quantity":request["quantity"],"account":account,
                      "price_source":"ths_default_price_field","captured_at":time.time()}
            for cid in (1034, 1033, 1032):
                self.control("Edit", cid).type_keys("^a{BACKSPACE}", set_foreground=True)
            deadline = time.monotonic()+2
            while True:
                cleared = self.order_fields(side)
                if not any(cleared[key] for key in ("code","price","quantity")):
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("ORDER_CLEAR_FAILED")
                time.sleep(0.2)
            return result
        quantity_control = self.control("Edit", 1034)
        if not quantity_control.is_enabled():
            raise RuntimeError("ORDER_FIELD_DISABLED")
        type_numeric_edit(quantity_control, request["quantity"])
        time.sleep(0.3)
        order = dict(request, price=price)
        validate_order(order)
        if not order_fields_match(self.order_fields(side), order):
            raise RuntimeError("ORDER_READBACK_MISMATCH")
        return dict(order, unit="shares", price_source="ths_default_price_field",
                    captured_at=time.time())

    def open_market_page(self, side):
        if side not in ("buy", "sell"):
            raise RuntimeError("ORDER_SIDE_INVALID")
        self.check_ready()
        edits = [c for c in self.window.descendants() if c.class_name() == "Edit"
                 and c.control_id() in (1032, 1034) and c.is_visible()]
        if any(read_edit(c) for c in edits):
            raise RuntimeError("FORM_DRAFT_PRESENT")
        target = "买入" if side == "buy" else "卖出"
        tree = self.control("SysTreeView32", 129)
        tree.get_item(["市价委托", target]).select()
        time.sleep(0.4)
        self.check_ready()
        if not tree.is_selected(["市价委托", target]):
            raise RuntimeError("MARKET_PAGE_MISMATCH")
        self.market_order_fields(side)

    def market_order_fields(self, side):
        self.check_ready()
        target = "买入" if side == "buy" else "卖出" if side == "sell" else None
        if target is None:
            raise RuntimeError("ORDER_SIDE_INVALID")
        if self.control("Static", 1478).window_text().strip() != "市价" + target:
            raise RuntimeError("MARKET_PAGE_MISMATCH")
        if self.control("Button", 1006).window_text().strip() != target:
            raise RuntimeError("ORDER_SIDE_MISMATCH")
        if "数量" not in self.control("Static", 1399).window_text():
            raise RuntimeError("ORDER_QUANTITY_MODE_REQUIRED")
        combo = self.control("ComboBox", 1541)
        labels = combo.item_texts()
        index = combo.selected_index()
        strategy = labels[index] if 0 <= index < len(labels) else ""
        return {"side": side, "unit": "shares", "code": read_edit(self.control("Edit", 1032)),
                "quantity": read_edit(self.control("Edit", 1034)),
                "reference_price": read_edit(self.control("Edit", 1033)),
                "market_strategy": strategy, "market_strategy_index": index,
                "available_strategies": labels}

    def market_page_active(self, side):
        target = "买入" if side == "buy" else "卖出" if side == "sell" else None
        if target is None:
            raise RuntimeError("ORDER_SIDE_INVALID")
        return any(c.class_name() == "Static" and c.control_id() == 1478
                   and c.is_visible() and c.window_text().strip() == "市价" + target
                   for c in self.window.descendants())

    def reset_market_form(self, side):
        self.market_order_fields(side)
        reset = self.control("Button", 1007)
        if reset.window_text().strip() != "重填":
            raise RuntimeError("MARKET_RESET_MISMATCH")
        reset.click()
        fields = self.market_order_fields(side)
        if fields["code"] or fields["quantity"]:
            raise RuntimeError("ORDER_CLEAR_FAILED")
        return fields

    def market_order(self, request):
        side, code, account = (request[key] for key in ("side", "code", "account"))
        kind = request.get("account_kind", "simulated")
        self.assert_trading_account(account, kind)
        self.open_market_page(side)
        fields = self.market_order_fields(side)
        if fields["code"] or fields["quantity"]:
            raise RuntimeError("FORM_DRAFT_PRESENT")
        control = self.control("Edit", 1032)
        if not control.is_enabled():
            raise RuntimeError("ORDER_FIELD_DISABLED")
        type_numeric_edit(control, code)
        time.sleep(2.0)
        self.assert_trading_account(account, kind)
        fields = self.market_order_fields(side)
        if fields["code"] != code or fields["quantity"]:
            raise RuntimeError("MARKET_ORDER_UNAVAILABLE")
        if (not fields["market_strategy"] or "不支持市价委托" in fields["market_strategy"]
                or fields["market_strategy_index"] < 0):
            self.reset_market_form(side)
            raise RuntimeError("MARKET_ORDER_UNAVAILABLE")
        if (not re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,3})?", fields["reference_price"])
                or Decimal(fields["reference_price"]) <= 0):
            self.reset_market_form(side)
            raise RuntimeError("MARKET_REFERENCE_PRICE_UNAVAILABLE")
        quantity = self.control("Edit", 1034)
        if not quantity.is_enabled():
            raise RuntimeError("ORDER_FIELD_DISABLED")
        type_numeric_edit(quantity, request["quantity"])
        time.sleep(0.3)
        actual = self.market_order_fields(side)
        order = dict(request, market_strategy=fields["market_strategy"],
                     market_strategy_index=fields["market_strategy_index"])
        if not market_fields_match(actual, order):
            raise RuntimeError("ORDER_READBACK_MISMATCH")
        return dict(order, unit="shares", reference_price=actual["reference_price"],
                    captured_at=time.time())

    def assert_simulated(self, expected):
        current = self.accounts()["current_account"]
        if not current.startswith("模拟炒股-") or account_id(current) != expected:
            raise RuntimeError("SIMULATED_ACCOUNT_REQUIRED")

    def assert_trading_account(self, expected, kind):
        current = self.accounts()["current_account"]
        if account_id(current) != expected:
            raise RuntimeError("ORDER_ACCOUNT_MISMATCH")
        if kind == "simulated":
            if not current.startswith("模拟炒股-"):
                raise RuntimeError("SIMULATED_ACCOUNT_REQUIRED")
        elif kind == "real":
            if current.startswith("模拟炒股-"):
                raise RuntimeError("REAL_ACCOUNT_REQUIRED")
        else:
            raise RuntimeError("ACCOUNT_KIND_INVALID")

    def order_response(self):
        dialogs = []
        for window in self.app.windows(visible_only=True):
            if window.handle == self.window.handle:
                continue
            labels = [window.window_text()] + [c.window_text() for c in window.descendants()
                       if c.class_name() == "Static"]
            text = "\n".join(s for s in labels if s.strip())
            if not text:
                continue
            if "验证码" in text:
                return {"status":"verification_required","dialog_text":"验证码需人工处理"}
            buttons = [{"id":c.control_id(),"label":c.window_text()}
                       for c in window.descendants() if c.class_name()=="Button" and c.is_visible()]
            dialogs.append({"text":text,"buttons":buttons})
        return {"status":"dialog_review_required" if dialogs else "submission_unconfirmed", "dialogs":dialogs}

    def confirmation_window(self, order):
        self.assert_trading_account(order["account"], order.get("account_kind", "simulated"))
        label = self.accounts()["current_account"]
        candidates=[]
        for window in self.app.windows(visible_only=True):
            if window.handle == self.window.handle:
                continue
            text="\n".join([window.window_text()]+[c.window_text() for c in window.descendants()
                            if c.class_name()=="Static"])
            matches = (validate_market_confirmation(text, order, label)
                       if order.get("mode") == "market" else validate_confirmation(text, order, label))
            if matches:
                buttons=[c for c in window.descendants() if c.class_name()=="Button"
                         and c.control_id()==6 and c.is_visible() and c.window_text().startswith("是")]
                if len(buttons)==1:
                    candidates.append(window)
        if len(candidates)!=1:
            raise RuntimeError("ORDER_CONFIRMATION_MISMATCH")
        return candidates[0]

    def confirm_order(self, order, before_send):
        modal = self.confirmation_window(order)
        self.assert_trading_account(order["account"], order.get("account_kind", "simulated"))
        trace = [{"event":"confirmation_matched", "handle":modal.handle,
                  "at":time.time()}]
        before_send()
        # easytrader sends Alt+Y to the foreground dialog, not its button.
        modal.type_keys("%Y", set_foreground=True)
        deadline = time.monotonic() + 6.0
        last = None
        while True:
            response = self.order_response()
            signature = (response.get("status"), tuple(d.get("text", "") for d in response.get("dialogs", [])))
            if signature != last:
                trace.append({"event":"dialog_state", "status":response["status"],
                              "titles":[d.get("text", "").split("\n")[0][:160] for d in response.get("dialogs", [])],
                              "at":time.time()})
                last = signature
            if receipt_contract(response, order["side"]):
                return dict(response, status="submission_accepted", timeline=trace)
            if response["status"] == "verification_required":
                return dict(response, timeline=trace)
            if response.get("dialogs") and not any("您是否确定以上" in d.get("text", "") for d in response["dialogs"]):
                return dict(response, timeline=trace)
            if time.monotonic() >= deadline:
                return dict(response, status="submission_unconfirmed", timeline=trace)
            time.sleep(0.2)

    def resume(self, checkpoint):
        # Resume only the recorded request. Never select the grid or send keys.
        if checkpoint.get("schema_version") != 1:
            raise RuntimeError("INVALID_COPY_CHECKPOINT")
        age = time.time() - checkpoint["requested_at"]
        if not 0 <= age <= 300:
            raise RuntimeError("COPY_CHECKPOINT_EXPIRED")
        if (checkpoint["process_id"] != self.app.process
                or checkpoint["window_handle"] != self.window.handle
                or checkpoint["account"] != self.accounts()["current_account"]):
            raise RuntimeError("COPY_CHECKPOINT_ACCOUNT_MISMATCH")
        return self._collect_copy(checkpoint)

    def _collect_copy(self, checkpoint):
        import win32clipboard
        try:
            for attempt in range(20):
                try:
                    self.check_ready()
                except RuntimeError as exc:
                    if str(exc) != "WINDOW_BUSY" or attempt == 19:
                        raise
                else:
                    if win32clipboard.GetClipboardSequenceNumber() != checkpoint["clipboard_sequence"]:
                        break
                time.sleep(0.1)
            else:
                raise RuntimeError("GRID_COPY_UNAVAILABLE")
        except RuntimeError as exc:
            raise PendingCopy(str(exc), checkpoint) from exc
        result = self.funds()
        if result["current_account"] != checkpoint["account"]:
            raise RuntimeError("COPY_CHECKPOINT_ACCOUNT_MISMATCH")
        sequence = win32clipboard.GetClipboardSequenceNumber()
        import win32process
        owner = win32clipboard.GetClipboardOwner()
        if not owner or win32process.GetWindowThreadProcessId(owner)[1] != self.app.process:
            raise RuntimeError("CLIPBOARD_PROVENANCE_UNVERIFIED")
        win32clipboard.OpenClipboard()
        try:
            content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        if win32clipboard.GetClipboardSequenceNumber() != sequence:
            raise RuntimeError("CLIPBOARD_CHANGED_DURING_READ")
        if "证券代码" not in content or "证券名称" not in content:
            raise RuntimeError("GRID_HEADERS_INVALID")
        rows = parse_grid(content)
        if rows is None:
            raise RuntimeError("GRID_PARSE_FAILED")
        self.check_ready()
        if self.accounts()["current_account"] != result["current_account"]:
            raise RuntimeError("ACCOUNT_CHANGED_DURING_READ")
        market_value = sum((Decimal(str(row["市值"])) for row in rows), Decimal("0"))
        warnings = []
        if market_value != Decimal(result["funds"]["股票市值"]):
            warnings.append("DISPLAYED_STOCK_VALUE_MISMATCH")
        if market_value + Decimal(result["funds"]["资金余额"]) != Decimal(result["funds"]["总资产"]):
            warnings.append("ASSET_RECONCILIATION_MISMATCH")
        return dict(result, clipboard_owner_verified=True, positions=rows, row_count=len(rows),
                    holdings_market_value=str(market_value), warnings=warnings,
                    copy_requested_at=checkpoint["requested_at"])


import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import re
import sqlite3
import uuid


def capture_window_png(handle):
    """Render the window; never send copy, export or keyboard commands."""
    import ctypes
    import struct
    import zlib
    import win32gui
    import win32ui
    if win32gui.IsIconic(handle):
        raise RuntimeError("WINDOW_MINIMIZED")
    left, top, right, bottom = win32gui.GetWindowRect(handle)
    width, height = right-left, bottom-top
    if not (500 <= width <= 8000 and 300 <= height <= 8000):
        raise RuntimeError("WINDOW_NOT_CAPTURE_READY")
    dc_handle = win32gui.GetWindowDC(handle)
    source = win32ui.CreateDCFromHandle(dc_handle)
    target = source.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(source, width, height)
    previous = target.SelectObject(bitmap)
    try:
        from ctypes import wintypes
        print_window = ctypes.windll.user32.PrintWindow
        print_window.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        print_window.restype = wintypes.BOOL
        if not print_window(handle, target.GetSafeHdc(), 2):
            raise RuntimeError("WINDOW_CAPTURE_FAILED")
        raw = bitmap.GetBitmapBits(True)
        if len(raw) != width*height*4:
            raise RuntimeError("CAPTURE_FORMAT_UNSUPPORTED")
        rgb = bytearray(width*height*3)
        rgb[0::3], rgb[1::3], rgb[2::3] = raw[2::4], raw[1::4], raw[0::4]
        rows = b"".join(b"\x00"+rgb[i*width*3:(i+1)*width*3] for i in range(height))
        def chunk(kind, value):
            return struct.pack(">I",len(value))+kind+value+struct.pack(">I",zlib.crc32(kind+value)&0xffffffff)
        return (b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,2,0,0,0))
                +chunk(b"IDAT",zlib.compress(rows))+chunk(b"IEND",b""))
    finally:
        target.SelectObject(previous)
        win32gui.DeleteObject(bitmap.GetHandle())
        target.DeleteDC()
        source.DeleteDC()
        win32gui.ReleaseDC(handle,dc_handle)


def parse_grid(content):
    reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), delimiter="\t")
    headers = reader.fieldnames or []
    if not {"证券代码", "证券名称", "市值"}.issubset(headers) or len(headers) != len(set(headers)):
        raise RuntimeError("GRID_HEADERS_INVALID")
    rows = []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise RuntimeError("GRID_ROW_INVALID")
        if not re.fullmatch(r"[0-9]{6}", row["证券代码"].strip()):
            raise RuntimeError("SECURITY_CODE_INVALID")
        row = {k: v.strip() for k,v in row.items()}
        try:
            value = Decimal(row["市值"].replace(",", ""))
            if not value.is_finite(): raise ValueError()
            row["市值"] = str(value)
        except Exception:
            raise RuntimeError("GRID_AMOUNT_INVALID")
        rows.append(row)
    return rows


def account_id(label):
    return "a_" + hashlib.sha256(label.encode("utf-8")).hexdigest()[:16]


def validate_order(request):
    result = {key:request.get(key) for key in ("side","code","price","quantity","account")}
    if result["side"] not in ("buy","sell"):
        raise RuntimeError("ORDER_SIDE_INVALID")
    if not isinstance(result["account"],str) or not re.fullmatch(r"a_[a-f0-9]{16}",result["account"]):
        raise RuntimeError("ACCOUNT_REQUIRED")
    if not isinstance(result["code"],str) or not re.fullmatch(r"[0-9]{6}",result["code"]):
        raise RuntimeError("SECURITY_CODE_INVALID")
    if not isinstance(result["quantity"],str) or not re.fullmatch(r"[1-9][0-9]{0,8}",result["quantity"]):
        raise RuntimeError("ORDER_QUANTITY_INVALID")
    if (not isinstance(result["price"],str) or not re.fullmatch(r"[0-9]{1,6}(\.[0-9]{1,3})?",result["price"])
            or Decimal(result["price"]) <= 0):
        raise RuntimeError("ORDER_PRICE_INVALID")
    return result


def type_numeric_edit(control, value):
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?",value):
        raise RuntimeError("ORDER_FIELD_VALUE_INVALID")
    control.set_focus()
    # Default select() derives its end from GetWindowText, empty on this client.
    # Explicit EM_SETSEL(0, -1) selects the complete existing value.
    control.select(0, -1)
    control.type_keys(value, set_foreground=False, pause=0.01)


def read_edit(control):
    # EditWrapper.texts() includes EM_GETLINE results; GetWindowText is empty on THS.
    values = [s.strip() for s in control.texts() if s.strip()]
    if len(set(values)) > 1:
        raise RuntimeError("EDIT_READBACK_AMBIGUOUS")
    return values[-1] if values else ""


def validate_confirmation(text, order, account_label):
    import html
    text=html.unescape(re.sub(r"<[^>]*>","",text))
    side="买入" if order["side"]=="buy" else "卖出"
    def one(pattern):
        found=re.findall(pattern,text)
        return found[0].strip() if len(found)==1 else None
    try:
        return ("验证码" not in text and "您是否确定以上"+side+"委托" in text
                and one(r"资金帐号[：:]([^\n]+)")==account_label
                and one(r"证券代码[：:]\s*([0-9]{6})")==order["code"]
                and Decimal(one(side+r"价格[：:]\s*([0-9.]+)"))==Decimal(order["price"])
                and int(one(side+r"数量[：:]\s*([0-9]+)"))==int(order["quantity"]))
    except (TypeError,ValueError,ArithmeticError):
        return False


def validate_market_confirmation(text, order, account_label):
    import html
    text = html.unescape(re.sub(r"<[^>]*>", "", text))
    side = "买入" if order["side"] == "buy" else "卖出"
    def one(pattern):
        found = re.findall(pattern, text)
        return found[0].strip() if len(found) == 1 else None
    try:
        shareholder = one(r"股东帐号[：:]\s*([0-9A-Za-z]+)")
        return ("验证码" not in text and "您是否确定以上市价" + side + "委托" in text
                and bool(shareholder)
                and one(r"证券代码[：:]\s*([0-9]{6})") == order["code"]
                and int(one(side + r"数量[：:]\s*([0-9]+)")) == int(order["quantity"])
                and one(r"委托策略[：:]([^\n]+)") == order["market_strategy"])
    except (TypeError, ValueError, ArithmeticError, KeyError):
        return False


def receipt_contract(response, side):
    dialogs = response.get("dialogs") or []
    if len(dialogs) != 1:
        return None
    action = "买入" if side == "buy" else "卖出"
    matches = re.findall(r"您的"+action+r"委托已成功提交，合同编号：([0-9]+)", dialogs[0].get("text", ""))
    return matches[0] if len(matches) == 1 else None


def validate_batch_orders(orders, account):
    if not isinstance(orders, list) or not 1 <= len(orders) <= 15:
        raise RuntimeError("BATCH_SIZE_INVALID")
    if not isinstance(account, str) or not re.fullmatch(r"a_[a-f0-9]{16}", account):
        raise RuntimeError("ACCOUNT_REQUIRED")
    result = []
    seen = set()
    for row in orders:
        if not isinstance(row, dict) or set(row) != {"side", "code", "price", "quantity"}:
            raise RuntimeError("BATCH_ORDER_SCHEMA_INVALID")
        order = validate_order(dict(row, account=account))
        if order["side"] == "buy" and order["code"] in seen:
            raise RuntimeError("BATCH_DUPLICATE_SECURITY")
        if order["side"] == "buy": seen.add(order["code"])
        result.append(order)
    return result


def validate_default_batch_orders(orders, account):
    if not isinstance(orders, list) or not 1 <= len(orders) <= 15:
        raise RuntimeError("BATCH_SIZE_INVALID")
    if not isinstance(account, str) or not re.fullmatch(r"a_[a-f0-9]{16}", account):
        raise RuntimeError("ACCOUNT_REQUIRED")
    result, seen = [], set()
    for row in orders:
        if not isinstance(row, dict) or set(row) != {"side","code","quantity"}:
            raise RuntimeError("BATCH_ORDER_SCHEMA_INVALID")
        if row["side"] not in ("buy","sell") or not isinstance(row["code"],str) or not re.fullmatch(r"[0-9]{6}",row["code"]):
            raise RuntimeError("BATCH_ORDER_INVALID")
        if not isinstance(row["quantity"],str) or not re.fullmatch(r"[1-9][0-9]{0,8}",row["quantity"]):
            raise RuntimeError("BATCH_ORDER_INVALID")
        if row["side"] == "buy" and row["code"] in seen:
            raise RuntimeError("BATCH_DUPLICATE_SECURITY")
        if row["side"] == "buy": seen.add(row["code"])
        result.append(dict(row,account=account))
    return result


def batch_digest(account, orders):
    return hashlib.sha256(json.dumps({"account":account,"orders":orders},
                       ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def order_fields_match(actual, order):
    try:
        return (actual.get("unit") == "shares" and actual["side"] == order["side"] and actual["code"] == order["code"]
                and Decimal(actual["price"]) == Decimal(order["price"])
                and int(actual["quantity"]) == int(order["quantity"]))
    except (ValueError, KeyError, ArithmeticError):
        return False


def market_fields_match(actual, order):
    try:
        return (actual.get("unit") == "shares" and actual["side"] == order["side"]
                and actual["code"] == order["code"]
                and int(actual["quantity"]) == int(order["quantity"])
                and actual["market_strategy"] == order["market_strategy"]
                and actual["market_strategy_index"] == order["market_strategy_index"]
                and "不支持市价委托" not in actual["market_strategy"]
                and re.fullmatch(r"[0-9]{1,6}(?:\.[0-9]{1,3})?", actual["reference_price"])
                and Decimal(actual["reference_price"]) > 0)
    except (ValueError, KeyError, TypeError):
        return False


def public_accounts(data):
    result = dict(data)
    result["accounts"] = [dict(a, id=account_id(a["label"])) for a in data["accounts"]]
    result["account_id"] = account_id(data["current_account"])
    return result


def resolve_account(client, identity):
    data = client.accounts()
    if not identity: return data["current_account"]
    found = [a["label"] for a in data["accounts"] if account_id(a["label"]) == identity]
    if len(found) != 1: raise RuntimeError("ACCOUNT_NOT_FOUND_OR_AMBIGUOUS")
    return found[0]


class Store:
    def __init__(self, filename):
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        if filename.is_symlink(): raise RuntimeError("STATE_PATH_UNSAFE")
        if filename.exists() and not filename.is_file(): raise RuntimeError("STATE_PATH_UNSAFE")
        self.db = sqlite3.connect(filename)
        self.db.execute("CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        self.db.commit()

    def save(self, op):
        op["updated_at"] = time.time()
        self.db.execute("INSERT INTO operations VALUES (?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data", (op["id"], json.dumps(op)))
        self.db.commit()

    def get(self, identity):
        row = self.db.execute("SELECT data FROM operations WHERE id=?", (identity,)).fetchone()
        if not row: raise RuntimeError("OPERATION_NOT_FOUND")
        return json.loads(row[0])

    def find_batch_digest(self, digest):
        for row in self.db.execute("SELECT data FROM operations"):
            item = json.loads(row[0])
            # A failed run with every row still queued never reached submit.
            # Its form may need manual cleanup, but it cannot duplicate an order.
            if (item.get("kind") == "batch" and item.get("status") == "needs_attention"
                    and all(entry.get("status") == "queued" for entry in item.get("orders", []))):
                continue
            if (item.get("kind") == "batch" and item.get("digest") == digest
                    and (item.get("status") in ("running", "needs_attention")
                         or time.time()-item.get("requested_at",0)<300)):
                return item
        return None

    def pending(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM operations")
                if json.loads(row[0])["status"] in ("running", "waiting")
                or (json.loads(row[0])["status"] == "failed" and json.loads(row[0]).get("checkpoint"))]


def batch_result(batch):
    return {"ok":batch["status"] in ("prepared", "completed"),
            "batch_id":batch["id"], "digest":batch["digest"],
            "account":batch["account"], "account_kind":batch.get("account_kind","simulated"),
            "mode":batch.get("mode","limit"), "status":batch["status"],
            "error":batch.get("error"), "orders":batch["orders"],
            "estimated_buy_total":batch["estimated_buy_total"],
            "available_before":batch["available_before"],
            "started_at":batch.get("started_at"), "updated_at":batch["updated_at"]}


def acknowledge_batch_receipt(client, order, response):
    contract = receipt_contract(response, order["side"])
    if not contract:
        raise RuntimeError("ORDER_RECEIPT_REQUIRED")
    current = client.order_response()
    if current.get("dialogs") != response.get("dialogs"):
        raise RuntimeError("ORDER_RECEIPT_CHANGED")
    matches=[]
    for window in client.app.windows(visible_only=True):
        if window.handle == client.window.handle:
            continue
        text="\n".join(c.window_text() for c in window.descendants() if c.class_name()=="Static")
        if not re.search(r"合同编号："+re.escape(contract)+r"(?![0-9])",text):
            continue
        matches.extend(c for c in window.descendants() if c.class_name()=="Button"
                       and c.control_id()==2 and c.is_visible() and c.window_text()=="确定")
    if len(matches)!=1:
        raise RuntimeError("ORDER_RECEIPT_MISMATCH")
    client.assert_trading_account(order["account"], order.get("account_kind", "simulated"))
    matches[0].click()


def clear_batch_form(client, order):
    client.assert_trading_account(order["account"], order.get("account_kind", "simulated"))
    if order.get("mode") == "market":
        fields = client.market_order_fields(order["side"])
        if not fields["code"] and not fields["quantity"]:
            return
        if not market_fields_match(fields, order):
            raise RuntimeError("ORDER_READBACK_MISMATCH")
        client.reset_market_form(order["side"])
        return
    fields=client.order_fields(order["side"])
    if not any(fields[key] for key in ("code","price","quantity")):
        return
    if not order_fields_match(fields, order):
        raise RuntimeError("ORDER_READBACK_MISMATCH")
    for cid in (1034,1033,1032):
        client.control("Edit",cid).type_keys("^a{BACKSPACE}",set_foreground=True)
    fields=client.order_fields(order["side"])
    if fields["code"] or fields["quantity"]:
        raise RuntimeError("ORDER_CLEAR_FAILED")


def execute_batch(client, store, batch):
    batch["status"]="running"
    batch["started_at"]=time.time()
    store.save(batch)
    for entry in batch["orders"]:
        order=entry["order"]
        try:
            client.assert_trading_account(batch["account"], batch.get("account_kind", "simulated"))
            if entry["status"] != "queued":
                raise RuntimeError("BATCH_ORDER_ALREADY_ATTEMPTED")
            if batch.get("mode") == "market":
                prepared = client.market_order(order)
                order.update(mode="market", market_strategy=prepared["market_strategy"],
                             market_strategy_index=prepared["market_strategy_index"])
            elif batch.get("mode") == "default_price":
                prepared=client.default_price_order(order)
                order["price"]=prepared["price"]
            else:
                prepared=client.prepare_order(order)
            entry["status"]="prepared"
            preview_keys = (("side", "unit", "code", "quantity", "market_strategy",
                             "reference_price", "captured_at") if batch.get("mode") == "market"
                            else ("side", "unit", "code", "price", "quantity", "captured_at"))
            entry["preview"] = {k: prepared[k] for k in preview_keys}
            store.save(batch)
            fields_match = (market_fields_match(client.market_order_fields(order["side"]), order)
                            if batch.get("mode") == "market" else
                            order_fields_match(client.order_fields(order["side"]), order))
            if not fields_match:
                raise RuntimeError("ORDER_READBACK_MISMATCH")
            client.assert_trading_account(batch["account"], batch.get("account_kind", "simulated"))
            entry["status"]="submit_attempted"
            store.save(batch)
            client.control("Button",1006).click()
            deadline=time.monotonic()+5
            while True:
                response=client.order_response()
                if response.get("dialogs") or response["status"] == "verification_required" or time.monotonic() >= deadline:
                    break
                time.sleep(0.2)
            entry["submission_response"]=response
            store.save(batch)
            if response["status"] != "dialog_review_required":
                raise RuntimeError("ORDER_CONFIRMATION_NOT_FOUND")
            # Validate the precise dialog before recording a confirmation attempt.
            client.confirmation_window(order)
            def persist_attempt():
                entry["status"]="confirm_attempted"
                store.save(batch)
            response=client.confirm_order(order,persist_attempt)
            entry["confirmation_response"]=response
            store.save(batch)
            contract=receipt_contract(response,order["side"])
            if not contract:
                raise RuntimeError("ORDER_RECEIPT_UNCONFIRMED")
            entry["contract_no"]=contract
            entry["status"]="accepted"
            store.save(batch)
            acknowledge_batch_receipt(client,order,response)
            clear_batch_form(client,order)
            entry["form_cleared"]=True
            store.save(batch)
        except Exception as exc:
            previous=entry["status"]
            entry["status"]="unknown" if previous in ("submit_attempted","confirm_attempted") else previous
            entry["error"]=safe_error(exc)
            batch["status"]="needs_attention"
            batch["error"]=safe_error(exc)
            store.save(batch)
            return batch_result(batch)
    batch["status"]="completed"
    store.save(batch)
    return batch_result(batch)


def safe_error(exc):
    value = str(exc)
    return value if isinstance(exc, RuntimeError) and re.fullmatch(r"[A-Z][A-Z0-9_]+",value) else type(exc).__name__


def result_for(op):
    return {"ok": op["status"] == "completed", "operation_id":op["id"],
            "status":op["status"], "error":op.get("error"),
            "results":op["results"], "restoration":op.get("restoration"),
            "requested_at":op["requested_at"], "updated_at":op["updated_at"]}


def execute_operation(client, store, op, resume=False):
    def persist(checkpoint):
        op["checkpoint"] = checkpoint
        store.save(op)
    try:
        if resume:
            if not op.get("checkpoint"): raise RuntimeError("OPERATION_NOT_RESUMABLE")
            data = client.resume(op["checkpoint"])
            op["results"].append(public_accounts(data))
            op["index"] += 1
            op.pop("checkpoint",None)
            op["status"] = "running"
            store.save(op)
        while op["index"] < len(op["targets"]):
            client.switch(op["targets"][op["index"]])
            data = client.capture_positions() if op["kind"] == "positions" else client.funds()
            op["results"].append(public_accounts(data))
            op["index"] += 1
            op.pop("checkpoint",None)
            store.save(op)
        op["status"] = "completed"
        op.pop("error",None)
    except PendingCopy as exc:
        op.update(status="waiting",error=str(exc),checkpoint=exc.checkpoint)
        store.save(op)
        return result_for(op)
    except Exception as exc:
        if op.get("checkpoint"):
            op.update(status="waiting",error=safe_error(exc))
            store.save(op)
            return result_for(op)
        op.update(status="failed",error=safe_error(exc))
    if op.get("error") in ("COPY_CHECKPOINT_ACCOUNT_MISMATCH", "ACCOUNT_CHANGED_DURING_READ"):
        op["restoration"] = "manual_review_required"
        store.save(op)
        return result_for(op)
    try:
        client.switch(op["original"])
        op["restoration"] = "restored"
    except Exception as exc:
        op["restoration"] = safe_error(exc)
        if op["status"] == "completed": op.update(status="failed",error="RESTORE_FAILED")
    store.save(op)
    return result_for(op)


def dispatch(request, store, factory=ReadOnlyTHS):
    action = request["action"]
    if action == "batches.status":
        batch=store.get(request.get("batch", ""))
        if batch.get("kind")!="batch" or batch["exe"]!=request["exe"]:
            raise RuntimeError("BATCH_INVALID")
        if batch["status"] == "running":
            # The desktop mutex is held throughout an active run; reaching this
            # branch means its process has exited without a terminal checkpoint.
            batch.update(status="needs_attention",error="BATCH_INTERRUPTED")
            store.save(batch)
        return batch_result(batch)
    if action.startswith("operations."):
        op = store.get(request.get("id", ""))
        if op["exe"] != request["exe"]: raise RuntimeError("OPERATION_CONNECTION_MISMATCH")
        if action == "operations.status": return result_for(op)
        if action == "operations.abandon":
            if not request.get("yes"): raise RuntimeError("CONFIRMATION_REQUIRED")
            if op["status"] not in ("waiting", "running") and not (op["status"] == "failed" and op.get("checkpoint")): raise RuntimeError("OPERATION_TERMINAL")
            op.update(status="abandoned",error="USER_ABANDONED",restoration="manual_review_required")
            store.save(op)
            return {"ok":True,"operation_id":op["id"],"status":"abandoned"}
        if action != "operations.resume": raise RuntimeError("COMMAND_UNSUPPORTED")
        if op["status"] == "completed": return result_for(op)
        if op["status"] not in ("waiting", "running") and not (op["status"] == "failed" and op.get("checkpoint")): raise RuntimeError("OPERATION_TERMINAL")
        try: client = factory(request["exe"])
        except Exception as exc:
            return {**result_for(op),"ok":False,"error":safe_error(exc)}
        return execute_operation(client,store,op,True)
    if action in ("batches.prepare-default", "batches.prepare-real-default",
                  "batches.prepare-market", "batches.prepare-real-market"):
        pending=store.pending()
        if pending:
            return {"ok":False,"error":"OPERATION_PENDING","operation_id":pending[0]["id"]}
        account=request.get("account")
        orders=validate_default_batch_orders(request.get("orders"),account)
        kind="real" if action in ("batches.prepare-real-default", "batches.prepare-real-market") else "simulated"
        mode = "market" if action.endswith("market") else "default_price"
        if kind == "real":
            client=factory(request["exe"])
            client.assert_trading_account(account,kind)
        orders=[dict(order,account_kind=kind) for order in orders]
        digest=batch_digest(account,[{"mode":mode,"account_kind":kind},*orders])
        if store.find_batch_digest(digest):
            raise RuntimeError("BATCH_DUPLICATE_PLAN")
        batch={"id":str(uuid.uuid4()),"kind":"batch","exe":request["exe"],
               "account":account,"mode":mode,"account_kind":kind,"digest":digest,
               "status":"prepared","requested_at":time.time(),
               "estimated_buy_total":None,"available_before":None,
               "orders":[{"index":i,"order":o,"status":"queued"} for i,o in enumerate(orders)]}
        store.save(batch)
        return batch_result(batch)
    if action not in ("accounts", "accounts.select", "orders.open", "orders.inspect", "orders.ledger", "orders.clear", "orders.quantity-mode", "orders.prepare", "orders.submit-simulated", "orders.confirm-simulated", "orders.acknowledge", "orders.result", "batches.prepare", "batches.run-simulated", "batches.run-real", "funds", "positions", "snapshot", "doctor"):
        raise RuntimeError("COMMAND_UNSUPPORTED")
    pending=store.pending()
    if pending:
        return {"ok":False,"error":"OPERATION_PENDING","operation_id":pending[0]["id"]}
    if action in ("orders.acknowledge", "orders.result","orders.confirm-simulated"):
        client = factory(request["exe"], allow_dialogs=True)
    else:
        client = factory(request["exe"])
    if action == "doctor":
        return {"ok":True,"attached":True,"account_count":len(client.accounts()["accounts"]),
                "interactive_session":os.environ.get("SESSIONNAME","unknown"),
                "simulated_orders_only":False,"real_default_price_batches":True}
    if action == "accounts": return {"ok":True,**public_accounts(client.accounts())}
    if action == "batches.prepare":
        account=request.get("account")
        orders=validate_batch_orders(request.get("orders"),account)
        if account_id(client.accounts()["current_account"])!=account:
            raise RuntimeError("ORDER_ACCOUNT_MISMATCH")
        client.assert_simulated(account)
        client.open_page("holdings")
        funds=client.funds()["funds"]
        total=sum((Decimal(o["price"])*int(o["quantity"])
                  for o in orders if o["side"]=="buy"),Decimal("0"))
        reserve=Decimal(5)*sum(o["side"]=="buy" for o in orders)
        if total+reserve>Decimal(funds["可用金额"]):
            raise RuntimeError("BATCH_FUNDS_INSUFFICIENT")
        digest=batch_digest(account,[{"mode":"limit"},*orders])
        if store.find_batch_digest(digest):
            raise RuntimeError("BATCH_DUPLICATE_PLAN")
        batch={"id":str(uuid.uuid4()),"kind":"batch","exe":request["exe"],"account":account,
               "mode":"limit",
               "digest":digest,"status":"prepared","requested_at":time.time(),
               "estimated_buy_total":str(total),
               "available_before":funds["可用金额"],
               "orders":[{"index":i,"order":o,"status":"queued"} for i,o in enumerate(orders)]}
        store.save(batch)
        return batch_result(batch)
    if action in ("batches.run-simulated", "batches.run-real"):
        if request.get("confirmed") is not True:
            raise RuntimeError("CONFIRMATION_REQUIRED")
        batch=store.get(request.get("batch", ""))
        if batch.get("kind")!="batch" or batch["exe"]!=request["exe"]:
            raise RuntimeError("BATCH_INVALID")
        if batch["status"]!="prepared":
            raise RuntimeError("BATCH_ALREADY_ATTEMPTED")
        if (request.get("account")!=batch["account"] or request.get("digest")!=batch["digest"]
                or not 0<=time.time()-batch["requested_at"]<=300):
            raise RuntimeError("BATCH_EXPIRED_OR_MISMATCH")
        kind="real" if action == "batches.run-real" else "simulated"
        if batch.get("account_kind","simulated") != kind:
            raise RuntimeError("BATCH_ACCOUNT_KIND_MISMATCH")
        client.assert_trading_account(batch["account"],kind)
        return execute_batch(client,store,batch)
    if action.startswith("orders."):
        if action in ("orders.submit-simulated", "orders.confirm-simulated", "orders.result", "orders.acknowledge"):
            draft = store.get(request.get("draft", ""))
            if draft.get("kind") != "order" or draft["exe"] != request["exe"]:
                raise RuntimeError("ORDER_DRAFT_INVALID")
            client.assert_simulated(draft["order"]["account"])
            if action == "orders.acknowledge":
                if request.get("account") != draft["order"]["account"]:
                    raise RuntimeError("ORDER_ACCOUNT_MISMATCH")
                saved = draft.get("response", {})
                current = client.order_response()
                if draft["status"] != "confirmation_attempted" or current.get("dialogs") != saved.get("dialogs"):
                    raise RuntimeError("ORDER_RECEIPT_MISMATCH")
                side = "买入" if draft["order"]["side"] == "buy" else "卖出"
                receipts = [d for d in current.get("dialogs", []) if re.search(
                    "您的"+side+r"委托已成功提交，合同编号：[0-9]+",d["text"])]
                if len(receipts) != 1 or len(current["dialogs"]) != 1:
                    raise RuntimeError("ORDER_RECEIPT_REQUIRED")
                matches=[]
                for window in client.app.windows(visible_only=True):
                    if window.handle == client.window.handle: continue
                    text="\n".join(c.window_text() for c in window.descendants() if c.class_name()=="Static")
                    if not re.search("您的"+side+r"委托已成功提交，合同编号：[0-9]+",text): continue
                    matches.extend(c for c in window.descendants() if c.class_name()=="Button" and c.control_id()==2 and c.is_visible() and c.window_text()=="确定")
                if len(matches)!=1: raise RuntimeError("ORDER_RECEIPT_MISMATCH")
                client.assert_simulated(draft["order"]["account"])
                draft["status"]="receipt_acknowledgment_attempted"
                store.save(draft)
                matches[0].click()
                draft["accepted_receipt"]={"status":"submission_accepted","filled":None,
                    "contract_no":re.search(r"合同编号：([0-9]+)",receipts[0]["text"]).group(1),"receipt":receipts[0]}
                store.save(draft)
                return {"ok":True,"draft_id":draft["id"],**draft["accepted_receipt"]}
            if action == "orders.result":
                response=client.order_response()
                if response.get("dialogs"):
                    draft["response"]=response
                    store.save(draft)
                return {"ok":True,"draft_id":draft["id"],"attempt_status":draft["status"],
                        "accepted_receipt":draft.get("accepted_receipt"),**response}
            if action == "orders.confirm-simulated":
                if draft["status"] != "submission_attempted":
                    raise RuntimeError("ORDER_ALREADY_ATTEMPTED")
                if request.get("account") != draft["order"]["account"] or not 0 <= time.time()-draft["requested_at"] <= 300:
                    raise RuntimeError("ORDER_CONFIRMATION_EXPIRED_OR_MISMATCH")
                def persist_attempt():
                    draft["status"]="confirmation_attempted"
                    store.save(draft)
                response=client.confirm_order(draft["order"],persist_attempt)
                draft["response"]=response
                store.save(draft)
                return {"ok":True,"draft_id":draft["id"],"simulation_only":True,"confirmation_attempted":True,**response}
            if draft["status"] != "prepared":
                raise RuntimeError("ORDER_ALREADY_ATTEMPTED")
            if not 0 <= time.time()-draft["requested_at"] <= 300:
                raise RuntimeError("ORDER_DRAFT_EXPIRED")
            if request.get("account") != draft["order"]["account"]:
                raise RuntimeError("ORDER_ACCOUNT_MISMATCH")
            client.check_ready()
            if not order_fields_match(client.order_fields(draft["order"]["side"]),draft["order"]):
                raise RuntimeError("ORDER_READBACK_MISMATCH")
            client.assert_simulated(draft["order"]["account"])
            draft["status"] = "submission_attempted"
            store.save(draft)
            # At-most-once click. No automatic confirmation or retry after uncertainty.
            client.control("Button",1006).click()
            time.sleep(0.6)
            response = client.order_response()
            draft["response"] = response
            store.save(draft)
            return {"ok":True,"draft_id":draft["id"],"simulation_only":True,"submission_attempted":True,**response}
        if request.get("account") != account_id(client.accounts()["current_account"]):
            raise RuntimeError("ORDER_ACCOUNT_MISMATCH")
        if action == "orders.ledger":
            client.check_ready()
            tree = client.control("SysTreeView32",129)
            node = tree.get_item(["查询[F4]", "当日委托"])
            node.select()
            client.window.type_keys("{F5}", set_foreground=True)
            time.sleep(1.0)
            client.check_ready()
            if not tree.is_selected(["查询[F4]", "当日委托"]):
                raise RuntimeError("ORDER_LEDGER_PAGE_MISMATCH")
            if request["account"] != account_id(client.accounts()["current_account"]):
                raise RuntimeError("ORDER_ACCOUNT_MISMATCH")
            return {"ok":True,"submitted":False,"results":[{"account_id":request["account"],"captured_at":time.time(),
                    "source":"order_ledger_window","review_required":True,
                    "image_base64":base64.b64encode(capture_window_png(client.window.handle)).decode("ascii")}]}
        if action == "orders.clear":
            if not request.get("yes"):
                raise RuntimeError("CONFIRMATION_REQUIRED")
            if client.market_page_active(request.get("side")):
                return {"ok":True,"submitted":False,
                        "fields":client.reset_market_form(request["side"])}
            client.order_fields(request.get("side"))
            for cid in (1034,1033,1032):
                if request["account"] != account_id(client.accounts()["current_account"]):
                    raise RuntimeError("ORDER_ACCOUNT_MISMATCH")
                client.control("Edit",cid).type_keys("^a{BACKSPACE}",set_foreground=True)
            return {"ok":True,"submitted":False,"fields":client.order_fields(request["side"])}
        if action == "orders.quantity-mode":
            fields = client.order_fields(request.get("side"))
            if any(fields[key] for key in ("code","quantity")):
                raise RuntimeError("FORM_DRAFT_PRESENT")
            if fields["unit"] == "amount":
                client.control("Static",1399).click_input()
                time.sleep(0.3)
            fields = client.order_fields(request["side"])
            return {"ok":fields["unit"]=="shares","submitted":False,"fields":fields}
        if action == "orders.inspect":
            fields = (client.market_order_fields(request.get("side"))
                      if client.market_page_active(request.get("side"))
                      else client.order_fields(request.get("side")))
            return {"ok":True,"submitted":False,"fields":fields,
                    "results":[{"account_id":request["account"],"captured_at":time.time(),
                    "image_base64":base64.b64encode(capture_window_png(client.window.handle)).decode("ascii")}]}
        if action == "orders.open":
            if request.get("side") not in ("buy","sell"):
                raise RuntimeError("ORDER_SIDE_INVALID")
            client.open_page(request["side"])
            return {"ok":True,"submitted":False,"fields":client.order_fields(request["side"])}
        result = client.prepare_order(request)
        draft={"id":str(uuid.uuid4()),"kind":"order","exe":request["exe"],"order":validate_order(request),
               "status":"prepared","requested_at":time.time(),"results":[]}
        store.save(draft)
        return {"ok":True,"draft_id":draft["id"],"submitted":False,"results":[result],"status":"prepared_for_manual_submission"}
    if action == "accounts.select":
        if not request.get("account"):
            raise RuntimeError("ACCOUNT_REQUIRED")
        target = resolve_account(client, request["account"])
        original = account_id(client.accounts()["current_account"])
        client.open_page("holdings")
        result = client.switch(target)
        return {"ok":True,"previous_account_id":original,"selection_retained":True,
                **public_accounts(result)}
    identities=request.get("accounts") if action=="snapshot" else [request.get("account")]
    if not isinstance(identities,list) or not identities or len(identities)!=len(set(identities)):
        raise RuntimeError("ACCOUNTS_REQUIRED_OR_DUPLICATED")
    original=client.accounts()["current_account"]
    targets=[resolve_account(client,i) for i in identities]
    op={"id":str(uuid.uuid4()),"exe":request["exe"],"kind":"funds" if action=="funds" else "positions",
        "status":"running","original":original,"targets":targets,"index":0,"results":[],"requested_at":time.time()}
    store.save(op)
    return execute_operation(client,store,op)


def main():
    if sys.platform != "win32": return {"ok":False,"error":"WINDOWS_REQUIRED"}
    import win32event, win32api
    mutex=win32event.CreateMutex(None,False,"Local\\tradecli_readonly_v1")
    acquired=win32event.WaitForSingleObject(mutex,0) in (0,0x80)
    if not acquired:
        win32api.CloseHandle(mutex)
        return {"ok":False,"error":"SESSION_BUSY"}
    try:
        request=decode_request(sys.argv[1:])
        if request.get("protocol")!=1: raise RuntimeError("PROTOCOL_UNSUPPORTED")
        store=Store(Path(os.environ["LOCALAPPDATA"])/"tradecli"/"operations.sqlite3")
        try: return dispatch(request,store)
        finally: store.db.close()
    except Exception as exc:
        return {"ok":False,"error":safe_error(exc)}
    finally:
        win32event.ReleaseMutex(mutex)
        win32api.CloseHandle(mutex)


def decode_request(args):
    if len(args)==3 and args[0]=="--request-file":
        content=Path(args[1]).read_bytes()
        if hashlib.sha256(content).hexdigest()!=args[2]:
            raise RuntimeError("REQUEST_HASH_MISMATCH")
        return json.loads(content.decode("utf-8"))
    if len(args)==1:
        return json.loads(base64.b64decode(args[0]).decode("utf-8"))
    raise RuntimeError("REQUEST_ARGUMENTS_INVALID")


if __name__ == "__main__":
    print(json.dumps({"protocol":1,**main()},ensure_ascii=True))
