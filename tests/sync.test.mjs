import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {buildSyncPlan,createSyncPlan,allocateSyncBuys} from '../src/sync.mjs';

const account='a_0123456789abcdef';
const now=()=>new Date().toISOString();
const review=(positions=[{code:'002051',name:'中工国际',quantity:'200',available:'200'}])=>({
 ok:true,status:'reviewed',complete:true,source:'codex_visual_review',account_id:account,
 current_account:'模拟炒股-TEST',capture_id:'capture',captured_at:now(),
 funds:{'可用金额':'10000.00'},positions
});
const live={name:'小市值周策略',is_limit:false,position_count:2,positions:[
 {code:'002591.XSHE',name:'恒大高新',asset_type:'股票',side:'多',amount:'100股',time:'2026-09-30 16:00:00'},
 {code:'002188.XSHE',name:'中天服务',asset_type:'股票',side:'多',amount:'200股',time:'2026-09-30 16:00:00'}
]};
test('sync compares stock identities and plans full exits before equal-cash entries',()=>{
 const plan=buildSyncPlan(review(),live,'小市值周策略');
 assert.deepEqual(plan.sells.map(x=>[x.code,x.quantity]),[['002051','200']]);
 assert.deepEqual(plan.buys.map(x=>x.code),['002591','002188']);
 assert.equal(plan.phase,'sell_then_verified_cash_then_buy');
});
test('sync blocks unavailable sells and ambiguous strategy data',()=>{
 const r=review();r.positions[0].available='100';
 assert.throws(()=>buildSyncPlan(r,live,'小市值周策略'),/SELL_NOT_FULLY_AVAILABLE/);
 assert.throws(()=>buildSyncPlan(review(),{...live,name:'other'},'小市值周策略'),/JQ_STRATEGY_POSITIONS_INCOMPLETE/);
 assert.throws(()=>buildSyncPlan(review(),{...live,is_limit:true},'小市值周策略'),/JQ_STRATEGY_POSITIONS_INCOMPLETE/);
});
test('allocation needs filled sells, refreshed empty holdings, current quotes, and funds',()=>{
 const old=process.env.TRADECLI_HOME,dir=fs.mkdtempSync(path.join(os.tmpdir(),'tradecli-sync-'));
 process.env.TRADECLI_HOME=dir;
 try {
  const capture=path.join(dir,'captures','capture');fs.mkdirSync(capture,{recursive:true});
  const before=path.join(capture,'review-a1b2.json');fs.writeFileSync(before,JSON.stringify(review()));
  const plan=createSyncPlan(before,'小市值周策略',account,live);
  const after=path.join(capture,'review-c3d4.json');
  const next=review([]);next.captured_at=new Date(Date.now()+1000).toISOString();next.funds['可用金额']='20000.00';
  fs.writeFileSync(after,JSON.stringify(next));
  const ledgerId='11111111-1111-4111-8111-111111111111';
  const ledgerDir=path.join(dir,'captures',ledgerId);fs.mkdirSync(ledgerDir);
  fs.writeFileSync(path.join(ledgerDir,'manifest.json'),JSON.stringify({account_id:account,source:'order_ledger_window'}));
  const fills=path.join(dir,'fills.json');fs.writeFileSync(fills,JSON.stringify({account_id:account,batch_id:'batch-1',ledger_capture_id:ledgerId,orders:[{code:'002051',status:'filled',filled_quantity:'200',contract_number:'123'}]}));
  const batch={ok:true,status:'completed',batch_id:'batch-1',account,mode:'market',orders:[{status:'accepted',order:{code:'002051',side:'sell',quantity:'200'},contract_no:'123'}]};
  const quotes=path.join(dir,'sync-plans','22222222-2222-4222-8222-222222222222-quotes.json');fs.writeFileSync(quotes,JSON.stringify({account_id:account,source:'ths_market_reference_fields',captured_at:now(),items:[{code:'002591',reference_price:'5.00'},{code:'002188',reference_price:'10.00'}]}));
  const allocated=allocateSyncBuys(plan.plan_path,after,fills,quotes,batch);
  assert.equal(allocated.per_security_cash,'10000.00');
  assert.deepEqual(allocated.rows.map(x=>x.quantity),['1900','900']);
  fs.writeFileSync(fills,JSON.stringify({account_id:account,batch_id:'batch-1',ledger_capture_id:ledgerId,orders:[{code:'002051',status:'accepted',filled_quantity:'0',contract_number:'123'}]}));
  assert.throws(()=>allocateSyncBuys(plan.plan_path,after,fills,quotes,batch),/SYNC_FILLS_INCOMPLETE/);
  assert.throws(()=>allocateSyncBuys(plan.plan_path,after,fills,quotes),/SYNC_SELL_BATCH_UNVERIFIED/);
  assert.equal(fs.statSync(plan.plan_path).mode&0o777,0o600);
 } finally {if(old===undefined)delete process.env.TRADECLI_HOME;else process.env.TRADECLI_HOME=old;fs.rmSync(dir,{recursive:true,force:true});}
});
