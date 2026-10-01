import fs from 'node:fs';
import { Fault } from './common.mjs';

export function validateBatchFile(file) {
 let data;
 try { data=JSON.parse(fs.readFileSync(file,'utf8')); }
 catch { throw new Fault('BATCH_FILE_INVALID'); }
 if(!data || Array.isArray(data) || Object.keys(data).length!==1 || !Array.isArray(data.orders)
    || data.orders.length<1 || data.orders.length>10)throw new Fault('BATCH_FILE_INVALID');
 const seen=new Set();
 const orders=data.orders.map(row=>{
  if(!row || Array.isArray(row) || Object.keys(row).sort().join(',')!=='code,price,quantity,side')throw new Fault('BATCH_ORDER_INVALID');
  if(!['buy','sell'].includes(row.side) || typeof row.code!=='string' || !/^\d{6}$/.test(row.code)
     || typeof row.price!=='string' || !/^\d{1,6}(\.\d{1,3})?$/.test(row.price)
     || Number(row.price)<=0 || typeof row.quantity!=='string' || !/^[1-9]\d{0,8}$/.test(row.quantity))throw new Fault('BATCH_ORDER_INVALID');
  if(seen.has(row.code))throw new Fault('BATCH_DUPLICATE_SECURITY');
  seen.add(row.code);
  return {side:row.side,code:row.code,price:row.price,quantity:row.quantity};
 });
 return {orders};
}
