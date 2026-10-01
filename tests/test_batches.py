import sys, unittest, tempfile, time, json, hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from ths import Store, dispatch, account_id, ReadOnlyTHS, receipt_contract, decode_request


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
    def default_price_order(self,order,preview=False):
        price='1.24' if preview else '1.25'
        result={**order,'price':price,'unit':'shares',
                'price_source':'ths_default_price_field','captured_at':time.time()}
        if not preview:self.fields=result
        return result
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
        action='买入' if order['side']=='buy' else '卖出'
        self.receipt_text=f'您的{action}委托已成功提交，合同编号：{1000+self.confirmations}'
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
                         'account':self.account,'digest':batch['digest'],'confirmed':True},self.store,self.factory)
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
    def test_default_price_is_bound_at_execution(self):
        self.orders=[{'side':'buy','code':'600001','quantity':'100'}]
        batch=dispatch({'action':'batches.prepare-default','exe':'test','account':self.account,
                        'orders':self.orders},self.store,self.factory)
        self.assertIsNone(batch['estimated_buy_total'])
        self.assertEqual(self.factory_calls,0)
        result=self.run_batch(batch)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['orders'][0]['order']['price'],'1.25')
        self.assertEqual(self.client.clicks,1)
    def test_fifteen_orders_with_split_sells(self):
        self.orders=([{'side':'buy','code':str(600001+i),'price':'1.23','quantity':'100'}
                      for i in range(10)]
                     +[{'side':'sell','code':code,'price':'2.00','quantity':'100'}
                       for code in ('300359','300737','002051','300359','002051')])
        batch=self.prepare()
        self.factory_calls=0
        result=self.run_batch(batch)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(self.factory_calls,1)
        self.assertEqual(self.client.clicks,15)
        self.assertEqual(len({row['contract_no'] for row in result['orders']}),15)
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
        with self.assertRaisesRegex(RuntimeError,'CONFIRMATION_REQUIRED'):
            dispatch({'action':'batches.run-simulated','exe':'test','batch':batch['batch_id'],
                      'account':self.account,'digest':batch['digest']},self.store,self.factory)
        with self.assertRaisesRegex(RuntimeError,'BATCH_EXPIRED_OR_MISMATCH'):
            dispatch({'action':'batches.run-simulated','exe':'test','batch':batch['batch_id'],
                      'account':self.account,'digest':'0'*64,'confirmed':True},self.store,self.factory)
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
    def test_file_request_requires_exact_hash(self):
        file=Path(self.tmp.name)/'request.json'
        self.assertFalse(file.exists())
        content=json.dumps({'action':'batches.prepare-default','orders':self.orders}).encode()
        file.write_bytes(content)
        digest=hashlib.sha256(content).hexdigest()
        self.assertEqual(decode_request(['--request-file',str(file),digest])['orders'],self.orders)
        file.write_bytes(content+b' ')
        with self.assertRaisesRegex(RuntimeError,'REQUEST_HASH_MISMATCH'):
            decode_request(['--request-file',str(file),digest])
    def test_default_execution_never_types_price(self):
        client=BatchClient()
        client.fields={'side':'buy','unit':'shares','code':'','price':'','quantity':''}
        writes=[]
        class Edit:
            def __init__(self,key):self.key=key
            def is_enabled(self):return True
            def set_focus(self):pass
            def select(self,start,end):pass
            def type_keys(self,value,**kwargs):
                writes.append(self.key)
                client.fields[self.key]=value
                if self.key=='code':client.fields['price']='1.23'
        def control(kind,cid):
            assert kind=='Edit'
            key={1032:'code',1033:'price',1034:'quantity'}[cid]
            if key=='price':raise AssertionError('price field was accessed for writing')
            return Edit(key)
        client.control=control
        client.open_page=lambda side:None
        with patch('ths.time.sleep',lambda _:None):
            actual=ReadOnlyTHS.default_price_order(client,{'side':'buy','code':'600221',
                'quantity':'100','account':self.account})
        self.assertEqual(actual['price'],'1.23')
        self.assertEqual(writes,['code','quantity'])


if __name__=='__main__':unittest.main()
