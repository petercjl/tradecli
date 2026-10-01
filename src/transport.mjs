import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import { root, run, Fault } from './common.mjs';
export const quote = s => "'" + String(s).replaceAll("'", "''") + "'";
export function powershell(c, script, timeout=60000) {
 const prefix = "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); ";
 const encoded=Buffer.from(prefix+script,'utf16le').toString('base64');
 if(c.transport==='parallels') return run(c.prlctl || 'prlctl',['exec',c.vm,'--current-user','powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],{timeout});
 if(c.transport==='windows' && process.platform==='win32') return run('powershell.exe',['-NoProfile','-NonInteractive','-EncodedCommand',encoded],{timeout});
 throw new Fault('TRANSPORT_UNSUPPORTED');
}
export function discover() {
 if(process.platform==='darwin') return {transport:'parallels',machines:JSON.parse(run('prlctl',['list','-a','-j']))};
 if(process.platform==='win32') return {transport:'windows',status:'implemented_not_live_tested'};
 throw new Fault('PLATFORM_UNSUPPORTED');
}
export function runtime(c, install=false, wheelhouse) {
 const req=fs.readFileSync(path.join(root,'worker/requirements.txt'),'utf8').trim().split(/\r?\n/);
 const script=`$base=Join-Path $env:LOCALAPPDATA 'tradecli'; $venv=Join-Path $base 'venv'; $python=Join-Path $venv 'Scripts/python.exe';
 ${install ? `if (!(Test-Path -LiteralPath $python)) { if(Test-Path -LiteralPath $venv) { throw 'INCOMPLETE_RUNTIME' }; & ${quote(c.bootstrapPython || 'python')} -m venv $venv; if($LASTEXITCODE -ne 0){throw 'VENV_FAILED'} }; & $python -m pip install ${wheelhouse ? '--no-index --find-links '+quote(wheelhouse) : '--index-url https://pypi.org/simple'} ${req.map(quote).join(' ')}; if($LASTEXITCODE -ne 0){throw 'DEPENDENCIES_FAILED'}; & $python -m pip check; if($LASTEXITCODE -ne 0){throw 'DEPENDENCIES_INVALID'};` : ''}
 if(!(Test-Path -LiteralPath $python)){throw 'RUNTIME_REQUIRED'};
 & $python -c ${quote("import json,sys,importlib.metadata as m; print(json.dumps({'python':sys.version.split()[0],'pywinauto':m.version('pywinauto'),'pywin32':m.version('pywin32')}))")}; if($LASTEXITCODE -ne 0){throw 'RUNTIME_INVALID'}`;
 const out=powershell(c,script,install?300000:60000);
 return JSON.parse(out.split(/\r?\n/).filter(x=>x.startsWith('{')).at(-1));
}
export function deploy(c) {
 const source=path.join(root,'worker/ths.py');
 const data=fs.readFileSync(source);
 const hash=crypto.createHash('sha256').update(data).digest('hex');
 let windowsSource=source;
 if(c.transport==='parallels') {
  const cache=path.join(os.homedir(),'.cache','tradecli','workers');
  fs.mkdirSync(cache,{recursive:true,mode:0o700});
  const local=path.join(cache,`${hash}.py`);
  if(fs.existsSync(local)) {
   if(crypto.createHash('sha256').update(fs.readFileSync(local)).digest('hex')!==hash)throw new Fault('WORKER_HASH_MISMATCH');
  } else fs.writeFileSync(local,data,{flag:'wx',mode:0o600});
  windowsSource=(c.sharedHome || '\\\\Mac\\Home')+'\\'+path.relative(os.homedir(),local).split(path.sep).join('\\');
 }
 const script=`$dir=Join-Path $env:LOCALAPPDATA 'tradecli/workers'; $dest=Join-Path $dir '${hash}.py';
 if(!(Test-Path -LiteralPath $dest)){[IO.Directory]::CreateDirectory($dir)|Out-Null; [IO.File]::Copy(${quote(windowsSource)},$dest,$false)};
 if((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLower() -ne '${hash}'){throw 'WORKER_HASH_MISMATCH'}; Write-Output 'ready'`;
 powershell(c,script);
 return hash;
}
export function invoke(c, request) {
 const hash=deploy(c);
 const encoded=Buffer.from(JSON.stringify({...request,exe:c.exe,protocol:1})).toString('base64');
 const out=powershell(c,`$python=Join-Path $env:LOCALAPPDATA 'tradecli/venv/Scripts/python.exe'; $worker=Join-Path $env:LOCALAPPDATA 'tradecli/workers/${hash}.py'; & $python $worker '${encoded}'; if($LASTEXITCODE -ne 0){throw 'WORKER_EXIT_FAILED'}`,120000);
 try { const result=JSON.parse(out); if(result.protocol!==1 || typeof result.ok!=='boolean') throw 0; return result; }
 catch {throw new Fault('WORKER_PROTOCOL_INVALID');}
}
