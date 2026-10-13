import test from 'node:test';
import assert from 'node:assert/strict';
import {validateReview} from '../src/visual.mjs';
const m={source:'window_image',capture_id:'test',image_sha256:'hash',account_id:'A',funds:{'股票市值':'10.01','资金余额':'5.02','可用金额':'5.02','总资产':'15.03'}};
const r={capture_id:'test',image_sha256:'hash',complete:true,all_rows_visible:true,rows:[{code:'000001',name:'示例',quantity:'100',available:'0',market_value:'10.01'}]};
test('visual review preserves codes and reconciles decimal amounts',()=>{const x=validateReview(m,r);assert.equal(x.ok,true);assert.equal(x.positions[0].code,'000001');});
test('wrong image or partial table cannot be accepted',()=>{assert.throws(()=>validateReview(m,{...r,image_sha256:'other'}));assert.throws(()=>validateReview(m,{...r,all_rows_visible:false}));});
test('duplicate codes and impossible available shares fail',()=>{assert.throws(()=>validateReview(m,{...r,rows:[...r.rows,...r.rows]}));assert.throws(()=>validateReview(m,{...r,rows:[{...r.rows[0],available:'101'}]}));});
test('disagreeing totals remain visible',()=>{const x=validateReview({...m,funds:{...m.funds,'总资产':'100'}},r);assert.equal(x.ok,true);assert.deepEqual(x.reconciliation.notes,['ASSET_RECONCILIATION_MISMATCH']);});

test('order screenshots cannot masquerade as holdings',()=>assert.throws(()=>validateReview({...m,source:'order_ledger_window'},r)));

test('signed zero preserves raw evidence and stale balance uses exactly reconciled available cash',()=>{
 const funds={'股票市值':'-0.00','资金余额':'5.00','可用金额':'100.00','总资产':'100.00'};
 const x=validateReview({...m,funds},{...r,rows:[]});
 assert.equal(x.ok,true);assert.deepEqual(x.funds,funds);
 assert.equal(x.reconciliation.cash_field,'可用金额');
 assert.deepEqual(x.reconciliation.notes,['ASSET_RECONCILIATION_MISMATCH']);
});
test('negative nonzero amounts remain rejected',()=>{
 for(const value of ['-0.01','-1','-0.0001']) assert.throws(()=>validateReview({...m,funds:{...m.funds,'股票市值':value}},r));
});
test('buy budget uses available funds regardless of balance or asset equation',()=>{
 for(const available of ['4.00','6.00','0.00']){
  const funds={'股票市值':'10.01','资金余额':'1.00','可用金额':available,'总资产':'15.03'};
  const x=validateReview({...m,funds},r);
  assert.equal(x.ok,true);assert.equal(x.reconciliation.buy_budget,available);
  assert.equal(x.reconciliation.cash_field,'可用金额');assert.deepEqual(x.funds,funds);
 }
});
test('frozen funds cannot inflate buy budget to balance',()=>{
 const x=validateReview({...m,funds:{...m.funds,'可用金额':'4.00'}},r);
 assert.equal(x.ok,true);assert.equal(x.reconciliation.buy_budget,'4.00');
});
test('missing malformed or negative available funds never fall back to balance',()=>{
 for(const available of [undefined,null,'','NaN','-0.01'])
  assert.throws(()=>validateReview({...m,funds:{...m.funds,'可用金额':available}},r));
});
test('unavailable balance is informational; stock mismatch still blocks',()=>{
 const x=validateReview({...m,funds:{...m.funds,'资金余额':'--'}},r);
 assert.equal(x.ok,true);assert.deepEqual(x.reconciliation.notes,['ASSET_RECONCILIATION_UNAVAILABLE']);
 const y=validateReview({...m,funds:{...m.funds,'股票市值':'11.00'}},r);
 assert.equal(y.ok,false);assert.ok(y.warnings.includes('DISPLAYED_STOCK_VALUE_MISMATCH'));
});
