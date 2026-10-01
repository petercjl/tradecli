import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import { validateBatchFile } from '../src/batches.mjs';

test('batch input is exact, ordered and rejects ambiguous orders',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'tradecli-batch-'));
 const file=path.join(dir,'orders.json');
 const good={orders:[{side:'buy',code:'600001',price:'1.23',quantity:'100'},
                     {side:'sell',code:'600002',price:'2.10',quantity:'200'}]};
 try {
  fs.writeFileSync(file,JSON.stringify(good));
  assert.deepEqual(validateBatchFile(file).orders,good.orders);
  const defaultPlan={orders:[{side:'buy',code:'600001',quantity:'100'}]};
  fs.writeFileSync(file,JSON.stringify(defaultPlan));
  assert.deepEqual(validateBatchFile(file,'default').orders,defaultPlan.orders);
  const market=spawnSync(process.execPath,['bin/tradecli.mjs','batches','validate-market','--input',file],
                         {cwd:path.resolve(import.meta.dirname,'..'),encoding:'utf8'});
  assert.equal(market.status,0);
  assert.deepEqual(JSON.parse(market.stdout).orders,defaultPlan.orders);
  assert.equal(JSON.parse(market.stdout).price_mode,'market');
  assert.throws(()=>validateBatchFile(file));
  for(const bad of [
   {...good,account:'unexpected'},
   {orders:[good.orders[0],good.orders[0]]},
   {orders:[{...good.orders[0],quantity:100}]},
   {orders:[{...good.orders[0],price:'NaN'}]},
   {orders:Array.from({length:16},(_,i)=>({...good.orders[0],code:String(600000+i)}))}
  ]) {
   fs.writeFileSync(file,JSON.stringify(bad));
   assert.throws(()=>validateBatchFile(file));
  }
  const repeatedSells={orders:[{side:'sell',code:'300359',quantity:'100'},
                               {side:'sell',code:'300359',quantity:'100'}]};
  fs.writeFileSync(file,JSON.stringify(repeatedSells));
  assert.equal(validateBatchFile(file,'default').orders.length,2);
 } finally { fs.rmSync(dir,{recursive:true,force:true}); }
});
