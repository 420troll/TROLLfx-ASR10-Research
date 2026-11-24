import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/'force_plugin/dist/TROLLfx - VST - ASR10 FX Collection'
TOOLS=ROOT/'force_plugin/tools'
sys.path.insert(0,str(TOOLS))
import build_release, install_package

class ReleaseInfraTests(unittest.TestCase):
    def test_sdk_discovery_finds_valid_checkout(self):
        sdk=build_release.discover_sdk(None)
        self.assertTrue((sdk/'tools/build.py').is_file())
        self.assertTrue((sdk/'framework/mpc_plugin.h').is_file())

    def test_candidate_manifest_and_package_checksums(self):
        m=json.loads((PACKAGE/'release-manifest.json').read_text())
        self.assertEqual(m['release_state'],'candidate')
        self.assertFalse(m['playable'])
        expected={}
        for line in (PACKAGE/'SHA256SUMS').read_text().splitlines():
            h,name=line.split('  ',1); expected[name]=h
        actual={p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
        self.assertEqual(set(expected),actual)
        for name,h in expected.items(): self.assertEqual(hashlib.sha256((PACKAGE/name).read_bytes()).hexdigest(),h)

    def test_candidate_refused_without_creating_install_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'VST2 Plugins'
            with self.assertRaisesRegex(ValueError,'no DSP integration marker'):
                install_package.verify(PACKAGE)
            p=subprocess.run([sys.executable,str(TOOLS/'install_package.py'),str(PACKAGE),str(target)],text=True,capture_output=True)
            self.assertEqual(p.returncode,2,p.stdout+p.stderr)
            self.assertFalse(target.exists())

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
            p=subprocess.run([sys.executable,str(TOOLS/'mark_playable.py'),'--package',str(PACKAGE),'--report',str(report)],text=True,capture_output=True)
            self.assertNotEqual(p.returncode,0)
            self.assertFalse((PACKAGE/'INTEGRATION_STATUS').exists())

if __name__=='__main__': unittest.main(verbosity=2)
