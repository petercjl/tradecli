import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from ths import ReadOnlyTHS,account_id


class QuoteClient:
    market_quotes=ReadOnlyTHS.market_quotes

    def __init__(self, unsupported=False):
        self.label='模拟炒股-TEST'
        self.code=''
        self.unsupported=unsupported
        self.page='holdings'
        self.submits=0

    def accounts(self):return {'current_account':self.label}
    def open_market_page(self,side):
        assert side=='buy'
        self.page='market'
    def market_order_fields(self,side):
        assert side=='buy'
        return {'code':self.code,'quantity':'',
                'market_strategy':'不支持市价委托' if self.unsupported else '对手方最优价格',
                'reference_price':'0' if self.unsupported else '5.00'}
    def control(self,kind,identity):
        assert (kind,identity)==('Edit',1032)
        return self
    def reset_market_form(self,side):
        self.code=''
        return self.market_order_fields(side)
    def open_page(self,page):self.page=page


class SyncQuotes(unittest.TestCase):
    def test_quote_probe_reads_each_code_and_restores_holdings(self):
        client=QuoteClient()
        with patch('ths.type_numeric_edit',lambda _,code:setattr(client,'code',code)),patch('ths.time.sleep'):
            result=client.market_quotes(account_id(client.label),['002591','002188'])
        self.assertEqual([x['code'] for x in result['items']],['002591','002188'])
        self.assertEqual(result['source'],'ths_market_reference_fields')
        self.assertEqual(client.page,'holdings')
        self.assertEqual(client.code,'')
        self.assertEqual(client.submits,0)

    def test_unsupported_quote_clears_task_code(self):
        client=QuoteClient(unsupported=True)
        with patch('ths.type_numeric_edit',lambda _,code:setattr(client,'code',code)),patch('ths.time.sleep'):
            with self.assertRaisesRegex(RuntimeError,'MARKET_QUOTE_UNAVAILABLE'):
                client.market_quotes(account_id(client.label),['002591'])
        self.assertEqual(client.page,'holdings')
        self.assertEqual(client.code,'')

    def test_invalid_or_wrong_account_never_opens_form(self):
        client=QuoteClient()
        for account,codes in [('a_wrong',['002591']),(account_id(client.label),['bad'])]:
            with self.assertRaises(RuntimeError):client.market_quotes(account,codes)
            self.assertEqual(client.page,'holdings')


if __name__=='__main__':unittest.main()
