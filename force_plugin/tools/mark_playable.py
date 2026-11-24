#!/usr/bin/env python3
"""Create a release marker from a full-collection native DSP integration report."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path
SCHEMA="trollfx-force-dsp-integration-report-v1"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def verify_candidate(package):
 sums=package/'SHA256SUMS'
 if not sums.is_file(): raise SystemExit('refusing marker: candidate SHA256SUMS missing')
 expected={}
 for line in sums.read_text().splitlines():
  parts=line.split('  ',1)
  if len(parts)!=2: raise SystemExit('refusing marker: malformed checksum manifest')
  rel=Path(parts[1])
  if rel.is_absolute() or '..' in rel.parts or parts[1]=='SHA256SUMS': raise SystemExit('refusing marker: unsafe checksum path')
  expected[rel.as_posix()]=parts[0]
 actual={f.relative_to(package).as_posix() for f in package.rglob('*') if f.is_file() and f.name!='SHA256SUMS'}
 if actual!=set(expected): raise SystemExit('refusing marker: candidate files differ from checksum inventory')
 for name,h in expected.items():
  if sha(package/name)!=h: raise SystemExit(f'refusing marker: checksum mismatch for {name}')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
 package=a.package.resolve(strict=True);report_path=a.report.resolve(strict=True);verify_candidate(package);r=json.loads(report_path.read_text())
 if r.get('schema')!=SCHEMA or r.get('status')!='PASS': raise SystemExit('refusing marker: report schema/status is not a passing DSP integration result')
 manifest_path=package/'release-manifest.json';m=json.loads(manifest_path.read_text());plugin=json.loads((package/'plugin.json').read_text());rel=Path(plugin['file32'])
 if m.get('release_state')!='candidate' or m.get('sdk_validation',{}).get('result')!='PASS': raise SystemExit('refusing marker: package is not an SDK-validated candidate')
 if rel.is_absolute() or '..' in rel.parts: raise SystemExit('refusing marker: unsafe ARM32 manifest path')
 binary=package/rel;binary_hash=sha(binary)
 if r.get('arm32_binary_sha256')!=binary_hash: raise SystemExit('refusing marker: report is not bound to this ARMv7 binary')
 if r.get('mock_backend') is not False: raise SystemExit('refusing marker: report must confirm mock_backend=false')
 if int(r.get('processed_dsp_frames',0))<1 or int(r.get('non_silent_output_frames',0))<1: raise SystemExit('refusing marker: no numerical DSP output evidence')
 slots=r.get('verified_slots')
 if not isinstance(slots,list) or any(type(v) is not int for v in slots) or slots!=list(range(1,51)): raise SystemExit('refusing marker: all 50 slots must pass processing checks')
 slot_results=r.get('slot_results')
 if not isinstance(slot_results,list) or [x.get('slot') for x in slot_results if isinstance(x,dict)]!=list(range(1,51)): raise SystemExit('refusing marker: per-slot playback results are incomplete')
 if any(x.get('status')!='PASS' or int(x.get('frames',0))<1 or float(x.get('rms_left',0))<=0 or float(x.get('rms_right',0))<=0 for x in slot_results): raise SystemExit('refusing marker: a slot lacks non-silent stereo playback evidence')
 if int(r.get('callback_allocations',-1))!=0: raise SystemExit('refusing marker: callback allocation check did not pass')
 host=r.get('sdk_host_simulator',{})
 if not isinstance(host,dict) or host.get('result')!='PASS' or not re.fullmatch(r'[0-9a-f]{64}',str(host.get('wav_sha256',''))): raise SystemExit('refusing marker: SDK host simulator evidence is missing')
 required={'factory_processing','effect_switching','no_mock_fallback','initialization_validation','stereo_routing'}
 passed=r.get('passed_tests')
 if not isinstance(passed,list) or not required.issubset(set(passed)): raise SystemExit('refusing marker: required test results are missing')
 for key in ('engine_id','test_command','input_sha256','output_sha256'):
  if not isinstance(r.get(key),str) or not r[key].strip(): raise SystemExit(f'refusing marker: missing {key}')
 for key in ('input_sha256','output_sha256'):
  if not re.fullmatch(r'[0-9a-f]{64}',r[key]): raise SystemExit(f'refusing marker: malformed {key}')
 marker={'schema':'trollfx-playable-release-marker-v1','status':'playable','version':plugin['version'],'arm32_binary_sha256':binary_hash,'verification_report_sha256':sha(report_path),'engine_id':r['engine_id'],'verified_slots':r['verified_slots'],'passed_tests':sorted(required),'mock_backend':False}
 # This redacted report contains hashes and numerical slot metrics, not local
 # paths or proprietary payloads. Keep it next to the release marker so users
 # can inspect exactly which binary and per-slot playback results were gated.
 (package/'factory-playback-status.json').write_text(json.dumps(r,indent=2)+'\n')
 (package/'INTEGRATION_STATUS').write_text(json.dumps(marker,indent=2)+'\n')
 (package/'INSTALL.txt').write_text('PLAYABLE RELEASE: all 50 effect slots passed the recorded non-mock DSP integration gate.\nInstall only by explicitly invoking the repository opt-in installer. Device installation/restart has not been performed by the build.\nSee the release-manifest.json and INTEGRATION_STATUS for build and verification hashes.\n')
 (package/'README.txt').write_text(f'TROLLfx ASR-10 FX Collection {plugin["version"]}\nRelease gate: PASS. Verified slots: 50. DSP engine: {r["engine_id"]}.\nThis is a playable software release candidate. Physical Akai Force device validation remains separate.\n')
 m.update({'release_state':'playable','playable':True,'playable_marker':'INTEGRATION_STATUS','verified_slots':r['verified_slots'],'verification_report_sha256':marker['verification_report_sha256']});manifest_path.write_text(json.dumps(m,indent=2)+'\n')
 sums=[]
 for f in sorted(package.rglob('*')):
  if f.is_symlink(): raise SystemExit(f'package symlink refused: {f}')
  if f.is_file() and f.name!='SHA256SUMS': sums.append(f"{sha(f)}  {f.relative_to(package).as_posix()}")
 (package/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
 dist=package.parent
 zip_path=dist/f'asr10-fx-collection-{plugin["version"]}-playable.zip'
 with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for f in sorted(package.rglob('*')):
   if f.is_file(): z.write(f,package.name+'/'+f.relative_to(package).as_posix())
 (zip_path.with_suffix(zip_path.suffix+'.sha256')).write_text(f'{sha(zip_path)}  {zip_path.name}\n')
 print('Playable marker written; generated playable archive. DSP report itself was not copied into the release package.')
if __name__=='__main__':main()
