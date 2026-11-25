#!/usr/bin/env python3
"""Merge the public manual inventory, recovered register mappings, and V4 editor map."""
from __future__ import annotations
import argparse, hashlib, json, re
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'docs/qa-v4/source'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return re.sub(r'[^A-Z0-9]+','',str(s).upper())
def parse_range(text):
    text=str(text or '').strip()
    out={'minimum':None,'maximum':None,'units':None,'choices':None,'choice_count':None,'parse_status':'UNKNOWN','source_text':text}
    if not text:return out
    if re.search(r'four\s+Effect\s+Variations',text,re.I):
        out.update(parse_status='COUNT_ONLY_CHOICES_UNRECOVERED',choice_count=4);return out
    ratios=re.search(r'(\d+\s*/\s*\d+)\s+to\s+(\d+\s*/\s*\d+)',text,re.I)
    if ratios:
        out.update(minimum=ratios.group(1).replace(' ',''),maximum=ratios.group(2).replace(' ',''),parse_status='PARSED_RATIO')
        if re.search(r'\bINF(?:INITY)?\b',text,re.I):out['choices']=['INF']
        return out
    m=re.search(r'(?<![A-Za-z0-9])([+-]?\d+(?:\.\d+)?)\s*([A-Za-zµμ%]*)\s*(?:to|–|—)\s*([+-]?\d+(?:\.\d+)?)\s*([A-Za-zµμ%]*)',text,re.I)
    if m:
        lo,lu,hi,hu=m.groups()
        out.update(minimum={'value':float(Decimal(lo)),'unit':lu or hu or None,'text':lo+(lu or hu)},
                   maximum={'value':float(Decimal(hi)),'unit':hu or lu or None,'text':hi+(hu or lu)},
                   units=(hu or lu or None),parse_status='PARSED_NUMERIC')
        return out
    # Plain two-state labels are enumerations, not numeric ranges.
    if re.search(r'\s+or\s+',text,re.I):
        choices=[x.strip().strip('.') for x in re.split(r'\s+or\s+',text,flags=re.I)]
        out.update(choices=choices,choice_count=len(choices),parse_status='PARSED_ENUM')
    return out

def header_controls(path):
    text=path.read_text()
    arrays={}
    for m in re.finditer(r'kPointLabels(\d+)\[\]\s*=\s*\{([^}]*)\};',text):
        arrays.setdefault(int(m.group(1)),{})['labels']=re.findall(r'"([^"]*)"',m.group(2))
    for m in re.finditer(r'kPointValues(\d+)\[\]\s*=\s*\{([^}]*)\};',text):
        vals=[]
        for tok in m.group(2).split(','):
            tok=tok.strip()
            if tok: vals.append(int(tok,0))
        arrays.setdefault(int(m.group(1)),{})['values']=vals
    controls=[]
    pattern=r'\{\s*(\d+)\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*kPointLabels(\d+)\s*,\s*kPointValues\7\s*,\s*(\d+)\s*\}'
    for m in re.finditer(pattern,text):
        slot,cid,label,dyn_id,host_id,canonical,arr,count=m.groups(); slot=int(slot); ordinal=sum(x['slot']==slot for x in controls)
        points=arrays.get(int(arr),{})
        controls.append({'slot':slot,'control_id':cid,'display_name':label,'dynamic_name':dyn_id,'vst_parameter_id':host_id,
            'canonical_vst_parameter_index':int(canonical),'point_count':int(count),'point_values':points.get('values',[]),
            'point_labels':points.get('labels',[]),'dynamic_router_vst_parameter_index':46+ordinal if ordinal<8 else None,
            'edit_q_link':ordinal+1 if ordinal<8 else None,'page':'EDIT','source':'V4.1 es5510_factory_editor_v04.hpp'})
    return controls

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,default=SRC);ap.add_argument('--output',type=Path,default=ROOT/'docs/qa-v4/factory-parameter-validation-matrix.json');a=ap.parse_args()
    src=a.source; catalog=json.loads((src/'ASR10_FACTORY_PARAMETER_CATALOG_V1.json').read_text())
    v2=json.loads((src/'ASR10_FACTORY_PARAMETER_MAPPINGS_V02.json').read_text())
    v3=json.loads((src/'ASR10_FACTORY_PARAMETER_RECOVERY_V03.json').read_text())
    v5=json.loads((src/'ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05.json').read_text())
    vst=header_controls(src/'es5510_factory_editor_v04.hpp')
    evidence={}
    def add(slot,control_id,label,points,source,register_status='REGISTER_VERIFIED_ADJACENT_POINTS',audio=None,runtime=None,range_status=None):
        key=(int(slot),norm(label))
        evidence.setdefault(key,[]).append({'parameter_id':control_id,'source':source,'register_status':register_status,
            'display_name':label,'audio_status':audio,'runtime_status':runtime,'range_status':range_status,'verified_points':points})
    for effect in catalog['effects']:
        for c in effect.get('verified_runtime_parameters',[]):
            add(effect['slot'],c['id'],c['display_name'],c.get('verified_display_points',[]),'ASR10_FACTORY_PARAMETER_CATALOG_V1')
    for effect in v2['effects']:
        for c in effect.get('parameters',[]):
            add(effect['slot'],c['id'],c.get('ui_label',c['id']),c.get('points',[]),'ASR10_FACTORY_PARAMETER_MAPPINGS_V02')
    for c in v3.get('new_verified_controls',[]):
        pts=[{'display_value':p['value'],'display_text':p['text'],'ordered_writes':[{'gpr':f'0x{gpr:02X}','raw24':v} for gpr,v in p['writes']]} for p in c.get('points',[])]
        add(c['slot'],c['parameter_id'],c['display_name'],pts,'ASR10_FACTORY_PARAMETER_RECOVERY_V03',audio=c.get('audio_verification'),runtime=c.get('register_verification'),range_status=c.get('display_domain'))
    for c in v5.get('controls',[]):
        pts=[{'display_value':p['value'],'display_text':p['text'],'ordered_writes':[{'gpr':w['gpr'],'raw24':w['value24']} for w in p['ordered_writes']]} for p in c.get('verified_points',[])]
        add(c['slot'],c['parameter_id'],c['display_name'],pts,'ASR10_FACTORY_DSP_PARAMETER_MAPPINGS_V05',
            audio=c.get('audio_status'),runtime=c.get('mapping_status'),range_status={'status':c.get('range_status'),'text':c.get('documented_range')})
    vst_by_key={}
    for c in vst:vst_by_key.setdefault((c['slot'],norm(c['display_name'])),[]).append(c)
    effects=[];summary={'effects':len(catalog['effects']),'original_parameters':0,'additional_recovered_controls':0,'classification':{},'register_mapped_manual_parameters':0,'current_vst_controls':len(vst),'current_vst_dynamic_q_routes':0,'full_range_implemented':0}
    for effect in catalog['effects']:
        rows=[];matched_keys=set()
        for p in effect['parameters']:
            label=p.get('display_name','');key=(effect['slot'],norm(label));evs=evidence.get(key,[]);vmap=vst_by_key.get(key,[])
            if evs:matched_keys.add(key)
            points=[]
            for ev in evs:
                points.extend(ev['verified_points'])
            # deduplicate identical values/write groups from V1 and V2 sources.
            normalized_points=[]
            for pt in points:
                value=pt.get('display_value',pt.get('value'));text=pt.get('display_text',pt.get('text',str(value)))
                writes=pt.get('ordered_writes',pt.get('writes',[])); ordered=[]
                for w in writes:
                    if isinstance(w,dict):gpr=w.get('gpr');raw=w.get('raw24',w.get('value24'))
                    else:gpr,raw=w
                    if isinstance(gpr,int):gpr=f'0x{gpr:02X}'
                    ordered.append({'gpr':gpr,'raw24':raw})
                normalized_points.append({'display_value':value,'display_text':text,'ordered_writes':ordered})
            uniq=[];seen=set()
            for pt in normalized_points:
                signature=json.dumps(pt,sort_keys=True)
                if signature not in seen:seen.add(signature);uniq.append(pt)
            rg=parse_range(p.get('documented_range'))
            register_status='REGISTER_VERIFIED' if uniq else 'UNMAPPED'
            dsp_status='YES' if any(e['audio_status']=='AUDIO_DIFFERENCE_OBSERVED' or e['audio_status'] and 'difference measured' in str(e['audio_status']).lower() for e in evs) else ('UNKNOWN' if uniq else 'NOT_TESTED')
            audio_status='OBSERVED_CHANGE' if dsp_status=='YES' else ('NO_CHANGE_FOR_RECORDED_STIMULUS' if any(e['audio_status'] and ('NO_DIFFERENCE' in str(e['audio_status']) or 'bit-identical' in str(e['audio_status']).lower()) for e in evs) else 'NOT_VALIDATED')
            full_test=False
            if full_test:classification='VERIFIED'
            elif uniq:classification='PARTIAL'
            elif rg['parse_status'] in ('UNKNOWN','COUNT_ONLY_CHOICES_UNRECOVERED'):classification='UNKNOWN'
            else:classification='UNMAPPED'
            regmap={}
            if uniq:
                regs=[]
                for pt in uniq:
                    for w in pt.get('ordered_writes',[]):
                        gpr=w.get('gpr'); regs.append(gpr)
                regmap={'register_addresses':list(dict.fromkeys(regs)),'observed_setting_points':uniq,
                        'all_observed_points_are_full_range':False}
                summary['register_mapped_manual_parameters']+=1
            rows.append({'original_parameter_id':p['id'],'original_parameter_name':label,'display_order':p.get('display_order'),
                'documented_range':rg,'minimum_value':rg['minimum'],'maximum_value':rg['maximum'],'enumerated_choices':rg['choices'],'documented_type':p.get('display_type'),'units':p.get('units'),
                'full_range_step_size':None,'observed_adjacent_steps':sorted({abs(int(ev['verified_points'][j+1]['display_value'])-int(ev['verified_points'][j]['display_value'])) for ev in evs for j in range(max(0,len(ev['verified_points'])-1)) if isinstance(ev['verified_points'][j].get('display_value'),(int,float)) and isinstance(ev['verified_points'][j+1].get('display_value'),(int,float))}),
                'factory_evidence':{'catalog_note':p.get('evidence'),'manual_cross_references':effect.get('manual_cross_references',[]),'mapping_sources':[e['source'] for e in evs]},
                'current_vst_mapping':vmap,
                'register_mapping':regmap,'full_documented_range_implemented':False,
                'range_implementation_note':'Only explicitly listed verified points are implemented; no interpolation/full-range claim.',
                'changes_dsp_behavior':dsp_status,'audio_behavior_validation':audio_status,
                'classification':classification})
            summary['original_parameters']+=1;summary['classification'][classification]=summary['classification'].get(classification,0)+1
            summary['current_vst_dynamic_q_routes']+=len(vmap)
        extras=[]
        for (slot,nlabel),evs in sorted(evidence.items()):
            if slot!=effect['slot'] or (slot,nlabel) in matched_keys:continue
            # Attach only recovered controls whose display label was not a manual-listed label.
            examples=evs[-1]
            vmap=vst_by_key.get((slot,nlabel),[])
            pts=[]
            for e in evs:pts.extend(e['verified_points'])
            normal_extra=[]
            for pt in pts:
                val=pt.get('display_value',pt.get('value'));text=pt.get('display_text',pt.get('text',str(val)))
                writes=pt.get('ordered_writes',pt.get('writes',[]));ordered=[]
                for w in writes:
                    if isinstance(w,dict):gpr=w.get('gpr');raw=w.get('raw24',w.get('value24'))
                    else:gpr,raw=w
                    if isinstance(gpr,int):gpr=f'0x{gpr:02X}'
                    ordered.append({'gpr':gpr,'raw24':raw})
                normal_extra.append({'display_value':val,'display_text':text,'ordered_writes':ordered})
            uniq_extra=[];seen_extra=set()
            for pt in normal_extra:
                sig=json.dumps(pt,sort_keys=True)
                if sig not in seen_extra:seen_extra.add(sig);uniq_extra.append(pt)
            extras.append({'control_label':evs[0].get('display_name',nlabel),'parameter_ids':[e['parameter_id'] for e in evs],
                'mapping_sources':list(dict.fromkeys(e['source'] for e in evs)),
                'verified_points':uniq_extra,'current_vst_mapping':vmap,
                'documented_range_evidence':[e.get('range_status') for e in evs if e.get('range_status')],
                'full_documented_range_implemented':False,'classification':'PARTIAL' if pts else 'UNMAPPED'})
        summary['additional_recovered_controls']+=len(extras)
        effects.append({'slot':effect['slot'],'effect_id':effect['id'],'factory_effect_name':effect['factory_name'],
                        'original_parameter_count':len(rows),'parameters':rows,'additional_recovered_controls':extras})
    summary['full_range_implemented']=0
    summary['current_vst_dynamic_q_routes']=sum(c['edit_q_link'] is not None for c in vst)
    out={'schema':'trollfx-asr10-full-parameter-independent-validation-matrix-v1',
        'provenance':{'inventory_commit':'ce4bfdaa6dba8b3787e013a3262bbdeb7ec4d3ab','current_v4_1_source_commit':'28458b3a1fb8c1e12f5f1abbdb70772e40e129fa',
            'matrix_source_directory':'docs/qa-v4/source','firmware_and_private_probe_captures_excluded':True},
        'classification_policy':{'VERIFIED':'Complete original range and value-domain exercised, observed register writes match factory evidence, DSP effect independently confirmed; none promoted by inventory alone.',
            'PARTIAL':'Some exact points/registers are evidenced or integrated, but the complete original range/step behavior is not independently validated.',
            'UNMAPPED':'Documented parameter has no recovered register mapping in the imported evidence.',
            'UNKNOWN':'Original range/choices or identity remain ambiguous, or source says see below/unrecovered.'},
        'summary':summary,'effects':effects}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
