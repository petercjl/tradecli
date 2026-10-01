import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {home,privateDir,Fault} from './common.mjs';
export function saveCaptures(result) {
 if(!result.results?.some(x=>x.image_base64))return result;
 const base=path.join(home(),'captures');privateDir(base);
 const captures=[];
 result.results=result.results.map(row=>{
  if(!row.image_base64)return row;
  const id=crypto.randomUUID();const folder=path.join(base,id);fs.mkdirSync(folder,{mode:0o700});
  const image=Buffer.from(row.image_base64,'base64');delete row.image_base64;
  if(!image.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))throw new Fault('CAPTURE_FORMAT_INVALID');
  const imagePath=path.join(folder,'window.png');
  fs.writeFileSync(imagePath,image,{flag:'wx',mode:0o600});
  const capture={capture_id:id,image_path:imagePath,image_sha256:crypto.createHash('sha256').update(image).digest('hex'),...row};
  fs.writeFileSync(path.join(folder,'manifest.json'),JSON.stringify(capture,null,2),{flag:'wx',mode:0o600});
  captures.push(id);return capture;
 });
 const reviewRequired=result.results.some(x=>x.review_required);
 return {...result,status:result.ok&&reviewRequired?'review_required':result.status,capture_ids:captures,review_required:reviewRequired};
}
function money(value) {
 if(typeof value!=='string'||!/^\d+(\.\d{1,4})?$/.test(value))throw new Fault('REVIEW_AMOUNT_INVALID');
 const [a,b='']=value.split('.');return BigInt(a)*10000n+BigInt(b.padEnd(4,'0'));
}
export function validateReview(manifest,review) {
 if(manifest.source!=='window_image'||!manifest.funds)throw new Fault('HOLDINGS_CAPTURE_REQUIRED');
 if(review.capture_id!==manifest.capture_id || review.image_sha256!==manifest.image_sha256)throw new Fault('EVIDENCE_MISMATCH');
 if(review.complete!==true || review.all_rows_visible!==true)throw new Fault('HOLDINGS_INCOMPLETE');
 if(!Array.isArray(review.rows))throw new Fault('REVIEW_ROWS_REQUIRED');
 const seen=new Set();let total=0n;
 for(const row of review.rows) {
  if(typeof row.code!=='string'||!/^\d{6}$/.test(row.code)||seen.has(row.code))throw new Fault('SECURITY_CODE_INVALID_OR_DUPLICATED');
  seen.add(row.code);
  if(typeof row.name!=='string'||!row.name.trim())throw new Fault('SECURITY_NAME_REQUIRED');
  if(![row.quantity,row.available].every(x=>typeof x==='string'&&/^\d+$/.test(x))||BigInt(row.available)>BigInt(row.quantity))throw new Fault('POSITION_QUANTITY_INVALID');
  total+=money(row.market_value);
 }
 const warnings=[];
 if(total!==money(manifest.funds['股票市值']))warnings.push('DISPLAYED_STOCK_VALUE_MISMATCH');
 if(total+money(manifest.funds['资金余额'])!==money(manifest.funds['总资产']))warnings.push('ASSET_RECONCILIATION_MISMATCH');
 return {ok:warnings.length===0,status:warnings.length?'review_inconsistent':'reviewed',error:warnings.length?'RECONCILIATION_FAILED':null,
  account_id:manifest.account_id,current_account:manifest.current_account,capture_id:manifest.capture_id,
  captured_at:manifest.captured_at,source:'codex_visual_review',freshness:manifest.freshness,
  funds:manifest.funds,positions:review.rows,row_count:review.rows.length,warnings,
  clipboard_unchanged:manifest.clipboard_unchanged,complete:true};
}
export function reviewCapture(id,file) {
 if(!/^[a-f0-9-]{36}$/.test(id||''))throw new Fault('CAPTURE_ID_INVALID');
 const folder=path.join(home(),'captures',id);
 const manifest=JSON.parse(fs.readFileSync(path.join(folder,'manifest.json'),'utf8'));
 const image=fs.readFileSync(path.join(folder,'window.png'));
 if(crypto.createHash('sha256').update(image).digest('hex')!==manifest.image_sha256)throw new Fault('EVIDENCE_CHANGED');
 const result=validateReview(manifest,JSON.parse(fs.readFileSync(file,'utf8')));
 const output=path.join(folder,'review-'+crypto.randomUUID()+'.json');
 fs.writeFileSync(output,JSON.stringify(result,null,2),{flag:'wx',mode:0o600});
 return {...result,review_path:output};
}
