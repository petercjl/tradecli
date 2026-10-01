import sys, unittest, tempfile, time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from ths import Store, dispatch, account_id, ReadOnlyTHS, receipt_contract


class BatchClient:
    assert_simulated=ReadOnlyTHS.assert_simulated
    def __init__(self):
        self.label='模拟炒股-TEST'
        self.clicks=0
        self.confirmations=0
        self.fail_at=None
        self.auto_clear=False
        self.fields=None
        self.response={'status':'submission_unconfirmed','dialogs':[]}
        self.window=SimpleNamespace(handle=1)
        self.app=SimpleNamespace(windows=lambda visible_only: [self.window,self.receipt_window])
        button=SimpleNamespace(class_name=lambda:'Button',control_id=lambda:2,is_visible=lambda:True,
                               window_text=lambda:'确定',click=self.dismiss)
        label=SimpleNamespace(class_name=lambda:'Static',window_text=lambda:self.receipt_text)
        self.receipt_window=SimpleNamespace(handle=2,descendants=lambda:[label,button])
    def accounts(self):return {'current_account':self.label}
    def open_page(self,page):self.page=page
    def funds(self):return {'funds':{'可用金额':'100000.00'}}
    def prepare_order(self,order):
        self.fields={**order,'unit':'shares'}
        return {**self.fields,'captured_at':time.time()}
    def order_fields(self,side):
        return self.fields or {'side':side,'unit':'shares','code':'','price':'','quantity':''}
    def control(self,kind,identity):
        if (kind,identity)==('Button',1006):return SimpleNamespace(click=self.click)
        if kind=='Edit' and identity in (1032,1033,1034):
            key={1032:'code',1033:'price',1034:'quantity'}[identity]
            return SimpleNamespace(type_keys=lambda *a,**kw:self.fields.__setitem__(key,''))
        raise AssertionError((kind,identity))
    def click(self):
        self.clicks+=1
        self.response={'status':'dialog_review_required','dialogs':[{'text':'confirm'}]}
    def order_response(self):return self.response
    def confirmation_window(self,order):return object()
    def confirm_order(self,order,before_send):
        before_send()
        self.confirmations+=1
        if self.fail_at==self.confirmations:
            self.response={'status':'submission_unconfirmed','dialogs':[],'timeline':[{'event':'timeout'}]}
            return self.response
        self.receipt_text=f'您的买入委托已成功提交，合同编号：{1000+self.confirmations}'
        self.response={'status':'submission_accepted','dialogs':[{'text':self.receipt_text}]}
        return self.response
    def dismiss(self):
        self.response={'status':'submission_unconfirmed','dialogs':[]}
        if self.auto_clear:
            self.fields={'side':'buy','unit':'shares','code':'','price':'','quantity':''}


class Batches(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'ops.db')
        self.client=BatchClient()
        self.account=account_id(self.client.label)
        self.orders=[{'side':'buy','code':code,'price':'1.23','quantity':'100'}
                     for code in ('600001','600002')]
        self.factory_calls=0
    def tearDown(self):
        self.store.db.close();self.tmp.cleanup()
    def factory(self,*args,**kwargs):
        self.factory_calls+=1
        return self.client
    def prepare(self):
        return dispatch({'action':'batches.prepare','exe':'test','account':self.account,
                         'orders':self.orders},self.store,self.factory)
    def run_batch(self,batch):
        return dispatch({'action':'batches.run-simulated','exe':'test','batch':batch['batch_id'],
                         'account':self.account,'digest':batch['digest']},self.store,self.factory)
    def test_two_orders_one_worker_and_receipts(self):
        batch=self.prepare()
        self.factory_calls=0
        result=self.run_batch(batch)
        self.assertTrue(result['ok'])
        self.assertEqual(result['status'],'completed')
        self.assertEqual(self.factory_calls,1)
        self.assertEqual(self.client.clicks,2)
        self.assertEqual([r['contract_no'] for r in result['orders']],['1001','1002'])
        self.assertTrue(all(r['form_cleared'] for r in result['orders']))
        with self.assertRaisesRegex(RuntimeError,'BATCH_ALREADY_ATTEMPTED'):
            self.run_batch(batch)
    def test_missing_receipt_stops_without_reclick(self):
        batch=self.prepare()
        self.client.fail_at=1
        result=self.run_batch(batch)
        self.assertFalse(result['ok'])
        self.assertEqual(result['status'],'needs_attention')
        self.assertEqual(result['orders'][0]['status'],'unknown')
        self.assertEqual(result['orders'][1]['status'],'queued')
        self.assertEqual(self.client.clicks,1)
        self.assertEqual(self.client.confirmations,1)
        with self.assertRaisesRegex(RuntimeError,'BATCH_ALREADY_ATTEMPTED'):
            self.run_batch(batch)
    def test_client_autoclears_after_receipt(self):
        batch=self.prepare()
        self.client.auto_clear=True
        result=self.run_batch(batch)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(self.client.clicks,2)
    def test_real_account_never_clicks(self):
        batch=self.prepare()
        self.client.label='真实账户-TEST'
        with self.assertRaisesRegex(RuntimeError,'SIMULATED_ACCOUNT_REQUIRED'):
            self.run_batch(batch)
        self.assertEqual(self.client.clicks,0)
    def test_real_account_cannot_prepare(self):
        self.client.label='真实账户-TEST'
        self.account=account_id(self.client.label)
        with self.assertRaisesRegex(RuntimeError,'SIMULATED_ACCOUNT_REQUIRED'):
            self.prepare()
        self.assertEqual(self.client.clicks,0)
    def test_wrong_digest_and_duplicate_plan(self):
        batch=self.prepare()
        with self.assertRaisesRegex(RuntimeError,'BATCH_DUPLICATE_PLAN'):
            self.prepare()
        with self.assertRaisesRegex(RuntimeError,'BATCH_EXPIRED_OR_MISMATCH'):
            dispatch({'action':'batches.run-simulated','exe':'test','batch':batch['batch_id'],
                      'account':self.account,'digest':'0'*64},self.store,self.factory)
        self.assertEqual(self.client.clicks,0)
    def test_crashed_run_requires_attention(self):
        batch=self.prepare()
        stored=self.store.get(batch['batch_id'])
        stored['status']='running'
        stored['orders'][0]['status']='confirm_attempted'
        self.store.save(stored)
        result=dispatch({'action':'batches.status','exe':'test','batch':batch['batch_id']},
                        self.store,self.factory)
        self.assertEqual(result['status'],'needs_attention')
        self.assertEqual(result['error'],'BATCH_INTERRUPTED')
        self.assertEqual(self.client.clicks,0)
    def test_receipt_requires_matching_side_and_contract(self):
        self.assertIsNone(receipt_contract({'dialogs':[{'text':'您的卖出委托已成功提交，合同编号：123'}]},'buy'))
        self.assertEqual(receipt_contract({'dialogs':[{'text':'您的买入委托已成功提交，合同编号：123'}]},'buy'),'123')


if __name__=='__main__':unittest.main()
