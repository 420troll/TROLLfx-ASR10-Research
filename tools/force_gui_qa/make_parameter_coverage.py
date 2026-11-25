#!/usr/bin/env python3
"""Generate conservative per-effect control coverage from public evidence."""
import argparse, csv, json
from collections import defaultdict
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--catalog',required=True); ap.add_argument('--recovery-v2',required=True); ap.add_argument('--recovery-v3',required=True); ap.add_argument('--registry',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
    cat=json.loads(Path(a.catalog).read_text()); v2=json.loads(Path(a.recovery_v2).read_text()); v3=json.loads(Path(a.recovery_v3).read_text()); reg=json.loads(Path(a.registry).read_text())
    v2c=[dict(slot=e['slot'], **p) for e in v2.get('effects',[]) for p in e.get('parameters',[])]; v3c=v3.get('new_verified_controls',[])
    verified=[]
    v2_slots=set()
    for c in list(v2c)+list(v3c):
        slot=c.get('slot'); verified.append({'slot':slot,'id':c.get('parameter_id',c.get('id')),'audio':str(c.get('audio_verification','')).lower()})
    v2_slots={e['slot'] for e in v2.get('effects',[]) if e.get('parameters')}
    # Registry JSON stores controls per effect; derive direct source-level GUI/Q-Link counts separately below.
    gui=defaultdict(int); qlink=defaultdict(int); runtime=defaultdict(int)
    for c in verified: runtime[c['slot']]+=1
    for c in reg.get('effects',[]):
        slot=c.get('slot')
        if slot in runtime and any(p.get('runtime_ready') or p.get('runtime_status')=='runtime_ready' for p in c.get('documented_controls',[])):
            runtime[slot]=sum(x['slot']==slot for x in verified)
    for c in verified: gui[c['slot']]+=1; qlink[c['slot']]+=1
    mapped_by_slot={}
    for c in verified: mapped_by_slot[c['slot']]=mapped_by_slot.get(c['slot'],0)+1
    effects=[]
    for e in cat['effects']:
        slot=e['slot']; manual=len(e.get('parameters',[])); mapped=mapped_by_slot.get(slot,0)
        # Only V3 publishes per-control nonzero delta attribution. V2's
        # public result is aggregate-only (10/16), so keep affected slots null.
        audio=1 if slot==39 else (None if slot in v2_slots else 0)
        effects.append({'slot':slot,'effect_id':e.get('id'),'factory_effect':e.get('factory_name'),'manual_listed_parameter_count':manual,'os_observed_editable_field_count_minimum_verified':mapped,'os_observation_is_exhaustive':False,'register_mapped_control_count':mapped,'audio_change_verified_control_count':audio,'force_runtime_ready_control_count':runtime.get(slot,0),'gui_visible_control_count':gui.get(slot,0),'q_link_assigned_control_count':qlink.get(slot,0),'q_link_end_to_end_verified_control_count':0,'physical_force_end_to_end_verified_control_count':0,'manual_entries_not_register_mapped_by_count_lower_bound':max(0,manual-mapped),'missing_or_unsupported_controls':'Manual entries remain unpromoted without register/runtime evidence; exact one-to-one matching against compound OS fields is incomplete.' if manual>mapped else 'No count gap; physical operation still unverified.','evidence':['ASR10_FACTORY_PARAMETER_CATALOG_V1.json','ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json','ASR10_FACTORY_PARAMETER_RECOVERY_V03.json','es5510_factory_editor_v03.hpp'],'status':'NOT TESTED on physical Force'})
    doc={'schema':'asr10-factory-parameter-coverage-matrix-v1','evidence_policy':'Counts are conservative evidence counts. Manual parameter count is not runtime support. OS-observed count is a confirmed lower bound from reversible register mappings, not an exhaustive OS field sweep. GUI and Q-Link counts reflect V3 source assignments, not physical activation. Q-Link end-to-end count requires trace from a physical Q-Link through internal state to DSP register writes. Per-effect audio delta is null where V2 public sources do not attribute its aggregate result to a specific control/effect. Manual-entry count gaps are not an exact one-to-one unsupported-control list because compound rows are not fully reconciled.','published_v2_audio_change_aggregate':'10 of 16 mapped controls showed nonzero output delta; per-control attribution unavailable in public summary.','totals':{'effects':len(effects),'manual_listed_parameters':sum(e['manual_listed_parameter_count'] for e in effects),'register_mapped_controls':sum(e['register_mapped_control_count'] for e in effects),'audio_change_verified_controls':11,'audio_count_basis':'V2 published aggregate 10/16 plus V3 PITCH SHIFT QUALITY nonzero output difference.','force_runtime_ready_controls':sum(e['force_runtime_ready_control_count'] for e in effects),'gui_visible_controls':sum(e['gui_visible_control_count'] for e in effects),'q_link_assigned_controls':sum(e['q_link_assigned_control_count'] for e in effects),'q_link_end_to_end_verified_controls':0,'physical_force_verified_controls':0},'effects':effects}
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(doc,indent=2)+'\n')
    with out.with_suffix('.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(effects[0]),lineterminator='\n'); w.writeheader(); w.writerows(effects)
    print(json.dumps(doc['totals'],indent=2))
if __name__=='__main__': main()
