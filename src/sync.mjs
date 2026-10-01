import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {Fault,home,privateDir,run} from './common.mjs';
import {buildStrategyPlan} from './strategy.mjs';

const code = value => typeof value === 'string' && /^\d{6}$/.test(value);
const amount = value => typeof value === 'string' && /^(0|[1-9]\d{0,8})$/.test(value);
const fresh = value => {
 const at = typeof value === 'number' ? value * 1000 : Date.parse(value);
 return Number.isFinite(at) && at <= Date.now() + 30000 && Date.now() - at <= 10 * 60000;
};
function readJson(file, fault) {
 try {return JSON.parse(fs.readFileSync(file,'utf8'));} catch {throw new Fault(fault);}
}
function reviewFromCapture(file) {
 const base=path.resolve(home(),'captures')+path.sep;
 if(!path.resolve(file).startsWith(base) || !/^review-[a-f0-9-]+\.json$/.test(path.basename(file)))throw new Fault('HOLDINGS_REVIEW_REQUIRED');
 const review=readJson(file,'HOLDINGS_REVIEW_REQUIRED');
 if(review.ok!==true || review.status!=='reviewed' || review.complete!==true || review.source!=='codex_visual_review' || !fresh(review.captured_at))throw new Fault('HOLDINGS_REVIEW_STALE_OR_INVALID');
 return review;
}
function targetPositions(live,requestedName) {
 if(live?.name!==requestedName || !Array.isArray(live.positions) || live.is_limit!==false)throw new Fault('JQ_STRATEGY_POSITIONS_INCOMPLETE');
 const seen=new Set();
 const positions=live.positions.filter(row=>row.asset_type==='股票' && row.side==='多' && /^\d+股$/.test(row.amount) && Number.parseInt(row.amount)>0).map(row=>{
  const match=/^(\d{6})\.(XSHE|XSHG)$/.exec(row.code||'');
  if(!match || !row.name?.trim() || seen.has(match[1]))throw new Fault('JQ_STRATEGY_POSITION_INVALID');
  seen.add(match[1]);return {code:match[1],name:row.name.trim()};
 });
 if(positions.length!==live.position_count || !positions.length || positions.length>15)throw new Fault('JQ_STRATEGY_POSITIONS_INCOMPLETE');
 const times=live.positions.map(x=>Date.parse(x.time)).filter(Number.isFinite);
 if(times.length!==live.positions.length || new Set(times).size!==1)throw new Fault('JQ_STRATEGY_ASOF_AMBIGUOUS');
 return {positions,asof:new Date(times[0]).toISOString()};
}
export function fetchJoinQuantLive(name) {
 if(typeof name!=='string' || !name.trim() || name.length>80)throw new Fault('JQ_STRATEGY_NAME_REQUIRED');
 let live;
 try {live=JSON.parse(run('jqcli',['--format','json','--non-interactive','live','positions','--name',name],{timeout:60000}));}
 catch(e) {throw new Fault('JQCLI_QUERY_FAILED',{reason:e.code||'INVALID_JSON'});}
 return live;
}
export function buildSyncPlan(review,live,requestedName,account=review?.account_id) {
 const target=targetPositions(live,requestedName);
 if(account!==review.account_id)throw new Fault('PLAN_ACCOUNT_MISMATCH');
 if(!fresh(review.captured_at))throw new Fault('HOLDINGS_REVIEW_STALE');
 const held=new Map(review.positions.map(row=>[row.code,row]));
 if(held.size!==review.positions.length || [...held.keys()].some(x=>!code(x)))throw new Fault('HOLDINGS_REVIEW_INVALID');
 const wanted=new Set(target.positions.map(x=>x.code));
 const sells=review.positions.filter(row=>!wanted.has(row.code)).map(row=>{
  if(!amount(row.quantity)||!amount(row.available)||row.quantity==='0')throw new Fault('HOLDINGS_REVIEW_INVALID');
  if(row.quantity!==row.available)throw new Fault('SELL_NOT_FULLY_AVAILABLE',{code:row.code});
  return {code:row.code,name:row.name,quantity:row.quantity,current_quantity:row.quantity,after_quantity:'0',side:'sell'};
 });
 const buys=target.positions.filter(row=>!held.has(row.code)).map(row=>({code:row.code,name:row.name,current_quantity:'0',side:'buy',allocation:'equal_remaining_cash'}));
 if(sells.length>15 || buys.length>15)throw new Fault('SYNC_BATCH_TOO_LARGE');
 if(sells.length) buildStrategyPlan(review,{orders:sells.map(({code,name,quantity,side})=>({code,name,quantity,side}))},account,'market');
 return {account_id:account,account_label:review.current_account,source_capture_id:review.capture_id,
  holdings_captured_at:review.captured_at,strategy_name:requestedName,strategy_asof:target.asof,
  target:target.positions,sells,buys,unchanged:target.positions.filter(row=>held.has(row.code)),
  available_before:review.funds?.['可用金额'],phase:'sell_then_verified_cash_then_buy'};
}
export function createSyncPlan(reviewFile,strategyName,account,live) {
 const review=reviewFromCapture(reviewFile);
 live ??= fetchJoinQuantLive(strategyName);
 const plan=buildSyncPlan(review,live,strategyName,account);
 const dir=path.join(home(),'sync-plans');privateDir(dir);
 const id=crypto.randomUUID();const planPath=path.join(dir,`${id}.json`);
 const sellOrdersPath=plan.sells.length?path.join(dir,`${id}-sells.json`):null;
 if(sellOrdersPath)fs.writeFileSync(sellOrdersPath,JSON.stringify({orders:plan.sells.map(({side,code,quantity})=>({side,code,quantity}))},null,2)+'\n',{flag:'wx',mode:0o600});
 fs.writeFileSync(planPath,JSON.stringify({...plan,plan_id:id,sell_orders_path:sellOrdersPath},null,2)+'\n',{flag:'wx',mode:0o600});
 return {ok:true,status:'planned',plan_id:id,plan_path:planPath,sell_orders_path:sellOrdersPath,...plan};
}
export function allocateSyncBuys(planFile,reviewFile,fillsFile,quotesFile,batch) {
 const base=path.resolve(home(),'sync-plans')+path.sep;
 if(!path.resolve(planFile).startsWith(base)|| !/^[a-f0-9-]{36}\.json$/.test(path.basename(planFile)))throw new Fault('SYNC_PLAN_REQUIRED');
 const plan=readJson(planFile,'SYNC_PLAN_REQUIRED');const review=reviewFromCapture(reviewFile);
 if(plan.account_id!==review.account_id || !Array.isArray(plan.buys) || !Array.isArray(plan.sells))throw new Fault('SYNC_ACCOUNT_MISMATCH');
 const reviewTime=typeof review.captured_at==='number'?review.captured_at*1000:Date.parse(review.captured_at);
 const planTime=typeof plan.holdings_captured_at==='number'?plan.holdings_captured_at*1000:Date.parse(plan.holdings_captured_at);
 if(reviewTime<=planTime)throw new Fault('SYNC_HOLDINGS_NOT_REFRESHED');
 const held=new Set(review.positions.map(x=>x.code));
 if(plan.sells.some(x=>held.has(x.code)))throw new Fault('SYNC_SELLS_NOT_COMPLETE');
 if(plan.buys.some(x=>held.has(x.code)))throw new Fault('SYNC_BUY_TARGET_CHANGED');
 const fills=readJson(fillsFile,'SYNC_FILLS_REQUIRED');
 if(fills.account_id!==plan.account_id || !fills.ledger_capture_id || !Array.isArray(fills.orders)||fills.orders.length!==plan.sells.length)throw new Fault('SYNC_FILLS_INCOMPLETE');
 if(plan.sells.length) {
  if(!/^[a-f0-9-]{36}$/.test(fills.ledger_capture_id))throw new Fault('SYNC_LEDGER_EVIDENCE_INVALID');
  const manifest=readJson(path.join(home(),'captures',fills.ledger_capture_id,'manifest.json'),'SYNC_LEDGER_EVIDENCE_INVALID');
  if(manifest.account_id!==plan.account_id || manifest.source!=='order_ledger_window')throw new Fault('SYNC_LEDGER_EVIDENCE_INVALID');
 }
 if(plan.sells.length && (batch?.ok!==true || batch.status!=='completed' || batch.account!==plan.account_id
    || batch.batch_id!==fills.batch_id || batch.mode!=='market' || !Array.isArray(batch.orders)
    || batch.orders.length!==plan.sells.length))throw new Fault('SYNC_SELL_BATCH_UNVERIFIED');
 for(const sell of plan.sells) {
  const matches=fills.orders.filter(x=>x.code===sell.code);
  if(matches.length!==1 || matches[0].status!=='filled' || matches[0].filled_quantity!==sell.quantity || !matches[0].contract_number)throw new Fault('SYNC_FILLS_INCOMPLETE',{code:sell.code});
  if(plan.sells.length) {
   const receipts=batch.orders.filter(x=>x.order?.code===sell.code && x.order?.side==='sell');
   if(receipts.length!==1 || receipts[0].status!=='accepted' || receipts[0].order.quantity!==sell.quantity
      || receipts[0].contract_no!==matches[0].contract_number)throw new Fault('SYNC_SELL_BATCH_UNVERIFIED',{code:sell.code});
  }
 }
 if(!path.resolve(quotesFile).startsWith(base) || !/^[a-f0-9-]{36}-quotes\.json$/.test(path.basename(quotesFile)))throw new Fault('SYNC_QUOTES_REQUIRED');
 const quotes=readJson(quotesFile,'SYNC_QUOTES_REQUIRED');
 if(quotes.account_id!==plan.account_id || quotes.source!=='ths_market_reference_fields' || !Array.isArray(quotes.items) || quotes.items.length!==plan.buys.length || !fresh(quotes.captured_at))throw new Fault('SYNC_QUOTES_STALE_OR_INVALID');
 const price=new Map();for(const item of quotes.items) {
  if(!code(item.code)||!/^\d{1,6}(?:\.\d{1,3})?$/.test(item.reference_price)||Number(item.reference_price)<=0||price.has(item.code))throw new Fault('SYNC_QUOTE_INVALID');
  price.set(item.code,Number(item.reference_price));
 }
 const cash=Number(review.funds?.['可用金额']);
 if(!Number.isFinite(cash)||cash<0)throw new Fault('SYNC_FUNDS_INVALID');
 const perName=plan.buys.length ? cash/plan.buys.length : 0;
 // Two percent price movement headroom plus a five-yuan fee reserve per order.
 const budget=Math.max(0,perName*0.98-5);
 const rows=plan.buys.map(item=>{
  const p=price.get(item.code);if(!p)throw new Fault('SYNC_QUOTE_MISSING',{code:item.code});
  const qty=100*Math.floor(budget/(p*100));
  return {code:item.code,name:item.name,side:'buy',reference_price:p.toFixed(3),allocation_cash:perName.toFixed(2),quantity:String(qty)};
 });
 if(rows.some(x=>x.quantity==='0'))throw new Fault('SYNC_BUDGET_BELOW_MINIMUM_LOT');
 const ordersPath=path.join(home(),'sync-plans',`${crypto.randomUUID()}-buys.json`);
 fs.writeFileSync(ordersPath,JSON.stringify({orders:rows.map(({side,code,quantity})=>({side,code,quantity}))},null,2)+'\n',{flag:'wx',mode:0o600});
 return {ok:true,status:'allocated_pending_confirmation',account_id:plan.account_id,plan_id:plan.plan_id,orders_path:ordersPath,
  available_cash:cash.toFixed(2),per_security_cash:perName.toFixed(2),rows,
  note:'Reference prices estimate quantities; market fills and fees may differ. Refresh evidence and confirm exact shares before order submission.'};
}
