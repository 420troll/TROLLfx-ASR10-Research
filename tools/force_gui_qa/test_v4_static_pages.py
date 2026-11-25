#!/usr/bin/env python3
"""Static contract smoke for V4's generated HALL/ROOM pages and Q-Link maps.

This does not simulate switching tabs on a Force or in the SDK host simulator.
"""
import argparse, json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('force_plugin',type=Path); a=ap.parse_args()
    root=a.force_plugin
    skin=root/'dist/TROLLfx - VST - ASR10 FX Collection/Plugin Skins'
    authored=json.loads((root/'ui.json').read_text())
    tabs=json.loads((skin/'TUI.json').read_text())['pageData']['tabs']
    maps=json.loads((skin/'Q-Links.json').read_text())['Screen Mode Q-Links']['map']
    names=[p['name'] for p in authored['pages']]
    generated=[t['tabName'] for t in tabs]
    assert names==generated, 'authored and generated page order differ'
    assert len(tabs)==len(maps)==15, 'V4 should contain 15 fixed tabs/maps'
    assert {'BROWSE','MIX','01 EDIT','03 EDIT'} <= set(generated)
    assert len({(t['fnKeyIndex'],t['fnKeySubIndex']) for t in tabs})==len(tabs)
    expected={
      '01 EDIT': {'REVERB MIX BUS1 @ 01','REVERB MIX BUS2 @ 01','DECAY TIME @ 01','HI FREQ DAMPING @ 01'},
      '03 EDIT': {'DECAY TIME @ 03','DIFFUSION @ 03','HI FREQ DAMPING @ 03'},
    }
    for page,labels in expected.items():
        i=generated.index(page); tab=tabs[i]
        controls=tab['componentDefinition']['componentsData']; bound={}
        for c in controls:
            name=c.get('componentData',{}).get('name')
            remap=c.get('handle remapping',{}).get('map',[])
            p=next((x.get('value') for x in remap if x.get('value','').startswith('Parameter ')),None)
            if p: bound[name]=int(p.split()[1])
        assert set(bound)==labels, f'{page}: unexpected visible control set {set(bound)}'
        qmap=maps[i]['Q-Links']
        mapped={v for v in qmap.values() if isinstance(v,int) and v>=0}
        assert mapped==set(bound.values()), f'{page}: Q-Link targets differ from visible effect-specific parameter bindings'
        assert len(mapped)==len(bound), f'{page}: duplicate target or unbound control'
        assert not any('visibleWhen' in x or 'visibility' in x.lower() for x in tab), 'tab appears conditionally hidden; SDK support is not established'
    print('PASS static HALL/ROOM page separation and per-page Q-Link map consistency')
    print(f'LIMIT: {len(tabs)} fixed tabs serialized; no host/Force navigation event was exercised')
if __name__=='__main__': main()
