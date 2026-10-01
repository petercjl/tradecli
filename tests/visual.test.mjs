import test from 'node:test';
import assert from 'node:assert/strict';
import {validateReview} from '../src/visual.mjs';
const m={source:'window_image',capture_id:'test',image_sha256:'hash',account_id:'A',funds:{'股票市值':'10.01','资金余额':'5.02','总资产':'15.03'}};
const r={capture_id:'test',image_sha256:'hash',complete:true,all_rows_visible:true,rows:[{code:'000001',name:'示例',quantity:'100',available:'0',market_value:'10.01'}]};
test('visual review preserves codes and reconciles decimal amounts',()=>{const x=validateReview(m,r);assert.equal(x.ok,true);assert.equal(x.positions[0].code,'000001');});
test('wrong image or partial table cannot be accepted',()=>{assert.throws(()=>validateReview(m,{...r,image_sha256:'other'}));assert.throws(()=>validateReview(m,{...r,all_rows_visible:false}));});
test('duplicate codes and impossible available shares fail',()=>{assert.throws(()=>validateReview(m,{...r,rows:[...r.rows,...r.rows]}));assert.throws(()=>validateReview(m,{...r,rows:[{...r.rows[0],available:'101'}]}));});
test('disagreeing totals remain visible',()=>{const x=validateReview({...m,funds:{...m.funds,'总资产':'100'}},r);assert.equal(x.ok,false);assert.deepEqual(x.warnings,['ASSET_RECONCILIATION_MISMATCH']);});

test('order screenshots cannot masquerade as holdings',()=>assert.throws(()=>validateReview({...m,source:'order_ledger_window'},r)));
