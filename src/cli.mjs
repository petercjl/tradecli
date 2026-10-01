import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { root, pkg, run, Fault, config, createConfig, output, parse } from './common.mjs';
import { discover, runtime, invoke } from './transport.mjs';
import { saveCaptures, reviewCapture } from './visual.mjs';
import { validateBatchFile } from './batches.mjs';
import { planStrategyFile } from './strategy.mjs';
export const help = `tradecli — Codex THS account query and batch-order CLI
  version | capabilities | schema | doctor
  connections discover
  config init --transport parallels --vm <name-or-id> --exe <Windows-path> [--python <bootstrap-python>]
  runtime install [--wheelhouse <Windows-directory>] | runtime status
  accounts list
  accounts select --account <id>
  orders open --side buy|sell --account <id>
  orders inspect --side buy|sell --account <id>
  orders clear --side buy|sell --account <id> --yes
  orders quantity-mode --side buy|sell --account <id>
  orders prepare --side buy|sell --account <id> --code <six-digits> --price <decimal> --quantity <shares>
  orders submit-simulated --draft <id> --account <id>
  orders confirm-simulated --draft <id> --account <id>
  orders acknowledge --draft <id> --account <id>
  orders result --draft <id>
  orders ledger --account <id>
  batches validate --input <orders.json>
  batches validate-default --input <orders.json>
  batches validate-market --input <orders.json>
  batches plan-default --strategy <strategy.json> --review <review.json> [--account <id>]
  batches plan-market --strategy <strategy.json> --review <review.json> [--account <id>]
  batches prepare --input <orders.json> --account <id>
  batches prepare-default --input <orders.json> --account <id>
  batches prepare-real-default --input <orders.json> --account <id>
  batches prepare-market --input <orders.json> --account <id>
  batches prepare-real-market --input <orders.json> --account <id>
  batches run-simulated --batch <id> --account <id> --digest <sha256> --yes
  batches run-real --batch <id> --account <id> --digest <sha256> --yes
  batches status --batch <id>
  funds get [--account <id>]
  positions list [--account <id>]
  positions review --capture <id> --input <review.json>
  snapshots create --accounts <id,id>
  operations status|resume <id>
  operations abandon <id> --yes
  skill source|status|install|update [--agent codex]
  update check | update install --yes
All commands return JSON. --json is accepted. Read errors exit 2.
Config is created once in TRADECLI_HOME (default ~/.tradecli).
Funds/positions require the THS funds/holdings page. Positions returns fresh images for Codex review; it never copies or exports the table.
Pending operations must be resumed or explicitly abandoned before another query.
Real-account submission is available through account-bound, confirmed market or default-price batches.
`;
export function skill(action,agent='codex') {
 if(agent!=='codex') throw new Fault('AGENT_UNSUPPORTED',{supported:['codex']});
 const source=path.join(root,'skills/tradecli');
 const target=path.join(process.env.CODEX_HOME || path.join(os.homedir(),'.codex'),'skills/tradecli');
 let stat; try {stat=fs.lstatSync(target);} catch(e){if(e.code!=='ENOENT')throw e;}
 const installed=Boolean(stat?.isSymbolicLink() && fs.realpathSync(target)===fs.realpathSync(source));
 if(action==='source') return {source};
 if(action==='status') return {source,target,installed};
 if(!['install','update'].includes(action))throw new Fault('COMMAND_UNSUPPORTED');
 if(stat && !installed) throw new Fault('SKILL_TARGET_EXISTS',{target});
 if(!stat) {fs.mkdirSync(path.dirname(target),{recursive:true});fs.symlinkSync(source,target,process.platform==='win32'?'junction':'dir');}
 return {source,target,installed:true};
}
const options={
 'version':[], 'capabilities':[], 'schema':[], 'doctor':[],
 'connections discover':[], 'config init':['transport','vm','exe','python','shared-home'],
 'runtime install':['wheelhouse'], 'runtime status':[], 'accounts list':[], 'accounts select':['account'],
 'positions review':['capture','input'],
 'orders open':['side','account'], 'orders prepare':['side','account','code','price','quantity'],
 'orders inspect':['side','account'],
 'orders clear':['side','account','yes'], 'orders quantity-mode':['side','account'],
 'orders submit-simulated':['draft','account'], 'orders result':['draft'],
 'orders confirm-simulated':['draft','account'], 'orders acknowledge':['draft','account'],
 'orders ledger':['account'],
 'batches validate':['input'], 'batches validate-default':['input'], 'batches validate-market':['input'],
 'batches plan-default':['strategy','review','account'], 'batches plan-market':['strategy','review','account'],
 'batches prepare':['input','account'], 'batches prepare-default':['input','account'], 'batches prepare-real-default':['input','account'],
 'batches prepare-market':['input','account'], 'batches prepare-real-market':['input','account'],
 'batches run-simulated':['batch','account','digest','yes'], 'batches run-real':['batch','account','digest','yes'], 'batches status':['batch'],
 'funds get':['account'], 'positions list':['account'], 'snapshots create':['accounts'],
 'operations status':[], 'operations resume':[], 'operations abandon':['yes'],
 'skill source':['agent'], 'skill status':['agent'], 'skill install':['agent'], 'skill update':['agent'],
 'update check':[], 'update install':['yes']
};
export function execute(argv) {
 const {args,flags}=parse(argv);
 if(flags.help || !args.length && !flags.version) return {ok:true,help};
 if(flags.version) return {ok:true,name:pkg.name,version:pkg.version};
 const key=options[args[0]] ? args[0] : args.slice(0,2).join(' ');
 if(!(key in options)) throw new Fault('COMMAND_UNSUPPORTED',{help:'tradecli --help'});
 const expected=key.split(' ').length+(args[0]==='operations'?1:0);
 if(args.length!==expected)throw new Fault('ARGUMENT_INVALID');
 for(const keyFlag of Object.keys(flags)) if(!['json',...options[key]].includes(keyFlag))throw new Fault('OPTION_UNSUPPORTED',{option:keyFlag});
 if(key==='version')return {ok:true,name:pkg.name,version:pkg.version};
 if(key==='capabilities')return {ok:true,...JSON.parse(fs.readFileSync(path.join(root,'capabilities.json'),'utf8'))};
 if(key==='schema')return {ok:true,protocol:1,result:{required:['ok','schemaVersion','version'],optional:['operation_id','batch_id','digest','orders','status','error','results','restoration']},error:{exitCode:2,code:'error.code (CLI) or error (worker)',details:'non-secret diagnostics'},amounts:'decimal strings',securityCodes:'six-digit strings',freshness:'client display only',commands:options};
 if(key==='connections discover')return {ok:true,...discover()};
 if(key==='config init') {
  const transport=flags.transport || (process.platform==='darwin'?'parallels':'windows');
  if(!['parallels','windows'].includes(transport) || !flags.exe || transport==='parallels'&&!flags.vm)throw new Fault('CONFIG_ARGUMENTS_REQUIRED');
  return {ok:true,...createConfig({transport,vm:flags.vm,exe:flags.exe,bootstrapPython:flags.python,sharedHome:flags['shared-home']})};
 }
 if(args[0]==='skill')return {ok:true,...skill(args[1],flags.agent)};
 if(key==='positions review') {
  if(!flags.capture||!flags.input)throw new Fault('REVIEW_ARGUMENTS_REQUIRED');
  return reviewCapture(flags.capture,flags.input);
 }
 if(['batches validate','batches validate-default','batches validate-market'].includes(key)) {
  if(!flags.input)throw new Fault('BATCH_INPUT_REQUIRED');
  const mode=key==='batches validate'?'limit':key==='batches validate-market'?'market':'default';
  const plan=validateBatchFile(flags.input,mode==='limit'?'limit':'default');
  return {ok:true,status:'validated',price_mode:mode,orders:plan.orders,count:plan.orders.length};
 }
 if(key==='batches plan-default'||key==='batches plan-market') {
  if(!flags.strategy||!flags.review)throw new Fault('STRATEGY_INPUT_REQUIRED');
  if(flags.account&&!/^a_[a-f0-9]{16}$/.test(flags.account))throw new Fault('ACCOUNT_ID_INVALID');
  return planStrategyFile(flags.review,flags.strategy,flags.account,key==='batches plan-market'?'market':'client_default');
 }
 if(args[0]==='update') {
  const latest=JSON.parse(run('npm',['view',pkg.name,'version','--json']));
  if(!/^\d+\.\d+\.\d+$/.test(latest))throw new Fault('REGISTRY_VERSION_INVALID');
  if(args[1]==='check')return {ok:true,current:pkg.version,latest,updateAvailable:latest!==pkg.version};
  if(!flags.yes)throw new Fault('CONFIRMATION_REQUIRED');
  run('npm',['install','--global',`${pkg.name}@${latest}`],{timeout:300000});
  return {ok:true,installed:latest,verify:'tradecli version'};
 }
 const c=config();
 if(args[0]==='batches') {
  if(args[1]==='status') {
   if(!/^[a-f0-9-]{36}$/.test(flags.batch||''))throw new Fault('BATCH_ID_REQUIRED');
   return invoke(c,{action:'batches.status',batch:flags.batch});
  }
  if(!/^a_[a-f0-9]{16}$/.test(flags.account||''))throw new Fault('ACCOUNT_REQUIRED');
  if(['prepare','prepare-default','prepare-real-default','prepare-market','prepare-real-market'].includes(args[1])) {
   if(!flags.input)throw new Fault('BATCH_INPUT_REQUIRED');
   const plan=validateBatchFile(flags.input,args[1]==='prepare'?'limit':'default');
   return invoke(c,{action:`batches.${args[1]}`,account:flags.account,orders:plan.orders});
  }
  if(!/^[a-f0-9-]{36}$/.test(flags.batch||'')|| !/^[a-f0-9]{64}$/.test(flags.digest||''))throw new Fault('BATCH_RUN_ARGUMENTS_INVALID');
  if(!flags.yes)throw new Fault('CONFIRMATION_REQUIRED');
  return invoke(c,{action:`batches.${args[1]}`,batch:flags.batch,account:flags.account,digest:flags.digest,confirmed:true},600000);
 }
 if(args[0]==='orders') {
  if(args[1]==='ledger') {
   if(!/^a_[a-f0-9]{16}$/.test(flags.account||''))throw new Fault('ACCOUNT_REQUIRED');
   return saveCaptures(invoke(c,{action:'orders.ledger',account:flags.account}));
  }
  if(['submit-simulated','confirm-simulated','acknowledge','result'].includes(args[1])) {
   if(!/^[a-f0-9-]{36}$/.test(flags.draft||''))throw new Fault('ORDER_DRAFT_REQUIRED');
   if(args[1]!=='result'&&!/^a_[a-f0-9]{16}$/.test(flags.account||''))throw new Fault('ACCOUNT_REQUIRED');
   return invoke(c,{action:`orders.${args[1]}`,...flags});
  }
  if(!['buy','sell'].includes(flags.side)||!/^a_[a-f0-9]{16}$/.test(flags.account||''))throw new Fault('ORDER_ARGUMENTS_REQUIRED');
  if(args[1]==='prepare' && (!/^\d{6}$/.test(flags.code||'')||!/^\d{1,6}(\.\d{1,3})?$/.test(flags.price||'')||Number(flags.price)<=0||! /^[1-9]\d{0,8}$/.test(flags.quantity||'')))throw new Fault('ORDER_ARGUMENTS_INVALID');
  return saveCaptures(invoke(c,{action:`orders.${args[1]}`,...flags}));
 }
 if(args[0]==='runtime')return {ok:true,...runtime(c,args[1]==='install',flags.wheelhouse)};
 if(key==='doctor')return {runtime:runtime(c),...invoke(c,{action:'doctor'})};
 if(args[0]==='operations')return invoke(c,{action:`operations.${args[1]}`,id:args[2],yes:flags.yes});
 if(key==='snapshots create') {
  const accounts=flags.accounts?.split(',');
  if(!accounts?.length || accounts.some(x=>!/^a_[a-f0-9]{16}$/.test(x)))throw new Fault('ACCOUNT_IDS_REQUIRED');
  return saveCaptures(invoke(c,{action:'snapshot',accounts}));
 }
 if(flags.account && !/^a_[a-f0-9]{16}$/.test(flags.account))throw new Fault('ACCOUNT_ID_INVALID');
 return saveCaptures(invoke(c,{action:key==='accounts select'?'accounts.select':args[0],account:flags.account}));
}
export async function main() {
 try {const value=execute(process.argv.slice(2));output(value);if(!value.ok)process.exitCode=2;}
 catch(e){output({ok:false,error:{code:e.code || 'INTERNAL_ERROR',...e.details}});process.exitCode=2;}
}
