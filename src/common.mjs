import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
export const home = () => process.env.TRADECLI_HOME || path.join(os.homedir(), '.tradecli');
export class Fault extends Error { constructor(code, details = {}) { super(code); this.code = code; this.details = details; } }
export function run(command, args, { timeout = 60000, ...opts } = {}) {
 const r = spawnSync(command, args, { encoding: 'utf8', timeout, killSignal: 'SIGKILL', maxBuffer: 16*1024*1024, ...opts });
 if (r.error || r.status !== 0) throw new Fault(r.error?.code === 'ETIMEDOUT' ? 'TRANSPORT_TIMEOUT' : 'COMMAND_FAILED', { command: path.basename(command), exitCode: r.status });
 return r.stdout.trim();
}
export function privateDir(dir) { fs.mkdirSync(dir, {recursive:true,mode:0o700}); }
export function config() {
 try { return JSON.parse(fs.readFileSync(path.join(home(),'config.json'),'utf8')); }
 catch(e) { if(e.code==='ENOENT') throw new Fault('CONFIG_REQUIRED'); throw new Fault('CONFIG_INVALID'); }
}
export function createConfig(value) {
 privateDir(home()); const target = path.join(home(),'config.json');
 if(fs.existsSync(target)) throw new Fault('CONFIG_EXISTS', {path:target});
 fs.writeFileSync(target, JSON.stringify(value,null,2)+'\n', {flag:'wx',mode:0o600});
 return {path:target};
}
export function output(value) { console.log(JSON.stringify({schemaVersion:1,version:pkg.version,...value},null,2)); }
export function parse(argv) {
 const args=[], flags={};
 for(let i=0;i<argv.length;i++) {
  const a=argv[i];
  if(!a.startsWith('--')) args.push(a);
  else { const key=a.slice(2); if(key in flags) throw new Fault('DUPLICATE_OPTION');
   flags[key]=['json','yes','help','version'].includes(key) ? true : argv[++i];
   if(flags[key]===undefined || (typeof flags[key]==='string' && flags[key].startsWith('--'))) throw new Fault('OPTION_VALUE_REQUIRED',{option:key});
  }
 }
 return {args,flags};
}
