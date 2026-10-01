import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { root, pkg, run, Fault, config, createConfig, output, parse } from './common.mjs';
import { discover, runtime, invoke } from './transport.mjs';
export const help = `tradecli — Codex THS read-only CLI
  version | capabilities | schema | doctor
  connections discover
  config init --transport parallels --vm <name-or-id> --exe <Windows-path> [--python <bootstrap-python>]
  runtime install [--wheelhouse <Windows-directory>] | runtime status
  accounts list
  funds get [--account <id>]
  positions list [--account <id>]
  snapshots create --accounts <id,id>
  operations status|resume <id>
  operations abandon <id> --yes
  skill source|status|install|update [--agent codex]
  update check | update install --yes
All commands return JSON. --json is accepted. Read errors exit 2.
Config is created once in TRADECLI_HOME (default ~/.tradecli).
Funds/positions require the THS funds/holdings page. Positions changes Windows clipboard.
Pending operations must be resumed or explicitly abandoned before another query.
No buy, sell, cancel or login commands are provided in this version.
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
 'runtime install':['wheelhouse'], 'runtime status':[], 'accounts list':[],
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
 if(key==='schema')return {ok:true,protocol:1,result:{required:['ok','schemaVersion','version'],optional:['operation_id','status','error','results','restoration']},error:{exitCode:2,code:'error.code (CLI) or error (worker)',details:'non-secret diagnostics'},amounts:'decimal strings',securityCodes:'six-digit strings',freshness:'client display only',commands:options};
 if(key==='connections discover')return {ok:true,...discover()};
 if(key==='config init') {
  const transport=flags.transport || (process.platform==='darwin'?'parallels':'windows');
  if(!['parallels','windows'].includes(transport) || !flags.exe || transport==='parallels'&&!flags.vm)throw new Fault('CONFIG_ARGUMENTS_REQUIRED');
  return {ok:true,...createConfig({transport,vm:flags.vm,exe:flags.exe,bootstrapPython:flags.python,sharedHome:flags['shared-home']})};
 }
 if(args[0]==='skill')return {ok:true,...skill(args[1],flags.agent)};
 if(args[0]==='update') {
  const latest=JSON.parse(run('npm',['view',pkg.name,'version','--json']));
  if(!/^\d+\.\d+\.\d+$/.test(latest))throw new Fault('REGISTRY_VERSION_INVALID');
  if(args[1]==='check')return {ok:true,current:pkg.version,latest,updateAvailable:latest!==pkg.version};
  if(!flags.yes)throw new Fault('CONFIRMATION_REQUIRED');
  run('npm',['install','--global',`${pkg.name}@${latest}`],{timeout:300000});
  return {ok:true,installed:latest,verify:'tradecli version'};
 }
 const c=config();
 if(args[0]==='runtime')return {ok:true,...runtime(c,args[1]==='install',flags.wheelhouse)};
 if(key==='doctor')return {runtime:runtime(c),...invoke(c,{action:'doctor'})};
 if(args[0]==='operations')return invoke(c,{action:`operations.${args[1]}`,id:args[2],yes:flags.yes});
 if(key==='snapshots create') {
  const accounts=flags.accounts?.split(',');
  if(!accounts?.length || accounts.some(x=>!/^a_[a-f0-9]{16}$/.test(x)))throw new Fault('ACCOUNT_IDS_REQUIRED');
  return invoke(c,{action:'snapshot',accounts});
 }
 if(flags.account && !/^a_[a-f0-9]{16}$/.test(flags.account))throw new Fault('ACCOUNT_ID_INVALID');
 return invoke(c,{action:args[0],account:flags.account});
}
export async function main() {
 try {const value=execute(process.argv.slice(2));output(value);if(!value.ok)process.exitCode=2;}
 catch(e){output({ok:false,error:{code:e.code || 'INTERNAL_ERROR',...e.details}});process.exitCode=2;}
}
