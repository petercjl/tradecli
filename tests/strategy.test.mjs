import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {buildStrategyPlan,planStrategyFile} from '../src/strategy.mjs';

const account='a_0123456789abcdef';
const review=()=>({ok:true,status:'reviewed',complete:true,source:'codex_visual_review',account_id:account,
 capture_id:'capture-1',captured_at:new Date().toISOString(),positions:[
  {code:'300359',name:'全通教育',quantity:'500',available:'300'},
  {code:'600010',name:'包钢股份',quantity:'100',available:'100'}]});

test('strategy converts share targets and order deltas to a reviewed before/after table',()=>{
 const target=buildStrategyPlan(review(),{targets:[
  {code:'300359',quantity:'300'},
  {code:'600221',name:'海航控股',quantity:'100'}]});
 assert.deepEqual(target.rows.map(x=>[x.code,x.current_quantity,x.side,x.quantity,x.after_quantity]),[
  ['300359','500','sell','200','300'],['600221','0','buy','100','100']]);
 assert.deepEqual(target.orders,[{side:'sell',code:'300359',quantity:'200'},{side:'buy',code:'600221',quantity:'100'}]);
 const split=buildStrategyPlan(review(),{orders:[
  {code:'300359',side:'sell',quantity:'100'},
  {code:'300359',side:'sell',quantity:'200'}]});
 assert.deepEqual(split.rows.map(x=>x.after_quantity),['400','200']);
 const liveShape=review();liveShape.captured_at=Date.now()/1000;
 assert.equal(buildStrategyPlan(liveShape,{orders:[{code:'300359',side:'sell',quantity:'100'}]}).rows[0].after_quantity,'400');
});

test('strategy rejects stale, mismatched, unavailable and unnamed plans',()=>{
 assert.throws(()=>buildStrategyPlan(review(),{orders:[{code:'300359',side:'sell',quantity:'400'}]}),/SELL_EXCEEDS_AVAILABLE/);
 assert.throws(()=>buildStrategyPlan(review(),{orders:[{code:'600221',side:'buy',quantity:'100'}]}),/SECURITY_NAME_REQUIRED/);
 assert.throws(()=>buildStrategyPlan(review(),{targets:[{code:'300359',quantity:'500'}]}),/STRATEGY_NO_CHANGE/);
 assert.throws(()=>buildStrategyPlan(review(),{targets:[{code:'300359',quantity:'0'}]}),/SELL_EXCEEDS_AVAILABLE/);
 assert.throws(()=>buildStrategyPlan(review(),{orders:[{code:'300359',side:'sell',quantity:'100'}]},'a_1111111111111111'),/PLAN_ACCOUNT_MISMATCH/);
 const old=review();old.captured_at=new Date(Date.now()-11*60_000).toISOString();
 assert.throws(()=>buildStrategyPlan(old,{orders:[{code:'300359',side:'sell',quantity:'100'}]}),/HOLDINGS_REVIEW_STALE/);
});

test('planner writes private executable orders and a bound plan',()=>{
 const previous=process.env.TRADECLI_HOME;
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'tradecli-strategy-'));
 process.env.TRADECLI_HOME=dir;
 try {
  const capture=path.join(dir,'captures','capture-1');fs.mkdirSync(capture,{recursive:true});
  const reviewFile=path.join(capture,'review-1234.json');const strategyFile=path.join(dir,'strategy.json');
  fs.writeFileSync(reviewFile,JSON.stringify(review()));
  fs.writeFileSync(strategyFile,JSON.stringify({orders:[{code:'600221',name:'海航控股',side:'buy',quantity:'100'}]}));
  const plan=planStrategyFile(reviewFile,strategyFile);
  assert.equal(plan.account_id,account);
  assert.deepEqual(JSON.parse(fs.readFileSync(plan.orders_path,'utf8')),{orders:plan.orders});
  assert.equal(fs.statSync(plan.orders_path).mode&0o777,0o600);
  assert.equal(fs.statSync(plan.plan_path).mode&0o777,0o600);
 } finally {if(previous===undefined)delete process.env.TRADECLI_HOME;else process.env.TRADECLI_HOME=previous;fs.rmSync(dir,{recursive:true,force:true});}
});
