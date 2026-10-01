import sys,unittest,tempfile,time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from ths import Store,dispatch,account_id,ReadOnlyTHS,validate_order,validate_confirmation,type_numeric_edit,read_edit

class Sim:
    assert_simulated=ReadOnlyTHS.assert_simulated
    def __init__(self):
        self.label='模拟炒股-TEST';self.clicks=0
        self.fields={'unit':'shares','side':'buy','code':'002051','price':'8.740','quantity':'100'}
    def accounts(self):return {'current_account':self.label}
    def check_ready(self):pass
    def order_fields(self,side):return self.fields
    def control(self,kind,identity):
        assert (kind,identity)==('Button',1006)
        return SimpleNamespace(click=self.click)
    def click(self):self.clicks+=1
    def order_response(self):return {'status':'submission_unconfirmed'}

class Orders(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'ops.db');self.client=Sim()
        self.order=dict(self.client.fields,account=account_id(self.client.label))
        self.draft={'id':'draft','kind':'order','exe':'test','order':self.order,'status':'prepared','requested_at':time.time(),'results':[]}
        self.store.save(self.draft)
    def tearDown(self):self.store.db.close();self.tmp.cleanup()
    def submit(self,**kw):
        return dispatch(dict(action='orders.submit-simulated',exe='test',draft='draft',account=self.order['account'],**kw),self.store,lambda _:self.client)
    def test_live_account_never_clicks(self):
        self.client.label='证券公司-TEST'
        with self.assertRaisesRegex(RuntimeError,'SIMULATED_ACCOUNT_REQUIRED'):self.submit()
        self.assertEqual(self.client.clicks,0)
    def test_attempt_is_not_repeated(self):
        self.assertTrue(self.submit()['submission_attempted'])
        with self.assertRaisesRegex(RuntimeError,'ALREADY_ATTEMPTED'):self.submit()
        self.assertEqual(self.client.clicks,1)
    def test_changed_form_never_clicks(self):
        self.client.fields=dict(self.client.fields,quantity='200')
        with self.assertRaisesRegex(RuntimeError,'READBACK_MISMATCH'):self.submit()
        self.assertEqual(self.client.clicks,0)
    def test_amount_mode_never_clicks(self):
        self.client.fields=dict(self.client.fields,unit='amount')
        with self.assertRaisesRegex(RuntimeError,'READBACK_MISMATCH'):self.submit()
        self.assertEqual(self.client.clicks,0)
    def test_expired_draft_never_clicks(self):
        self.draft['requested_at']-=301;self.store.save(self.draft)
        with self.assertRaisesRegex(RuntimeError,'EXPIRED'):self.submit()
        self.assertEqual(self.client.clicks,0)
    def test_click_exception_remains_attempted(self):
        def broken():raise RuntimeError('UI_TIMEOUT')
        self.client.click=broken
        with self.assertRaisesRegex(RuntimeError,'UI_TIMEOUT'):self.submit()
        self.assertEqual(self.store.get('draft')['status'],'submission_attempted')
    def test_confirmation_binds_all_fields_and_account(self):
        text='资金帐号：模拟炒股-TEST\n证券代码：002051(示例)\n买入价格：8.740\n买入数量：100\n您是否确定以上买入委托？'
        self.assertTrue(validate_confirmation(text,self.order,self.client.label))
        for old,new in [('TEST','OTHER'),('002051','000001'),('8.740','8.750'),('数量：100','数量：200'),('买入','卖出')]:
            self.assertFalse(validate_confirmation(text.replace(old,new),self.order,self.client.label))
    def test_explicit_selection_replaces_existing_numeric_text(self):
        class Edit:
            value='8.74'
            def set_focus(self):pass
            def select(self,start=0,end=0):self.selection=(start,end)
            def type_keys(self,value,**kwargs):
                self.value=value if self.selection==(0,-1) else self.value+value
            def texts(self):return ['',self.value]
        edit=Edit();type_numeric_edit(edit,'4.83')
        self.assertEqual(read_edit(edit),'4.83')
        with self.assertRaisesRegex(RuntimeError,'VALUE_INVALID'):type_numeric_edit(edit,'{ENTER}')
    def test_ambiguous_readback_stops(self):
        with self.assertRaisesRegex(RuntimeError,'AMBIGUOUS'):
            read_edit(SimpleNamespace(texts=lambda:['100','200']))
    def test_confirmation_attempt_survives_failure_and_cannot_repeat(self):
        self.draft['status']='submission_attempted';self.store.save(self.draft)
        def fail(order,before_send):
            before_send()
            raise RuntimeError('UI_TIMEOUT')
        self.client.confirm_order=fail
        request=dict(action='orders.confirm-simulated',exe='test',draft='draft',account=self.order['account'])
        factory=lambda *a,**k:self.client
        with self.assertRaisesRegex(RuntimeError,'UI_TIMEOUT'):dispatch(request,self.store,factory)
        self.assertEqual(self.store.get('draft')['status'],'confirmation_attempted')
        with self.assertRaisesRegex(RuntimeError,'ALREADY_ATTEMPTED'):dispatch(request,self.store,factory)
    def test_unknown_receipt_cannot_be_acknowledged(self):
        self.draft['status']='confirmation_attempted'
        self.draft['response']={'status':'submission_unconfirmed'};self.store.save(self.draft)
        request=dict(action='orders.acknowledge',exe='test',draft='draft',account=self.order['account'])
        with self.assertRaisesRegex(RuntimeError,'RECEIPT_REQUIRED'):
            dispatch(request,self.store,lambda *a,**k:self.client)
    def test_future_draft_never_clicks(self):
        self.draft['requested_at']+=600;self.store.save(self.draft)
        with self.assertRaisesRegex(RuntimeError,'EXPIRED'):self.submit()
        self.assertEqual(self.client.clicks,0)
    def test_confirmation_waits_for_contract_after_dialog_disappears(self):
        events=[]
        modal=SimpleNamespace(handle=7,type_keys=lambda key,**kw:events.append(('key',key)))
        self.client.confirmation_window=lambda order:modal
        responses=iter([{'status':'submission_unconfirmed','dialogs':[]},
                        {'status':'dialog_review_required','dialogs':[{'text':'您的买入委托已成功提交，合同编号：12345'}]}])
        self.client.order_response=lambda:next(responses)
        response=ReadOnlyTHS.confirm_order(self.client,self.order,lambda:events.append(('persist',None)))
        self.assertEqual(events,[('persist',None),('key','%Y')])
        self.assertEqual(response['status'],'submission_accepted')
        self.assertEqual(len(response['timeline']),3)
    def test_invalid_inputs_fail(self):
        for field,bad in [('code','1'),('price','NaN'),('price','0'),('quantity','0'),('quantity','1.5'),('side','cancel')]:
            with self.subTest(field=field,bad=bad):
                with self.assertRaises(RuntimeError):validate_order(dict(self.order,**{field:bad}))

if __name__=='__main__':unittest.main()
