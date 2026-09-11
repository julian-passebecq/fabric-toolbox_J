import os,subprocess,sys,time,json
from pathlib import Path
root=Path('D:/PROJ/s01-qa-2fe35a13')
reports=Path('D:/PROJ/fabric-toolbox_J/projectmanagement/reports')
node=Path(os.environ['TEMP'])/'fabric-studio-node22/node-v22.22.0-win-x64'
env=os.environ.copy();env['PATH']=str(node)+';'+env['PATH']
python=root/'studio/backend/.venv/Scripts/python.exe'
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
lanes={
 'backend':[(root,[python,'-m','compileall','-q','studio/backend/app','studio/scripts']),
            (root,[python,'-m','pytest','-q','studio/backend/tests']),
            (root,['pwsh','-NoProfile','-File','studio/scripts/start-studio.ps1','-NoBrowser','-SkipInstall','-SmokeTest','-PythonPath',python,'-ApiPort','18767','-UiPort','15175'])],
 'frontend':[(root/'studio',[node/'npm.cmd','run','test','-w','frontend','--','--run']),
             (root/'studio',[node/'npm.cmd','run','build']),
             (root/'studio',[node/'npm.cmd','run','test:e2e','-w','frontend'])]
}
lane=sys.argv[1]
with (reports/f'S01-clean-{lane}.txt').open('w',encoding='utf-8') as log:
 log.write(f'Candidate: {revision}\nClean checkout: {root}\n')
 for cwd,argv in lanes[lane]:
  args=[str(x) for x in argv]
  started=time.monotonic()
  result=subprocess.run(args,cwd=cwd,env=env,text=True,encoding='utf-8',errors='replace',capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
  elapsed=round(time.monotonic()-started,2)
  log.write(f'\nCWD: {cwd}\nCOMMAND: {json.dumps(args)}\nEXIT: {result.returncode}; SECONDS: {elapsed}\n'+result.stdout+result.stderr)
  log.flush()
  print(f'{lane}: {args[1:4]} exit={result.returncode} duration={elapsed}s',flush=True)
  if result.returncode:sys.exit(result.returncode)
