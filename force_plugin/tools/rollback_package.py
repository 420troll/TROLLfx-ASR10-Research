#!/usr/bin/env python3
"""Move the installed plugin aside and restore the latest install backup, if any."""
import argparse, datetime, json, sys
from pathlib import Path
FOLDER='TROLLfx - VST - ASR10 FX Collection'
def identity(p):
 try:
  d=json.loads((p/'plugin.json').read_text());return d.get('name')=='ASR10 FX Collection' and d.get('manufacturer')=='TROLLfx'
 except Exception:return False
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('plugins_root',type=Path);a=ap.parse_args();root=a.plugins_root.expanduser().absolute()
 if root.is_symlink() or not root.is_dir():raise ValueError('plugins root must be an existing real directory')
 root=root.resolve(strict=True);target=root/FOLDER
 if target.is_symlink() or not target.is_dir() or not identity(target):raise ValueError('installed plugin folder missing or identity mismatch')
 backups=sorted((p for p in root.glob(f'.rollback-{FOLDER}-*') if p.is_dir() and not p.is_symlink() and identity(p)),key=lambda p:p.name)
 stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');removed=root/f'.removed-{FOLDER}-{stamp}'
 if backups:
  target.rename(removed)
  try: backups[-1].rename(target)
  except Exception:
   if removed.exists() and not target.exists(): removed.rename(target)
   raise
  print(f'Restored prior package; current package retained at {removed}')
 else:
  target.rename(removed);print(f'No backup found; current package preserved at {removed}')
 print('Host restart is manual.')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError) as e:print(f'rollback refused: {e}',file=sys.stderr);raise SystemExit(2)
