#!/usr/bin/env python3
"""Opt-in installer for an explicitly selected, checksummed playable Force package."""
import argparse, datetime, hashlib, json, os, shutil, sys, tempfile
from pathlib import Path
FOLDER='TROLLfx - VST - ASR10 FX Collection'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(folder:Path):
 if folder.is_symlink() or not folder.is_dir(): raise ValueError('package must be a real directory')
 for f in folder.rglob('*'):
  if f.is_symlink(): raise ValueError(f'package symlink refused: {f}')
 sums=folder/'SHA256SUMS'
 if not sums.is_file(): raise ValueError('SHA256SUMS is missing')
 expected={}
 for line in sums.read_text().splitlines():
  if not line.strip(): continue
  parts=line.split('  ',1)
  if len(parts)!=2 or len(parts[0])!=64: raise ValueError('invalid SHA256SUMS entry')
  rel=Path(parts[1])
  if rel.is_absolute() or '..' in rel.parts or parts[1]=='SHA256SUMS': raise ValueError('unsafe checksum path')
  expected[rel.as_posix()]=parts[0]
 actual={p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
 if actual!=set(expected): raise ValueError('package file inventory differs from SHA256SUMS')
 for name,digest in expected.items():
  if sha(folder/name)!=digest: raise ValueError(f'checksum mismatch: {name}')
 m=json.loads((folder/'release-manifest.json').read_text()); plugin=json.loads((folder/'plugin.json').read_text())
 if not (folder/'INTEGRATION_STATUS').is_file(): raise ValueError('candidate has no DSP integration marker; only a verified playable release may be installed')
 marker=json.loads((folder/'INTEGRATION_STATUS').read_text())
 if m.get('release_state')!='playable' or m.get('playable') is not True: raise ValueError('release manifest is not playable')
 if marker.get('schema')!='trollfx-playable-release-marker-v1' or marker.get('status')!='playable': raise ValueError('playable integration marker is missing/invalid')
 rel=Path(plugin['file32'])
 if rel.is_absolute() or '..' in rel.parts: raise ValueError('unsafe plugin binary path')
 arm=folder/rel
 if marker.get('arm32_binary_sha256')!=sha(arm) or m.get('binaries',{}).get('arm32_sha256')!=sha(arm): raise ValueError('playable evidence is not bound to the packaged ARM32 binary')
 if marker.get('mock_backend') is not False or marker.get('verified_slots')!=list(range(1,51)): raise ValueError('playable marker lacks non-mock full-collection coverage')
 if plugin.get('name')!='ASR10 FX Collection' or plugin.get('manufacturer')!='TROLLfx': raise ValueError('plugin identity mismatch')
 if m.get('sdk_validation',{}).get('result')!='PASS': raise ValueError('SDK validation evidence missing')
 if not arm.is_file(): raise ValueError('ARM32 VST binary missing')
 return m
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('package',type=Path);ap.add_argument('plugins_root',type=Path);ap.add_argument('--replace',action='store_true',help='preserve existing package as rollback backup');a=ap.parse_args()
 package=a.package.resolve(strict=True);root=a.plugins_root.expanduser().absolute()
 verify(package)
 if root.is_symlink(): raise ValueError('plugins root may not be symlink')
 root.mkdir(parents=True,exist_ok=True);root=root.resolve(strict=True);target=root/FOLDER
 if target.resolve(strict=False)==package: raise ValueError('package and destination are identical')
 backup=None
 if target.exists():
  if not a.replace: raise ValueError('target exists; use --replace to retain it as a rollback copy')
  verify(target);stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');backup=root/f'.rollback-{FOLDER}-{stamp}'
  if backup.exists(): raise ValueError('backup name collision')
 temp_parent=Path(tempfile.mkdtemp(prefix='.trollfx-install-',dir=root))
 if backup: target.rename(backup);temp=temp_parent/FOLDER
 try:
  shutil.copytree(package,temp,symlinks=False);verify(temp);os.replace(temp,target)
 except Exception:
  shutil.rmtree(temp_parent,ignore_errors=True)
  if backup and backup.exists() and not target.exists(): backup.rename(target)
  raise
 shutil.rmtree(temp_parent,ignore_errors=True)
 print(f'Installed verified playable package {FOLDER} at {target}. Restart the host manually.')
 if backup: print(f'Previous package retained at {backup}')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,KeyError,json.JSONDecodeError) as e:print(f'install refused: {e}',file=sys.stderr);raise SystemExit(2)
