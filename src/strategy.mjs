import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {Fault,home,privateDir} from './common.mjs';
import {validateBatchFile} from './batches.mjs';

const shares=value=>typeof value==='string' && /^(0|[1-9]\d{0,8})$/.test(value) ? BigInt(value) : null;
const code=value=>typeof value==='string' && /^\d{6}$/.test(value);
const name=value=>typeof value==='string' && value.trim() && value.trim().length<=40;

export function buildStrategyPlan(review,strategy,account=review?.account_id,priceMode='client_default') {
 if(!review || review.ok!==true || review.status!=='reviewed' || review.complete!==true || !Array.isArray(review.positions)
    || review.source!=='codex_visual_review' || !/^a_[a-f0-9]{16}$/.test(review.account_id||''))throw new Fault('HOLDINGS_REVIEW_REQUIRED');
 if(account!==review.account_id)throw new Fault('PLAN_ACCOUNT_MISMATCH');
 const captured=typeof review.captured_at==='number' ? review.captured_at*1000 : Date.parse(review.captured_at);
 if(!Number.isFinite(captured) || Date.now()-captured>10*60_000 || captured-Date.now()>30_000)throw new Fault('HOLDINGS_REVIEW_STALE');
 if(!strategy || Array.isArray(strategy) || typeof strategy!=='object' || Object.keys(strategy).length!==1)throw new Fault('STRATEGY_INVALID');
 const mode=Array.isArray(strategy.orders)?'orders':Array.isArray(strategy.targets)?'targets':null;
 if(!mode || Object.keys(strategy)[0]!==mode || strategy[mode].length<1 || strategy[mode].length>15)throw new Fault('STRATEGY_INVALID');
 const held=new Map(review.positions.map(row=>[row.code,{name:row.name,current:shares(row.quantity),available:shares(row.available)}]));
 if([...held.values()].some(row=>!name(row.name)||row.current===null||row.available===null||row.available>row.current))throw new Fault('HOLDINGS_REVIEW_INVALID');
 const rows=[];const orders=[];const remaining=new Map();const buyCodes=new Set();const targetCodes=new Set();
 for(const [index,item] of strategy[mode].entries()) {
  if(!item || Array.isArray(item) || typeof item!=='object' || !code(item.code))throw new Fault('STRATEGY_ROW_INVALID',{index});
  const h=held.get(item.code);const supplied=item.name;
  if(supplied!==undefined && !name(supplied))throw new Fault('SECURITY_NAME_REQUIRED',{index});
  if(h && supplied && supplied.trim()!==h.name.trim())throw new Fault('SECURITY_NAME_MISMATCH',{index,code:item.code});
  const resolved=h?.name || supplied?.trim();
  if(!resolved)throw new Fault('SECURITY_NAME_REQUIRED',{index,code:item.code});
  const before=remaining.get(item.code) ?? h?.current ?? 0n;
  let side,quantity;
  if(mode==='orders') {
   if(![3,4].includes(Object.keys(item).length) || Object.keys(item).some(x=>!['code','name','side','quantity'].includes(x))
      || !['buy','sell'].includes(item.side) || shares(item.quantity)===null || shares(item.quantity)===0n)throw new Fault('STRATEGY_ROW_INVALID',{index});
   side=item.side;quantity=shares(item.quantity);
  } else {
   if(![2,3].includes(Object.keys(item).length) || Object.keys(item).some(x=>!['code','name','quantity'].includes(x))
      || shares(item.quantity)===null || targetCodes.has(item.code))throw new Fault('STRATEGY_ROW_INVALID',{index});
   targetCodes.add(item.code);
   const target=shares(item.quantity);if(target===before)continue;
   side=target>before?'buy':'sell';quantity=target>before?target-before:before-target;
  }
  if(side==='buy' && buyCodes.has(item.code))throw new Fault('BATCH_DUPLICATE_SECURITY',{code:item.code});
  if(side==='buy')buyCodes.add(item.code);
  const after=side==='buy'?before+quantity:before-quantity;
  if(after<0n)throw new Fault('SELL_EXCEEDS_HOLDINGS',{code:item.code});
  const available=h?.available ?? 0n;
  if(side==='sell') {
   const previouslySold=rows.filter(x=>x.code===item.code&&x.side==='sell').reduce((n,x)=>n+BigInt(x.quantity),0n);
   if(previouslySold+quantity>available)throw new Fault('SELL_EXCEEDS_AVAILABLE',{code:item.code});
  }
  remaining.set(item.code,after);
  const row={index:rows.length+1,code:item.code,name:resolved,current_quantity:before.toString(),available_quantity:available.toString(),side,quantity:quantity.toString(),after_quantity:after.toString()};
  rows.push(row);orders.push({side,code:item.code,quantity:quantity.toString()});
 }
 if(!orders.length)throw new Fault('STRATEGY_NO_CHANGE');
 // The batch validator remains the execution contract for quantity and duplicate buys.
 return {account_id:account,source_capture_id:review.capture_id,source_captured_at:review.captured_at,price_mode:priceMode,rows,orders};
}

export function planStrategyFile(reviewFile,strategyFile,account,priceMode='client_default') {
 let review,strategy;
 try {review=JSON.parse(fs.readFileSync(reviewFile,'utf8'));strategy=JSON.parse(fs.readFileSync(strategyFile,'utf8'));}
 catch {throw new Fault('STRATEGY_INPUT_INVALID');}
 const capturesRoot=path.resolve(home(),'captures')+path.sep;
 if(!path.resolve(reviewFile).startsWith(capturesRoot) || !/^review-[a-f0-9-]+\.json$/.test(path.basename(reviewFile)))throw new Fault('HOLDINGS_REVIEW_REQUIRED');
 const plan=buildStrategyPlan(review,strategy,account,priceMode);
 const dir=path.join(home(),'plans');privateDir(dir);
 const id=crypto.randomUUID();const ordersPath=path.join(dir,`${id}-orders.json`);
 fs.writeFileSync(ordersPath,JSON.stringify({orders:plan.orders},null,2)+'\n',{flag:'wx',mode:0o600});
 validateBatchFile(ordersPath,'default');
 const planPath=path.join(dir,`${id}-plan.json`);
 fs.writeFileSync(planPath,JSON.stringify({...plan,plan_id:id,orders_path:ordersPath},null,2)+'\n',{flag:'wx',mode:0o600});
 return {ok:true,status:'planned',plan_id:id,plan_path:planPath,orders_path:ordersPath,...plan};
}
