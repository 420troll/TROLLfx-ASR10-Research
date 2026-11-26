import hashlib, json, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/'force_plugin/dist/TROLLfx - VST - ASR10 FX Collection'
TOOLS=ROOT/'force_plugin/tools'
sys.path.insert(0,str(TOOLS))
import build_release, install_package

def candidate_fixture(parent):
    package=Path(parent)/'candidate';shutil.copytree(PACKAGE,package)
    for name in ('INTEGRATION_STATUS','factory-playback-status.json'):
        (package/name).unlink(missing_ok=True)
    manifest_path=package/'release-manifest.json';manifest=json.loads(manifest_path.read_text())
    manifest.update({'release_state':'candidate','playable':False});manifest.pop('playable_marker',None)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    (package/'INSTALL.txt').write_text('BUILD CANDIDATE ONLY — NOT PLAYABLE / DO NOT INSTALL.\n')
    build_release.create_checksums(package)
    return package

class ReleaseInfraTests(unittest.TestCase):
    def test_sdk_discovery_finds_valid_checkout(self):
        sdk=build_release.discover_sdk(None)
        self.assertTrue((sdk/'tools/build.py').is_file())
        self.assertTrue((sdk/'framework/mpc_plugin.h').is_file())

    def test_stale_qemu_report_is_not_applied_to_new_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);binary=root/'candidate-arm32.so';binary.write_bytes(b'new candidate')
            report=root/'qemu.json';report.write_text(json.dumps({'status':'PASS','processed_slots':50,'plugin_sha256':'0'*64}))
            with patch.object(build_release.shutil,'which',return_value=None):
                result=build_release.arm32_qemu_evidence(report,binary)
            self.assertEqual(result['result'],'NOT_RUN')
            self.assertNotEqual(result['stale_report_binary_sha256'],result['candidate_binary_sha256'])

    def test_stale_qemu_report_requires_rerun_when_qemu_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);binary=root/'candidate-arm32.so';binary.write_bytes(b'new candidate')
            report=root/'qemu.json';report.write_text(json.dumps({'status':'PASS','processed_slots':50,'plugin_sha256':'0'*64}))
            with patch.object(build_release.shutil,'which',return_value='/usr/bin/qemu-arm'):
                with self.assertRaisesRegex(RuntimeError,'stale'):
                    build_release.arm32_qemu_evidence(report,binary)

    def test_force_asset_root_requires_absolute_device_path(self):
        with patch.dict(build_release.os.environ,{'TROLLFX_FORCE_ASSET_ROOT':'relative/FactoryAssets'}):
            with self.assertRaisesRegex(RuntimeError,'absolute'):
                build_release.force_asset_root()
        with patch.dict(build_release.os.environ,{'TROLLFX_FORCE_ASSET_ROOT':'/media/SSD250g/TROLLfx/ASR10/factory-effects'}):
            self.assertEqual(build_release.force_asset_root(),'/media/SSD250g/TROLLfx/ASR10/factory-effects')

    def test_candidate_manifest_and_package_checksums(self):
        with tempfile.TemporaryDirectory() as tmp:
            package=candidate_fixture(tmp);m=json.loads((package/'release-manifest.json').read_text())
            self.assertEqual(m['release_state'],'candidate');self.assertFalse(m['playable'])
            expected={}
            for line in (package/'SHA256SUMS').read_text().splitlines():
                h,name=line.split('  ',1);expected[name]=h
            actual={p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
            self.assertEqual(set(expected),actual)
            for name,h in expected.items():self.assertEqual(hashlib.sha256((package/name).read_bytes()).hexdigest(),h)

    def test_candidate_refused_without_creating_install_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'VST2 Plugins'
            package=candidate_fixture(tmp)
            with self.assertRaisesRegex(ValueError,'no DSP integration marker'):install_package.verify(package)
            p=subprocess.run([sys.executable,str(TOOLS/'install_package.py'),str(package),str(target)],text=True,capture_output=True)
            self.assertEqual(p.returncode,2,p.stdout+p.stderr);self.assertFalse(target.exists())

    def test_rollback_preserves_removed_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'VST2 Plugins';active=root/'TROLLfx - VST - ASR10 FX Collection';active.mkdir(parents=True)
            (active/'plugin.json').write_text(json.dumps({'name':'ASR10 FX Collection','manufacturer':'TROLLfx'}))
            p=subprocess.run([sys.executable,str(TOOLS/'rollback_package.py'),str(root)],text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertFalse(active.exists())
            preserved=list(root.glob('.removed-TROLLfx - VST - ASR10 FX Collection-*'))
            self.assertEqual(len(preserved),1)
            self.assertTrue((preserved[0]/'plugin.json').is_file())

    def test_failed_dsp_report_cannot_write_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=Path(tmp)/'report.json';report.write_text(json.dumps({'schema':'trollfx-force-dsp-integration-report-v1','status':'FAIL'}))
            package=candidate_fixture(tmp)
            p=subprocess.run([sys.executable,str(TOOLS/'mark_playable.py'),'--package',str(package),'--report',str(report)],text=True,capture_output=True)
            self.assertNotEqual(p.returncode,0)
            self.assertFalse((package/'INTEGRATION_STATUS').exists())

if __name__=='__main__': unittest.main(verbosity=2)
