#!/usr/bin/env python3
"""Test generated V4.1 EDIT routes through the actual native VST2 callback and applied GPR trace."""
from __future__ import annotations
import argparse, importlib.util, json, os, sys, time
import math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DEFAULT_SOURCE=Path.home()/'worktrees/asr10-force-dynamic-editor-v4'
ASSETS=Path(os.environ.get('TROLLFX_FACTORY_PACKAGES_DIR',str(Path.home()/'asr10-force-assets-v1'))).expanduser()
MATRIX=ROOT/'docs/qa-v4/factory-parameter-validation-matrix.json'

def import_simulator(source):
    sys.dont_write_bytecode=True
    module_path=source/'tools/force_simulator/bridge.py'
    spec=importlib.util.spec_from_file_location('trollfx_qa_vst_bridge',module_path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def collect_routes(matrix):
    routes=[]
    for e in matrix['effects']:
        for p in e['parameters']:
            for r in p['current_vst_mapping']:
                pts=p['register_mapping'].get('observed_setting_points',[])
                routes.append((r,pts,p['original_parameter_name']))
        for p in e['additional_recovered_controls']:
            for r in p['current_vst_mapping']:
                routes.append((r,p['verified_points'],p['control_label']))
    bykey={(r['slot'],r['control_id']):(r,pts,label) for r,pts,label in routes}
    return list(bykey.values())

def expected_group(point):
    return [(int(w['gpr'],16),int(w['raw24'],16)) for w in point['ordered_writes']]

def find_group(rows,want,slot):
    for i in range(len(rows)-len(want)+1):
        g=rows[i:i+len(want)]
        if ([(x['gpr'],x['value24']) for x in g]==want and len({x['dsp_frame'] for x in g})==1
            and all(x['slot']==slot for x in g)):
            return g
    return []

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,default=DEFAULT_SOURCE);ap.add_argument('--sdk',default=os.environ.get('AKAI_FORCE_SDK','/mnt/c/Users/Gamer/research/AkaiForceSDK'));ap.add_argument('--assets',type=Path,default=ASSETS);ap.add_argument('--output',type=Path,default=ROOT/'docs/qa-v4/v41-register-range-test-report.json');ap.add_argument('--all-50',action='store_true');a=ap.parse_args()
    source=a.source_root.resolve();
    if not (source/'tools/force_simulator/build.py').is_file():raise SystemExit('V4.1 test host source missing; --source-root must point at the published V4.1 integration source checkout')
    if not (a.assets/'provider-index.tsv').is_file():raise SystemExit('trusted local factory provider index is unavailable')
    spec=importlib.util.spec_from_file_location('trollfx_qa_build',source/'tools/force_simulator/build.py')
    buildmod=importlib.util.module_from_spec(spec);sys.dont_write_bytecode=True;spec.loader.exec_module(buildmod)
    plugin,hostlib=buildmod.build(buildmod.sdk_path(a.sdk),True)
    bridge=import_simulator(source);v=bridge.VSTBridge(hostlib,plugin,a.assets)
    matrix=json.loads(MATRIX.read_text());routes=collect_routes(matrix)
    report={'schema':'asr10-v41-vst-parameter-range-independent-test-v1','test_binary_sha256':__import__('hashlib').sha256(plugin.read_bytes()).hexdigest(),
        'test_host':'native VST2 VSTPluginMain/dispatcher/setParameter/processReplacing with trace-enabled same-source test build',
        'factory_packages':'local private package provider; no contents included','route_count':len(routes),'point_tests':[],'selection_tests':[],
        'all_50_selection_requested':bool(a.all_50),'failed':[],'physical_force':'NOT_TESTED'}
    def select(slot):
        v.set(0,(slot-1)/49)
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            v.pump(256);text=v.text(0)
            if ' / READY' in text and f'{slot:02}' in text:return text
            if 'UNAVAILABLE' in text or 'LOAD FAILED' in text or 'PACKAGE REQUIRED' in text:return text
            time.sleep(.002)
        return v.text(0)
    def exercise(route,points,label):
        slot=int(route['slot']);q=int(route['edit_q_link']);idx=int(route['dynamic_router_vst_parameter_index']);point_count=int(route['point_count'])
        if not points or len(points)!=point_count:raise RuntimeError(f'{slot}/{route["control_id"]}: recovered evidence point count does not match V4.1 registry')
        cases=[('lowest_verified_point',0.0,0),('highest_verified_point',1.0,point_count-1),('midpoint_in_verified_point_domain',0.5,math.floor(.5*(point_count-1)+0.5)),('clamp_low_to_verified_domain',-.25,0),('clamp_high_to_verified_domain',1.25,point_count-1)]
        results=[]
        for case,norm,pi in cases:
            cursor=v.trace_latest();v.set(idx,norm);v.pump(256);rows=v.trace_since(cursor)
            want=expected_group(points[pi]);group=find_group(rows,want,slot)
            shown=v.text(idx);expected_label=route['point_labels'][pi]
            passed=bool(group) and expected_label in shown
            if not passed:report['failed'].append({'slot':slot,'control_id':route['control_id'],'case':case,'register_group_match':bool(group),'display_label_match':expected_label in shown})
            results.append({'case':case,'expected_discrete_point':pi,'resolved_label':expected_label,'exact_ordered_register_write_match':bool(group),'display_label_matches_point':expected_label in shown})
        # Repeat the maximum to ensure equal values remain accepted and update the same evidence group.
        cursor=v.trace_latest();v.set(idx,1.0);v.pump(256);repeat=find_group(v.trace_since(cursor),expected_group(points[-1]),slot)
        results.append({'case':'repeat_maximum','exact_ordered_register_write_match':bool(repeat)})
        if not repeat:report['failed'].append({'slot':slot,'control_id':route['control_id'],'case':'repeat_maximum'})
        return {'slot':slot,'effect':v.text(0).split(' / ')[0],'control_id':route['control_id'],'canonical_vst_index':route['canonical_vst_parameter_index'],
            'dynamic_router_vst_index':idx,'physical_equivalent_q_link':q,'full_range_tested':False,'tested_cases':results,
            'note':'Endpoints are the only supported factory-evidenced points. Midpoint rounds to the nearest of these discrete points; it does not imply full-range interpolation.'}
    try:
        route_results=[]
        for route,points,label in routes:
            status=select(int(route['slot']))
            if ' / READY' not in status:
                report['failed'].append({'slot':route['slot'],'control_id':route['control_id'],'selection':status});continue
            route_results.append(exercise(route,points,label))
        report['point_tests']=route_results
        if a.all_50:
            for slot in range(1,51):
                status=select(slot);ok=' / READY' in status
                report['selection_tests'].append({'slot':slot,'package_ready':ok})
                if not ok:report['failed'].append({'slot':slot,'selection':status})
        # Required HALL → ROOM → PITCH SHIFT → HALL transition and VST state round-trip.
        for slot in (1,3,39,1):
            status=select(slot);report['selection_tests'].append({'slot':slot,'package_ready':' / READY' in status,'sequence':'HALL_ROOM_PITCH_HALL'})
        # Retain distinct canonical selections through the HALL / ROOM / PITCH / HALL cycle.
        select(1);v.set(48,1.0);v.pump(256);hall_value=v.get(29)
        select(3);v.set(46,0.0);v.pump(256);room_value=v.get(33)
        select(39);v.set(46,1.0);v.pump(256);pitch_value=v.get(42)
        select(1);retained={'hall':abs(v.get(29)-hall_value)<1e-4,'room':abs(v.get(33)-room_value)<1e-4,'pitch':abs(v.get(42)-pitch_value)<1e-4}
        report['per_effect_state_retention']=retained
        if not all(retained.values()):report['failed'].append({'case':'per_effect_state_retention','details':retained})
        select(1);v.set(48,1.0);v.pump(256);saved=v.save_state();before=v.get(29)
        select(3);select(39);v.restore_state(saved);v.pump(512)
        restored={'effect_slot':round(v.get(0)*49)+1,'canonical_decay_vst_value':v.get(29),'expected_canonical_value':before,'passed':abs(v.get(29)-before)<1e-4}
        report['state_round_trip']=restored
        if not restored['passed']:report['failed'].append({'case':'state_round_trip'})
        # An effect with no verified editor controls must stay visibly unmapped.
        status=select(10);v.set(46,.9);v.pump(256);unmapped={'slot':10,'display':v.text(46),'passed':'NO VERIFIED CONTROL' in v.text(46)}
        report['unmapped_control_test']=unmapped
        if not unmapped['passed']:report['failed'].append({'case':'unmapped_control'})
    finally:v.close()
    report['tested_routes']=len(report['point_tests']);report['result']='PASS' if not report['failed'] and report['tested_routes']==19 else 'FAIL'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'result':report['result'],'routes':report['tested_routes'],'point_cases':sum(len(r['tested_cases']) for r in report['point_tests']),'selection_tests':len(report['selection_tests']),'failures':len(report['failed']),'report':str(a.output)},indent=2))
    if report['failed']:raise SystemExit(1)
if __name__=='__main__':main()
