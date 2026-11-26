import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'tools/force_hardware/rollback_package_device.sh'
PLUGIN='TROLLfx - VST - ASR10 FX Collection'

def make_package(path, binary):
    (path/'VST').mkdir(parents=True)
    (path/'plugin.json').write_text('{"name": "ASR10 FX Collection", "manufacturer": "TROLLfx"}\n')
    (path/'VST/asr10-fx-collection-arm32.so').write_bytes(binary)
    entries=[]
    for file in sorted(p for p in path.rglob('*') if p.is_file()):
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        entries.append(f"{digest}  {file.relative_to(path).as_posix()}")
    (path/'SHA256SUMS').write_text('\n'.join(entries)+'\n')

class DeviceRollbackTests(unittest.TestCase):
    def test_restore_keeps_failed_candidate_outside_scanner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);scan=root/'VST2 Plugins';scan.mkdir()
            backup_root=root/'TROLLfx/ASR10/rollback-v1';backup_root.mkdir(parents=True)
            backup=backup_root/PLUGIN;backup.mkdir()
            active=scan/PLUGIN;make_package(active,b'candidate')
            make_package(backup,b'previous-v1')
            p=subprocess.run([str(SCRIPT),str(scan),str(backup_root)],text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertEqual((active/'VST/asr10-fx-collection-arm32.so').read_bytes(),b'previous-v1')
            removed=list(backup_root.glob('.removed-current-*'))
            self.assertEqual(len(removed),1)
            self.assertEqual((removed[0]/'VST/asr10-fx-collection-arm32.so').read_bytes(),b'candidate')

    def test_rejects_backup_inside_plugin_scan_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            scan=Path(tmp)/'VST2 Plugins';scan.mkdir()
            inside=scan/'rollback';inside.mkdir()
            p=subprocess.run([str(SCRIPT),str(scan),str(inside)],text=True,capture_output=True)
            self.assertEqual(p.returncode,2)
            self.assertIn('outside the VST scan directory',p.stderr)

if __name__=='__main__': unittest.main(verbosity=2)
