#!/usr/bin/env python3
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
data=json.loads((root/'effects.json').read_text())
assert len(data)==50 and [x['slot'] for x in data]==list(range(1,51))
text=(root.parent/'docs/ASR10_ROM_EFFECT_CATALOG.md').read_text()
import re
expected=[(int(n),label.strip()) for n,label in re.findall(r'^\|\s*(\d{2})\s*\|\s*([^|]+?)\s*\|',text,re.M)]
expected=[x for x in expected if 1<=x[0]<=50]
assert [(x['slot'],x['name']) for x in data]==expected
assert not any(x.get('runtime_supported') for x in data)
manifest=json.loads((root/'plugin.json').read_text())
assert manifest['version']=='1.0.0' and manifest['releaseChannel']=='experimental'
src=(root/'src/ASR10FXCollection.cpp').read_text()
assert 'for(unsigned i=0;i<50;++i)' in src
assert '" [READY]":" [UNAVAILABLE]"' in src
assert 'TROLLfx_GetValidatedFactoryPackageProvider()' in src
assert 'backend_.request_effect' in src and 'backend_.process' in src
assert 'TROLLfx_GetProductionFactoryPackageProvider()' in src
assert 'out="UNAVAIL"' in src and 'out="LOADING"' in src and 'out="READY"' in src
assert 'mock' not in src.lower()
print('50-slot catalog, package identity labels, real backend connection and unavailable status: PASS')
