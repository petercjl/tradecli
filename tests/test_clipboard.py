import sys, unittest, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from ths import ReadOnlyTHS

class Clipboard(unittest.TestCase):
    def test_collects_verified_clipboard_without_gui_owner_api(self):
        client=ReadOnlyTHS.__new__(ReadOnlyTHS)
        client.app=SimpleNamespace(process=42)
        client.check_ready=lambda:None
        client.funds=lambda:{'current_account':'A','funds':{'股票市值':'10','资金余额':'5','总资产':'15'}}
        client.accounts=lambda:{'current_account':'A'}
        clipboard=SimpleNamespace(GetClipboardSequenceNumber=lambda:2,GetClipboardOwner=lambda:123,
            OpenClipboard=lambda:None,CloseClipboard=lambda:None,CF_UNICODETEXT=13,
            GetClipboardData=lambda fmt:'证券代码\t证券名称\t市值\n000001\t示例\t10\n')
        process=SimpleNamespace(GetWindowThreadProcessId=lambda hwnd:(1,42))
        with patch.dict(sys.modules,{'win32clipboard':clipboard,'win32process':process}):
            result=client._collect_copy({'clipboard_sequence':1,'account':'A','requested_at':time.time()})
            self.assertEqual(result['row_count'],1)
            self.assertEqual(result['warnings'],[])
            process.GetWindowThreadProcessId=lambda hwnd:(1,99)
            with self.assertRaisesRegex(RuntimeError,'PROVENANCE_UNVERIFIED'):client._collect_copy({'clipboard_sequence':1,'account':'A'})
