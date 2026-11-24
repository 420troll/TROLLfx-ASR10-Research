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
assert [(x['slot'],x['name']) for x in data if x.get('runtime_supported')]==[(1,'HALL REVERB'),(2,'44KHZ REVERB')]
assert json.loads((root/'plugin.json').read_text())['version']=='1.0.0-experimental'
src=(root/'src/ASR10FXCollection.cpp').read_text()
assert src.count('[UNAVAILABLE]')==48 and '[PACKAGE]' in src
print('catalog and fail-closed UI checks: PASS')
