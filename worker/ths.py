"""Query the current logged-in THS account without invoking trade methods."""
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
    def __init__(self, exe_path):
        import pywinauto
        self.app = pywinauto.Application(backend="win32").connect(path=exe_path, timeout=5)
        candidates = [w for w in self.app.windows(visible_only=True)
                      if any(c.class_name() == "ComboBox" and c.control_id() == 2322
                             for c in w.descendants())]
        if len(candidates) != 1:
            raise RuntimeError("ACCOUNT_WINDOW_AMBIGUOUS")
        self.window = candidates[0]
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

    def positions(self, persist=lambda checkpoint: None):
        import win32clipboard
        result = self.funds()
        grid = self.control("CVirtualGridCtrl", 1047)
        checkpoint = {"schema_version": 1, "requested_at": time.time(),
                      "process_id": self.app.process, "window_handle": self.window.handle,
                      "account": result["current_account"],
                      "clipboard_sequence": win32clipboard.GetClipboardSequenceNumber()}
        persist(checkpoint)
        # A copy request only; never invoke upstream's automatic CAPTCHA handling.
        grid.type_keys("^a^c", set_foreground=True, pause=0.2)
        return self._collect_copy(checkpoint)

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
        import win32gui, win32process
        owner = win32gui.GetClipboardOwner()
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

    def pending(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT data FROM operations")
                if json.loads(row[0])["status"] in ("running", "waiting")]


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
            data = client.positions(persist) if op["kind"] == "positions" else client.funds()
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
    if action.startswith("operations."):
        op = store.get(request.get("id", ""))
        if op["exe"] != request["exe"]: raise RuntimeError("OPERATION_CONNECTION_MISMATCH")
        if action == "operations.status": return result_for(op)
        if action == "operations.abandon":
            if not request.get("yes"): raise RuntimeError("CONFIRMATION_REQUIRED")
            if op["status"] not in ("waiting", "running"): raise RuntimeError("OPERATION_TERMINAL")
            op.update(status="abandoned",error="USER_ABANDONED",restoration="manual_review_required")
            store.save(op)
            return {"ok":True,"operation_id":op["id"],"status":"abandoned"}
        if action != "operations.resume": raise RuntimeError("COMMAND_UNSUPPORTED")
        if op["status"] == "completed": return result_for(op)
        if op["status"] not in ("waiting", "running"): raise RuntimeError("OPERATION_TERMINAL")
        try: client = factory(request["exe"])
        except Exception as exc:
            return {**result_for(op),"ok":False,"error":safe_error(exc)}
        return execute_operation(client,store,op,True)
    if action not in ("accounts", "funds", "positions", "snapshot", "doctor"):
        raise RuntimeError("COMMAND_UNSUPPORTED")
    pending=store.pending()
    if pending:
        return {"ok":False,"error":"OPERATION_PENDING","operation_id":pending[0]["id"]}
    client = factory(request["exe"])
    if action == "doctor":
        return {"ok":True,"attached":True,"account_count":len(client.accounts()["accounts"]),"interactive_session":os.environ.get("SESSIONNAME","unknown"),"read_only":True}
    if action == "accounts": return {"ok":True,**public_accounts(client.accounts())}
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
        request=json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
        if request.get("protocol")!=1: raise RuntimeError("PROTOCOL_UNSUPPORTED")
        store=Store(Path(os.environ["LOCALAPPDATA"])/"tradecli"/"operations.sqlite3")
        try: return dispatch(request,store)
        finally: store.db.close()
    except Exception as exc:
        return {"ok":False,"error":safe_error(exc)}
    finally:
        win32event.ReleaseMutex(mutex)
        win32api.CloseHandle(mutex)


if __name__ == "__main__":
    print(json.dumps({"protocol":1,**main()},ensure_ascii=True))
