#!/usr/bin/env python3
"""Register and run every package accepted by the trusted collection importer."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
 p=argparse.ArgumentParser();p.add_argument('--audit',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 d=json.loads(a.audit.resolve(strict=True).read_text()); accepted=[x['descriptor'] for x in d['slots'] if x.get('registry_eligible') and x.get('descriptor')]
 if not accepted: raise SystemExit('trusted importer accepted no packages')
 out=a.output.resolve();out.parent.mkdir(parents=True,exist_ok=True)
 cmd=['c++','-std=c++17','-O2','-I'+str(ROOT/'include'),'-I'+str(ROOT/'src'),str(ROOT/'tools/audio_validation/factory_package_registry_smoke.cpp'),str(ROOT/'src/es5510_factory_runtime.cpp'),str(ROOT/'src/es5510.cpp'),'-o',str(out)]
 subprocess.run(cmd,cwd=ROOT,check=True)
 results=[]
 for x in accepted:
  args=[str(out),str(x['slot']),x['factory_name'],str(x['active_program_words']),x['program_sha256'],x['run_checkpoint_path'],x['run_checkpoint_sha256'],str(x['factory_reference_rate_hz']),x['firmware_event_schedule_path']]
  r=subprocess.run(args,cwd=ROOT,text=True,capture_output=True)
  if r.returncode: raise SystemExit(f"slot {x['slot']} registry/runtime smoke failed: {r.stderr.strip()}")
  results.append(r.stdout.strip())
 print('\n'.join(results));return 0
if __name__=='__main__':raise SystemExit(main())
