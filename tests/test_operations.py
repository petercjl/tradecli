import sys, unittest, tempfile, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from ths import Store, dispatch, PendingCopy, parse_grid, account_id

class Fake:
    current='A'
    copies=0
    def __init__(self, exe): pass
    def accounts(self): return {'current_account':self.current,'accounts':[{'label':'A','index':0},{'label':'B','index':1}], 'current_index':0 if self.current=='A' else 1}
    def switch(self,label): self.current=label; return self.accounts()
    def funds(self): return dict(self.accounts(),funds={'资金余额':'100.00'})
    def positions(self,persist):
        self.copies+=1
        checkpoint={'account':self.current}
        persist(checkpoint)
        raise PendingCopy('USER_VERIFICATION_REQUIRED',checkpoint)
    def capture_positions(self):
        return dict(self.funds(),image_base64='fixture',review_required=True,clipboard_unchanged=True)
    def open_page(self,page):pass
    def resume(self,checkpoint):
        if checkpoint['account']!=self.current: raise RuntimeError('COPY_CHECKPOINT_ACCOUNT_MISMATCH')
        return dict(self.funds(),positions=[])

class Operations(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'ops.db');self.client=Fake('x')
    def tearDown(self):self.store.db.close();self.tmp.cleanup()
    def call(self,action,**args):return dispatch(dict(action=action,exe='test',**args),self.store,lambda _:self.client)
    def pending(self,target='A'):
        self.client.current=target;self.client.copies=1
        op={'id':'legacy','exe':'test','kind':'positions','status':'waiting','original':'A','targets':[target],
            'index':0,'results':[],'requested_at':time.time(),'checkpoint':{'account':target}}
        self.store.save(op)
        return {'operation_id':'legacy','status':'waiting'}
    def test_new_positions_uses_capture_and_never_copy(self):
        result=self.call('positions',account=account_id('B'))
        self.assertTrue(result['ok']);self.assertEqual(self.client.copies,0)
        self.assertTrue(result['results'][0]['review_required']);self.assertEqual(self.client.current,'A')
    def test_account_select_retains_selection(self):
        result=self.call('accounts.select',account=account_id('B'))
        self.assertTrue(result['ok']);self.assertEqual(self.client.current,'B')
    def test_resume_never_repeats_copy_and_restores(self):
        result=self.pending('B')
        self.assertEqual(result['status'],'waiting');self.assertEqual(self.client.current,'B')
        self.assertEqual(self.call('funds')['error'],'OPERATION_PENDING')
        result=self.call('operations.resume',id=result['operation_id'])
        self.assertTrue(result['ok']);self.assertEqual(self.client.copies,1);self.assertEqual(self.client.current,'A')
        self.assertTrue(self.call('operations.resume',id=result['operation_id'])['ok'])
        self.assertEqual(self.client.copies,1)
    def test_abandon_requires_confirmation_and_keeps_evidence(self):
        result=self.pending();identity=result['operation_id']
        with self.assertRaisesRegex(RuntimeError,'CONFIRMATION_REQUIRED'):self.call('operations.abandon',id=identity)
        self.assertTrue(self.call('operations.abandon',id=identity,yes=True)['ok'])
        self.assertEqual(self.store.get(identity)['status'],'abandoned')
    def test_unknown_command_cannot_reach_client(self):
        for action in ('buy','sell','cancel','switch'):
            with self.assertRaisesRegex(RuntimeError,'COMMAND_UNSUPPORTED'):self.call(action)
    def test_duplicate_accounts_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'DUPLICATED'):self.call('snapshot',accounts=[account_id('A')]*2)
    def test_mismatch_blocks_resume(self):
        result=self.pending();self.client.current='B'
        result=self.call('operations.resume',id=result['operation_id'])
        self.assertFalse(result['ok']);self.assertEqual(result['error'],'COPY_CHECKPOINT_ACCOUNT_MISMATCH');self.assertEqual(self.client.copies,1);self.assertEqual(self.client.current,'B');self.assertEqual(result['status'],'waiting')
    def test_collection_error_keeps_checkpoint_for_read_only_retry(self):
        result=self.pending()
        def broken(checkpoint):raise AttributeError('internal failure')
        self.client.resume=broken
        retry=self.call('operations.resume',id=result['operation_id'])
        self.assertEqual(retry['status'],'waiting')
        self.assertEqual(self.call('funds')['error'],'OPERATION_PENDING')
        self.assertEqual(self.client.copies,1)
    def test_database_retains_checkpoint_across_connections(self):
        result=self.pending();self.store.db.close();self.store=Store(Path(self.tmp.name)/'ops.db')
        self.assertIn('checkpoint',self.store.get(result['operation_id']))
    def test_grid_strings_and_empty_table(self):
        self.assertEqual(parse_grid('证券代码\t证券名称\t市值\n000001\t示例\t1,000.01\n')[0]['证券代码'],'000001')
        self.assertEqual(parse_grid('证券代码\t证券名称\t市值\n'),[])
        for bad in ['代码\t市值\n','证券代码\t证券名称\t市值\n000001\t示例\tNaN\n','证券代码\t证券名称\t市值\n=cmd\t示例\t0\n']:
            with self.assertRaises(RuntimeError):parse_grid(bad)

if __name__=='__main__':unittest.main()
