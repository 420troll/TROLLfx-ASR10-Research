#!/usr/bin/env python3
"""Strict gate for independently recorded Force/plugin Q-Link event traces.

This validates evidence shape and invariants. It does not synthesize events,
infer register effects, or treat host parameter changes as DSP proof.
"""
import argparse, json, re
from pathlib import Path

REQUIRED = ('effect_slot','parameter_id','page','bank','qlink','host_parameter_index',
            'physical_label','expected_label','label_matches','available','availability_checked',
            'host_event_seen','internal_parameter_before','internal_parameter_after',
            'expected_internal_change','register_writes_before','register_writes_after',
            'expected_register_write_group','observed_register_write_group',
            'reverse_value','reverse_restored','reverse_register_group_restored',
            'unrelated_state_unchanged','repeated_value_stable','save_reload_restored')

def trace_key(x):
    return (x.get('effect_slot'),x.get('parameter_id'),x.get('page'),x.get('bank'),x.get('qlink'))

def validate(doc):
    errors=[]; cases=doc.get('cases') if isinstance(doc,dict) else None
    for field in ('evidence_source','plugin_binary_sha256','runtime_trace_sha256','source_commit','candidate_id'):
        if not doc.get(field): errors.append(f'missing {field}')
    for field in ('plugin_binary_sha256','runtime_trace_sha256'):
        if doc.get(field) and not re.fullmatch(r'[0-9a-fA-F]{64}',str(doc[field])): errors.append(f'{field} must be a SHA-256 hex digest')
    if doc.get('source_commit') and not re.fullmatch(r'[0-9a-fA-F]{40}',str(doc['source_commit'])): errors.append('source_commit must be a 40-character Git commit')
    if not isinstance(cases,list) or not cases: errors.append('no event cases'); return errors
    expected=doc.get('expected_controls')
    if not isinstance(expected,list) or not expected: errors.append('missing expected_controls coverage list')
    seen=set()
    for i,c in enumerate(cases):
        for key in REQUIRED:
            if key not in c: errors.append(f'case[{i}] missing {key}')
        if any(k not in c for k in REQUIRED): continue
        ident=trace_key(c)
        if ident in seen: errors.append(f'case[{i}] duplicate assignment {ident}')
        seen.add(ident)
        if c['label_matches'] is not True or c['physical_label'] != c['expected_label']: errors.append(f'case[{i}] physical Q-Link label does not match the selected control')
        if c['available'] is True and c['host_event_seen'] is not True: errors.append(f'case[{i}] host event not observed')
        if c['available'] is False and c['host_event_seen'] is True: errors.append(f'case[{i}] unavailable control received an active event')
        if c['available'] is True and c['internal_parameter_before']==c['internal_parameter_after'] and c['expected_internal_change'] is True:
            errors.append(f'case[{i}] host event did not change internal parameter')
        if c['available'] is True and not c['expected_register_write_group']:
            errors.append(f'case[{i}] no independently specified expected DSP register group')
        if c['available'] is True and c['observed_register_write_group'] != c['expected_register_write_group']:
            errors.append(f'case[{i}] observed DSP register group differs from expected ordered group')
        if c['available'] is True and c['register_writes_before']==c['register_writes_after'] and c['expected_internal_change'] is True:
            errors.append(f'case[{i}] no intended DSP register write delta')
        for k in ('unrelated_state_unchanged','reverse_restored','reverse_register_group_restored','save_reload_restored','repeated_value_stable','availability_checked'):
            if c[k] is not True: errors.append(f'case[{i}] {k} not passed')
    if isinstance(expected,list):
        exp={trace_key(x) for x in expected}; got={trace_key(x) for x in cases}
        for missing in sorted(exp-got,key=str): errors.append(f'missing expected control case {missing}')
        for extra in sorted(got-exp,key=str): errors.append(f'unexpected control case {extra}')
    return errors

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('trace'); a=ap.parse_args(); d=json.loads(Path(a.trace).read_text()); errors=validate(d)
    print(json.dumps({'status':'FAIL' if errors else 'PASS','cases':len(d.get('cases',[])),'errors':errors},indent=2)); raise SystemExit(bool(errors))
if __name__=='__main__': main()
