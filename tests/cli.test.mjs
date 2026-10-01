import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {root} from '../src/common.mjs';
import {quote} from '../src/transport.mjs';
function cli(args,env={}) {const r=spawnSync(process.execPath,[path.join(root,'bin/tradecli.mjs'),...args],{encoding:'utf8',env:{...process.env,...env}});return {code:r.status,data:JSON.parse(r.stdout)};}
test('unknown commands and options fail before desktop access',()=>{
 for(const args of [['buy'],['funds','get','--accoun','abc'],['positions','list','--account','invalid'],['accounts','list','extra']])assert.equal(cli(args).code,2);
});
test('PowerShell quoting treats apostrophes as literals',()=>assert.equal(quote("a'b;$x"),"'a''b;$x'"));
test('isolated config is private and never overwritten',()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'tradecli-test-'));const env={TRADECLI_HOME:temp};
 try {
  const args=['config','init','--transport','parallels','--vm','Example','--exe','C:\\Example\\xiadan.exe'];
  assert.equal(cli(args,env).code,0);const before=fs.readFileSync(path.join(temp,'config.json'),'utf8');
  assert.equal(cli(args,env).data.error.code,'CONFIG_EXISTS');assert.equal(fs.readFileSync(path.join(temp,'config.json'),'utf8'),before);
  if(process.platform!=='win32')assert.equal(fs.statSync(path.join(temp,'config.json')).mode&0o777,0o600);
 } finally{fs.rmSync(temp,{recursive:true,force:true});}
});
test('Codex skill installation is idempotent and preserves user files',()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'tradecli-skill-'));const env={CODEX_HOME:temp};
 try {
  assert.equal(cli(['skill','install'],env).code,0);assert.equal(cli(['skill','update'],env).code,0);
  assert.equal(cli(['skill','status'],env).data.installed,true);
  assert.equal(cli(['skill','install','--agent','sealseek'],env).data.error.code,'AGENT_UNSUPPORTED');
  fs.unlinkSync(path.join(temp,'skills/tradecli'));fs.mkdirSync(path.join(temp,'skills/tradecli'));
  assert.equal(cli(['skill','install'],env).data.error.code,'SKILL_TARGET_EXISTS');
 } finally{fs.rmSync(temp,{recursive:true,force:true});}
});
test('machine capabilities declare read-only boundary',()=>{const c=cli(['capabilities']).data;assert.equal(c.permission,'read-only');assert.equal(c.agent,'codex');});
