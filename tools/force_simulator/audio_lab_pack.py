#!/usr/bin/env python3
"""Package two already-rendered WAV artifacts for the desktop AUDIO LAB.

This utility copies audio bytes and a small evidence manifest; it does not open
factory packages, run a processor, or infer raw-code destinations.
"""
import argparse
import base64
import json
from pathlib import Path

from audio_lab import SCHEMA

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--metadata',required=True,type=Path,help='Path-free pair metadata JSON')
    ap.add_argument('--a-wav',required=True,type=Path)
    ap.add_argument('--b-wav',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args()
    meta=json.loads(args.metadata.read_text())
    allowed={'source','variation','stimulus','case_id','a','b'}
    if not isinstance(meta,dict) or set(meta)!=allowed:
        raise SystemExit('metadata must contain only source, variation, stimulus, case_id, a and b')
    def render(key,wav):
        row=meta[key]
        required={'display_value','raw_code','raw_code_basis','dsp_status','runtime_status','firmware_status','processing_rate_hz','package_provenance','provenance_id','source_commit','register_updates'}
        if not isinstance(row,dict) or set(row)!=required:
            raise SystemExit(f'{key} metadata must contain exactly: {", ".join(sorted(required))}')
        raw=wav.read_bytes()
        return {**row,'wav_base64':base64.b64encode(raw).decode('ascii')}
    bundle={'schema':SCHEMA,'source':meta['source'],'effect_slot':1,'effect_name':'HALL REVERB',
        'variation':meta['variation'],
        'cases':[{'case_id':meta['case_id'],'stimulus':meta['stimulus'],'a':render('a',args.a_wav),'b':render('b',args.b_wav)}]}
    args.output.write_text(json.dumps(bundle,separators=(',',':'))+'\n')
    print(f'Wrote HALL AUDIO LAB bundle: {args.output} ({args.output.stat().st_size} bytes)')

if __name__=='__main__':main()
