#!/usr/bin/env python3
"""Seed, read-only intake, and validation for the ASR-10 OS 3.53 effect parameter catalog."""
from __future__ import annotations
import argparse, json, pathlib, re, sys

SCHEMA='asr10-os353-factory-parameter-catalog-v1'
NAMES=['HALL REVERB','44KHZ REVERB','ROOM REVERB','DUAL DELAYS','44KHZ DELAYS','CHORUS+REVRB','PHASER+REVRB','FLANGER+REV','ROT.SPKR+REV','CHOR+REV+DDL','CMP+DIST+REV','DIST+CHO+REV','WAH+DIST+REV','SMALL ROOM','LARGE ROOM','HALL REVERB2','SMALL PLATE','LARGE PLATE','REVRSE REVRB','REVRSE REVB2','GATED REVERB','NLIN REVRB 1','NLIN REVRB 2','NLIN REVRB 3','MULTITAP DDL','EQ+DELAY LFO','VCF+DISTORT','GUITAR AMP1','GUITAR AMP2','GUITAR AMP3','SPKR CABINET','TUNABLE SPKR','EQ+CHOR+DDL','EQ+VIBR+DDL','EQ+FLNGR+DDL','EQ+TREM+DDL','PHASER+DDL','8-VOICE CHOR','PITCH SHIFT','PITCH+DDL','FAST PITCHSH','EQ+CMPRESSOR','EXPANDER','KEYED EXPNDR','INVRS EXPNDR','DE-ESSER','DUCKER','RUMBLE FILTR','PARAM EQ','VAN DER POL']

def param(name, effect_id, values, gpr, raw=None, evidence='', tags=None):
    return {'name':name,'scope':'effect_specific','available_control':True,'displayed_values_observed':values,'default':None,'range':{'minimum':None,'maximum':None,'step':None},'dsp_mapping':{'status':'experimentally_verified','register_type':'GPR','address':f'0x{gpr:02X}','observed_raw_values':raw,'evidence':evidence},'possible_influence':{'categories':tags or [],'basis':'parameter name only; DSP function not independently established'}}

def seed():
    effects=[]
    for i,name in enumerate(NAMES,1):
        ps=[]
        if i==2: ps=[param('REVERB MIX BUS2',2,['25','26'],0x7a,['0x350000','0x370000','0x350000','0x370000'],'Repeated Up/Down/Up with no-edit control; emulator host writes to GPR 0x7A followed the reversible display cycle. See redacted ROM-02 mapping report.', ['routing','wet_dry_mix'])]
        if i==49: ps=[param('BASS GAIN',49,['+3','+4','+3','+4'],0x56,['0x00B500','0x00CB00','0x00B500','0x00CB00'],'Repeated Up/Down/Up with no-edit control; emulator host writes to GPR 0x56 followed the display cycle. See ASR10_PARAMETER_MAPPING.md.', ['frequency_response','gain'])]
        effects.append({'id':i,'display_name':name,'name_source':'OS 3.53 running-display inventory; redacted public catalog','parameter_enumeration_status':'partial' if ps else 'not_enumerated','parameters':ps,'unobserved_controls':None if not ps else 'Additional controls not enumerated; complete count unknown'})
    return {'schema':SCHEMA,'os_version':'3.53','effect_count_observed':50,'parameter_count_observed':2,'coverage_note':'The 50 display names are catalogued. Only two controls have public, reversible mapping evidence. Other parameter names, displayed values, defaults, ranges, and mappings are unknown and intentionally omitted.','effects':effects}

def parse_display(log_text):
    """Extract complete NAME=VALUE display rows; intentionally discard timing/PC/raw log context."""
    rows=[]
    for line in log_text.splitlines():
        m=re.match(r'^\s*\[\s*[0-9.]+s\]\s*\|([^|]*)\|\s*$',line)
        if not m: continue
        text=m.group(1).strip()
        if '=' not in text: continue
        name,value=(part.strip() for part in text.split('=',1))
        if not name or not value or not re.fullmatch(r'[A-Z0-9 +_./#-]{2,32}',name): continue
        if value.startswith('ROM-'): continue
        rows.append({'name':name,'displayed_value':value})
    # Preserve order but discard repeated unchanged refreshes.
    out=[]
    for r in rows:
        if not out or out[-1]!=r: out.append(r)
    return out

def validate(doc):
    errors=[]
    if doc.get('schema')!=SCHEMA: errors.append('schema mismatch')
    effects=doc.get('effects')
    if not isinstance(effects,list) or len(effects)!=50: errors.append('must contain exactly 50 effect entries'); effects=[]
    ids=[e.get('id') for e in effects]
    if ids!=list(range(1,51)): errors.append('effect IDs must be contiguous 1..50 in order')
    if len({e.get('display_name') for e in effects})!=len(effects): errors.append('effect display names must be unique')
    for e in effects:
        if e.get('parameter_enumeration_status') not in ('complete','partial','not_enumerated'): errors.append(f"effect {e.get('id')}: invalid enumeration status")
        for p in e.get('parameters',[]):
            if not all(k in p for k in ('name','displayed_values_observed','default','range','available_control','dsp_mapping','possible_influence')): errors.append(f"effect {e.get('id')}: incomplete parameter record")
            mp=p['dsp_mapping']
            if mp.get('status')=='experimentally_verified' and not mp.get('address'): errors.append(f"effect {e.get('id')} {p.get('name')}: verified mapping lacks address")
    if doc.get('effect_count_observed')!=len(effects): errors.append('effect_count_observed does not match effect list')
    if doc.get('parameter_count_observed')!=sum(len(e.get('parameters',[])) for e in effects): errors.append('parameter_count_observed does not match records')
    return errors

def enum_intake(doc, effect_id, log_text):
    if not 1<=effect_id<=50: raise ValueError('effect ID must be 1..50')
    rows=parse_display(log_text)
    if not rows: raise ValueError('no parameter display rows found; expected timestamped [t] |NAME=VALUE| lines')
    effect=doc['effects'][effect_id-1]
    for row in rows:
        p=next((x for x in effect['parameters'] if x['name']==row['name']),None)
        if p is None:
            p={'name':row['name'],'scope':'effect_specific_unconfirmed','available_control':True,'displayed_values_observed':[],'default':None,'range':{'minimum':None,'maximum':None,'step':None},'dsp_mapping':{'status':'unknown','register_type':None,'address':None,'observed_raw_values':None,'evidence':None},'possible_influence':{'categories':[],'basis':'unknown'}}
            effect['parameters'].append(p)
        if row['displayed_value'] not in p['displayed_values_observed']: p['displayed_values_observed'].append(row['displayed_value'])
    effect['parameter_enumeration_status']='partial'; effect['unobserved_controls']='Remaining controls and full ranges/defaults not established by this display log.'
    doc['parameter_count_observed']=sum(len(e['parameters']) for e in doc['effects'])
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__); s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('seed'); q.add_argument('--output',required=True)
    q=s.add_parser('validate'); q.add_argument('catalog')
    q=s.add_parser('enumerate'); q.add_argument('--catalog',required=True); q.add_argument('--effect-id',type=int,required=True); q.add_argument('--display-log',required=True); q.add_argument('--output',required=True)
    a=p.parse_args()
    if a.cmd=='seed':
        d=seed(); pathlib.Path(a.output).write_text(json.dumps(d,indent=2)+'\n'); print(json.dumps({'effects':50,'parameters':2,'valid':not validate(d)}))
    elif a.cmd=='validate':
        d=json.loads(pathlib.Path(a.catalog).read_text()); errs=validate(d); print(json.dumps({'valid':not errs,'errors':errs,'effects':len(d.get('effects',[])),'parameters':sum(len(e.get('parameters',[])) for e in d.get('effects',[]))},indent=2)); return int(bool(errs))
    else:
        d=json.loads(pathlib.Path(a.catalog).read_text()); rows=enum_intake(d,a.effect_id,pathlib.Path(a.display_log).read_text(errors='replace')); errs=validate(d)
        if errs: raise SystemExit('; '.join(errs))
        pathlib.Path(a.output).write_text(json.dumps(d,indent=2)+'\n'); print(json.dumps({'effect_id':a.effect_id,'parsed_rows':len(rows),'catalog_parameters':d['parameter_count_observed'],'output':a.output}))
    return 0
if __name__=='__main__': raise SystemExit(main())
