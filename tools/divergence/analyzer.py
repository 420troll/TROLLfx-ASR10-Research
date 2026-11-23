#!/usr/bin/env python3
"""Import, compare, transform, and report ES5510 execution traces without filling missing observations."""
from __future__ import annotations
import argparse, csv, json, pathlib, re, sys
from collections import defaultdict, Counter

SCHEMA='trollfx-es5510-execution-trace-v1'
REPORT_SCHEMA='trollfx-es5510-divergence-report-v1'
TYPES={'instruction','register_write','special_write','firmware_write','ram_request','ram_read','ram_write','pipeline_state','serial_input','serial_output','serial_frame','end','state_transition','alu_state','mac_state','arithmetic_state'}

def valid_trace(t):
    err=[]
    if t.get('schema')!=SCHEMA: err.append('unsupported trace schema')
    if not isinstance(t.get('trace_id'),str) or not t['trace_id']: err.append('trace_id required')
    if not isinstance(t.get('source'),dict) or not t['source'].get('implementation'): err.append('source.implementation required')
    if not isinstance(t.get('timing'),dict): err.append('timing required')
    else:
        if 'sample_rate_hz' not in t['timing']: err.append('timing.sample_rate_hz required')
        if not t['timing'].get('frame_basis'): err.append('timing.frame_basis required')
    if not isinstance(t.get('events'),list): err.append('events must be a list')
    else:
        for n,e in enumerate(t['events']):
            if e.get('event_type') not in TYPES: err.append(f'events[{n}].event_type unsupported')
            if not isinstance(e.get('frame'),int) or e['frame']<0: err.append(f'events[{n}].frame must be nonnegative integer')
    return err

def new_trace(trace_id, implementation, sample_rate=44100, frame_basis='DSP frame counter', clock_hz=None, events=None, complete_event_types=None, metadata=None):
    return {'schema':SCHEMA,'trace_id':trace_id,'source':{'implementation':implementation,'identity':None},'timing':{'sample_rate_hz':sample_rate,'clock_hz':clock_hz,'frame_basis':frame_basis,'clock_basis':'unknown','alignment_assumption':'frame 0 compared directly; no automatic offset applied'},'coverage':{'complete_event_types':complete_event_types or [],'observed_event_types':sorted({e['event_type'] for e in (events or [])})},'initial_state':None,'initialization_manifest':None,'metadata':metadata or {},'events':events or []}

def import_csv(path, trace_id, implementation, sample_rate=44100, frame_basis='DSP frame counter', clock_hz=None):
    """Import the existing I/RQ/RR/RW/W/END/ROUTE diagnostic trace CSV."""
    events=[]; instr_seq=defaultdict(int)
    with open(path,newline='') as f:
        for rownum,row in enumerate(csv.reader(f),1):
            if not row: continue
            tag=row[0]
            try:
                if tag=='I' and len(row)>=4:
                    fr=int(row[1]); idx=instr_seq[fr]; instr_seq[fr]+=1
                    events.append({'frame':fr,'instruction_index':idx,'event_order':rownum,'event_type':'instruction','program_counter':int(row[2],16),'instruction_word':row[3]})
                elif tag=='RQ' and len(row)>=6:
                    fr=int(row[1]); events.append({'frame':fr,'instruction_index':instr_seq[fr]-1 if instr_seq[fr] else None,'event_order':rownum,'event_type':'ram_request','program_counter':int(row[2],16),'ram_cycle':int(row[3]),'ram_access':int(row[4]),'address':int(row[5],16)})
                elif tag=='RR' and len(row)>=6:
                    fr=int(row[1]); events.append({'frame':fr,'instruction_index':instr_seq[fr]-1 if instr_seq[fr] else None,'event_order':rownum,'event_type':'ram_read','program_counter':int(row[2],16),'io':bool(int(row[3])),'address':int(row[4],16),'value':int(row[5],16)})
                elif tag=='RW' and len(row)>=5:
                    fr=int(row[1]); events.append({'frame':fr,'instruction_index':instr_seq[fr]-1 if instr_seq[fr] else None,'event_order':rownum,'event_type':'ram_write','program_counter':int(row[2],16),'address':int(row[3],16),'value':int(row[4],16)})
                elif tag=='W' and len(row)>=5:
                    fr=int(row[1]); reg=int(row[3],16); typ='register_write' if reg<192 else 'special_write'
                    events.append({'frame':fr,'instruction_index':instr_seq[fr]-1 if instr_seq[fr] else None,'event_order':rownum,'event_type':typ,'program_counter':int(row[2],16),'register':reg,'value':int(row[4],16),'timing_semantics':'value observed after this emitted instruction boundary; producer instruction may be earlier due to pipeline'})
                elif tag=='END' and len(row)>=3:
                    events.append({'frame':int(row[1]),'instruction_index':instr_seq[int(row[1])]-1 if instr_seq[int(row[1])] else None,'event_order':rownum,'event_type':'end','program_counter':int(row[2],16)})
                elif tag=='ROUTE' and len(row)>=7:
                    events.append({'frame':int(row[1]),'event_order':rownum,'event_type':'serial_frame','input_left':int(row[2]),'input_right':int(row[3]),'output_left':int(row[4]),'output_right':int(row[5]),'host_serial':int(row[6],16),'coverage_note':'Existing harness records only first serial frame.'})
            except (ValueError,IndexError) as ex: raise ValueError(f'malformed {tag} row {rownum}: {ex}') from ex
    complete=['instruction','ram_request','ram_read','ram_write','register_write','special_write','end']
    t=new_trace(trace_id,implementation,sample_rate,frame_basis,clock_hz,events,complete,{'import_format':'existing-diagnostic-csv-v1','source_file_name':pathlib.Path(path).name,'cycle_precision':'not recorded','serial_frame_scope':'first frame only'})
    # RQ and RR are emitted for all instructions/read retirements in this diagnostic format.
    t['coverage']['complete_event_types'] += ['ram_request','ram_read']
    return t

def load_trace(path, **meta):
    p=pathlib.Path(path)
    if p.suffix.lower()=='.csv': return import_csv(p,**meta)
    t=json.loads(p.read_text())
    errors=valid_trace(t)
    if errors: raise ValueError('; '.join(errors))
    return t

def _identity(e):
    # Pair observations by required event class and occurrence order. Optional payload
    # fields (PC, register, sample index, etc.) are compared as data, not used as keys.
    return (e.get('event_type'),)

def _order_identity(e):
    return (e.get('event_type'),e.get('register'),e.get('port'),e.get('channel'),e.get('source'),e.get('program_counter'))

def _sort_key(e):
    return (e.get('frame',0), e.get('instruction_index') if e.get('instruction_index') is not None else 10**12, e.get('cycle') if e.get('cycle') is not None else 10**12, e.get('event_order',0))

def _event_fields(e): return {k:v for k,v in e.items() if k not in ('frame','event_order','timing_semantics','coverage_note')}
def _category(a,b):
    ts={a.get('event_type'),b.get('event_type')}
    if 'firmware_write' in ts: return 'missing_firmware_events'
    if 'state_transition' in ts: return 'initialization_state_differences'
    if ts & {'pipeline_state'}: return 'pipeline_state_differences'
    if ts & {'ram_request','ram_read','ram_write'}: return 'ram_address_data_differences'
    if ts & {'serial_input','serial_output','serial_frame'}: return 'serial_input_output_alignment'
    if ts & {'instruction','end','alu_state','mac_state','arithmetic_state'}: return 'arithmetic_or_execution_differences'
    if ts & {'register_write','special_write'}: return 'register_write_ordering'
    return 'insufficient_evidence'

def compare(left,right, max_frame_offset=2):
    for t in (left,right):
        errs=valid_trace(t)
        if errs: raise ValueError('; '.join(errs))
    l=sorted(left['events'],key=_sort_key); r=sorted(right['events'],key=_sort_key)
    ld=defaultdict(list); rd=defaultdict(list)
    for e in l: ld[(e['frame'],_identity(e))].append(e)
    for e in r: rd[(e['frame'],_identity(e))].append(e)
    findings=[]; unknown=[]; matches=0; keys=sorted(set(ld)|set(rd),key=lambda k:(k[0],str(k[1])))
    li,ri=left.get('initial_state'),right.get('initial_state')
    if isinstance(li,dict) and isinstance(ri,dict):
        for field in sorted(set(li)&set(ri)):
            if li[field]!=ri[field]: findings.append({'status':'confirmed_mismatch','category':'initialization_state_differences','kind':'initial_state_field_mismatch','frame':0,'field':field,'left':li[field],'right':ri[field]})
        absent=sorted(set(li)^set(ri))
        if absent: unknown.append({'initial_state_fields_not_comparable':absent})
    elif li is None or ri is None: unknown.append({'initial_state':'one or both traces omit initial_state'})
    lm,rm=left.get('initialization_manifest'),right.get('initialization_manifest')
    if lm is not None and rm is not None and lm!=rm: findings.append({'status':'potential_mismatch','category':'initialization_state_differences','kind':'initialization_manifest_metadata_differs','frame':0,'left':lm,'right':rm,'reason':'manifest metadata differs; payload bytes are not interpreted here'})
    lc=set(left.get('coverage',{}).get('complete_event_types',[])); rc=set(right.get('coverage',{}).get('complete_event_types',[]))
    for key in keys:
        aa=ld.get(key,[]); bb=rd.get(key,[]); typ=key[1][0]
        if not aa or not bb:
            present_events=aa or bb; confirmed=typ in (lc&rc); present_side='left' if aa else 'right'; missing_side='right' if aa else 'left'
            opposite=rd if aa else ld
            for present in present_events:
                shifted=any(_event_fields(present)==_event_fields(other) and abs(other_frame-key[0])<=2 and other_frame!=key[0]
                            for (other_frame,other_ident),vals in opposite.items() if other_ident==key[1] for other in vals)
                if shifted: continue
                findings.append({'status':'confirmed_mismatch' if confirmed else 'potential_mismatch','category':'missing_firmware_events' if typ=='firmware_write' else _category(present,present),'kind':'extra_or_missing_event','frame':key[0],'event_type':typ,'identity':list(key[1]),'present_side':present_side,'missing_side':missing_side,'supporting_entries':{'left':present if aa else None,'right':present if bb else None},'reason':'event type is claimed complete on both traces' if confirmed else 'trace coverage does not establish this event absence'})
        else:
            for ix in range(max(len(aa),len(bb))):
                if ix>=len(aa) or ix>=len(bb):
                    present=(aa if ix<len(aa) else bb)[ix]; absent_side='right' if ix<len(aa) else 'left'
                    confirmed=typ in (lc&rc)
                    findings.append({'status':'confirmed_mismatch' if confirmed else 'potential_mismatch','category':'missing_firmware_events' if typ=='firmware_write' else _category(present,present),'kind':'extra_or_missing_event','frame':key[0],'event_type':typ,'identity':list(key[1]),'present_side':'left' if ix<len(aa) else 'right','missing_side':absent_side,'supporting_entries':{'left':aa[ix] if ix<len(aa) else None,'right':bb[ix] if ix<len(bb) else None},'reason':'event type is claimed complete on both traces' if confirmed else 'trace coverage does not establish this event absence'}); continue
                x,y=aa[ix],bb[ix]; xf,yf=_event_fields(x),_event_fields(y); common=sorted(set(xf)&set(yf)); diff={k:{'left':xf[k],'right':yf[k]} for k in common if xf[k]!=yf[k]}
                missing=sorted(set(xf)^set(yf))
                if diff:
                    kind='write_phase_mismatch' if set(diff)=={'timing_phase'} else ('instruction_boundary_offset' if set(diff)=={'instruction_index'} and x.get('cycle') is None and y.get('cycle') is None else ('instruction_cycle_offset' if set(diff)=={'cycle'} else 'field_mismatch'))
                    findings.append({'status':'confirmed_mismatch','category':'register_write_ordering' if typ=='firmware_write' else _category(x,y),'kind':kind,'frame':key[0],'instruction_index':x.get('instruction_index',y.get('instruction_index')),'event_type':typ,'identity':list(key[1]),'differing_fields':diff,'supporting_entries':{'left':x,'right':y}})
                else:
                    matches+=1
                    if missing: unknown.append({'frame':key[0],'event_type':typ,'identity':list(key[1]),'fields_not_comparable':missing,'left':x,'right':y})
    # Detect same semantic event shifted in frame with identical observed payload.
    for side,own,other in [('left',ld,rd)]:
        for (fr,ident),events in own.items():
            if (fr,ident) in other: continue
            candidate=next(((of,other[(of,ident)]) for of in range(max(0,fr-max_frame_offset),fr+max_frame_offset+1) if of!=fr and (of,ident) in other),None)
            if not candidate: continue
            of,oe=candidate; e=events[0]; o=candidate[1][0]
            if _event_fields(e)==_event_fields(o):
                findings.append({'status':'confirmed_mismatch' if ident[0] in (lc&rc) else 'potential_mismatch','category':'register_write_ordering' if ident[0] in ('register_write','special_write','firmware_write') else _category(e,o),'kind':'frame_offset','frame':min(fr,of),'event_type':ident[0],'identity':list(ident),'frame_offset':(of-fr if side=='left' else fr-of),'left_frame':fr if side=='left' else of,'right_frame':of if side=='left' else fr,'supporting_entries':{'left':e if side=='left' else o,'right':o if side=='left' else e},'reason':'same observed event/value appears at a different DSP frame; frame timestamps only'})
    # Order analysis within frames: compare common event identities in occurrence order.
    for fr in sorted({e['frame'] for e in l}|{e['frame'] for e in r}):
        lorder=[_order_identity(e) for e in l if e['frame']==fr]; rorder=[_order_identity(e) for e in r if e['frame']==fr]; common=set(lorder)&set(rorder); lcommon=[x for x in lorder if x in common]; rcommon=[x for x in rorder if x in common]
        if lcommon!=rcommon and lcommon and rcommon:
            findings.append({'status':'confirmed_mismatch' if all(x[0] in (lc&rc) for x in common) else 'potential_mismatch','category':'register_write_ordering','kind':'same_frame_event_order','frame':fr,'left_order':[list(x) for x in lcommon],'right_order':[list(x) for x in rcommon],'reason':'event order differs within a frame; no instruction-cycle time is inferred'})
    # Compare serial samples by stream order as well as explicit sample index.
    for typ in ('serial_input','serial_output'):
        ls=defaultdict(list); rs=defaultdict(list)
        for e in l:
            if e.get('event_type')==typ: ls[(e.get('port'),e.get('channel'))].append(e)
        for e in r:
            if e.get('event_type')==typ: rs[(e.get('port'),e.get('channel'))].append(e)
        for group in set(ls)&set(rs):
            aa,bb=ls[group],rs[group]
            for ix,(x,y) in enumerate(zip(aa,bb)):
                if x.get('sample_index') is not None and y.get('sample_index') is not None and x['sample_index']!=y['sample_index']:
                    confirmed=typ in (lc&rc)
                    findings.append({'status':'confirmed_mismatch' if confirmed else 'potential_mismatch','category':'serial_input_output_alignment','kind':'serial_sample_index_mismatch','frame':min(x['frame'],y['frame']),'sequence_position':ix,'left_sample_index':x['sample_index'],'right_sample_index':y['sample_index'],'supporting_entries':{'left':x,'right':y},'reason':'paired serial stream positions refer to different sample indices'})
            for side,seq in (('left',aa),('right',bb)):
                repeated=[e for prev,e in zip(seq,seq[1:]) if e.get('sample_index') is not None and e['sample_index']==prev.get('sample_index')]
                if repeated:
                    other=bb if side=='left' else aa
                    other_dups={e.get('sample_index') for prev,e in zip(other,other[1:]) if e.get('sample_index') is not None and e['sample_index']==prev.get('sample_index')}
                    unique=[e for e in repeated if e.get('sample_index') not in other_dups]
                    for e in unique:
                        findings.append({'status':'potential_mismatch','category':'serial_input_output_alignment','kind':'repeated_serial_sample_index','frame':e['frame'],'side':side,'event_type':typ,'supporting_entry':e,'reason':'sample index repeats on one side only; confirm capture indexing and frame boundaries'})
    # Metadata differences are explicit observations, never automatic resampling/alignment.
    meta=[]
    for field in ('sample_rate_hz','frame_basis','clock_hz','clock_basis'):
        a=left['timing'].get(field); b=right['timing'].get(field)
        if a!=b: meta.append({'field':field,'left':a,'right':b})
    if meta: findings.append({'status':'confirmed_mismatch','category':'serial_input_output_alignment','kind':'timing_basis_mismatch','frame':0,'differing_metadata':meta,'reason':'traces use different timing metadata; samples/frames were not resampled or shifted'})
    findings.sort(key=lambda f:(f.get('frame',0), f.get('instruction_index') if f.get('instruction_index') is not None else 10**12, 0 if f['status']=='confirmed_mismatch' else 1, f['kind']))
    confirmed=[f for f in findings if f['status']=='confirmed_mismatch']; first=confirmed[0] if confirmed else None
    categories=sorted({f['category'] for f in findings})
    missing_types=sorted((set(left.get('coverage',{}).get('observed_event_types',[]))|set(right.get('coverage',{}).get('observed_event_types',[])))-lc-rc)
    if missing_types: unknown.append({'coverage_not_declared_complete_for':missing_types})
    timeline=[]
    if first:
        f0=first.get('frame',0); lo=max(0,f0-1); hi=f0+1
        for side,events in [('left',l),('right',r)]:
            for e in events:
                if lo<=e.get('frame',0)<=hi: timeline.append({'side':side,**e})
        timeline.sort(key=lambda e:(e.get('frame',0),e.get('instruction_index') if e.get('instruction_index') is not None else 10**12,e.get('event_order',0),e['side']))
    return {'schema':REPORT_SCHEMA,'trace_pair':{'left':{'trace_id':left['trace_id'],'implementation':left['source']['implementation'],'identity':left['source'].get('identity')},'right':{'trace_id':right['trace_id'],'implementation':right['source']['implementation'],'identity':right['source'].get('identity')}},'alignment':{'automatic_alignment':False,'assumption':'frame 0 compared directly','left_timing':left['timing'],'right_timing':right['timing']},'identical_observations_compared':matches,'unknown_comparisons':unknown,'findings':findings,'timeline_around_first_divergence':timeline,'earliest_confirmed_divergence':first,'supported_categories':categories,'classification':'divergence_observed' if first else ('potential_divergence' if findings else ('insufficient_evidence' if unknown else 'no_observed_divergence')),'limitations':['No DSP arithmetic is inferred from absent fields.','Frame-level timestamps do not establish instruction-cycle timing.','No transformation is treated as a correction without independent execution and output validation.']}

def transform(trace, actions):
    t=json.loads(json.dumps(trace)); notes=[]
    for action in actions:
        kind=action['kind']
        if kind=='shift_gpr_frame':
            reg=int(action['register']); delta=int(action['frames']); found=0
            for e in t['events']:
                if e['event_type']=='register_write' and e.get('register')==reg: e['frame']+=delta; found+=1
            notes.append({'kind':kind,'register':reg,'frames':delta,'events_changed':found})
        elif kind=='shift_event_boundary':
            idx=int(action['event_index']); delta=int(action['boundaries'])
            if not 0<=idx<len(t['events']) or t['events'][idx].get('instruction_index') is None: raise ValueError('selected event has no instruction-boundary observation; no cycle inferred')
            t['events'][idx]['instruction_index']+=delta
            notes.append({'kind':kind,'event_index':idx,'boundaries':delta})
        elif kind=='swap_event_order':
            fr=int(action['frame']); indices=[i for i,e in enumerate(t['events']) if e['frame']==fr]; a=int(action['first_index']); b=int(action['second_index'])
            if max(a,b)>=len(indices): raise ValueError('same-frame event index out of range')
            t['events'][indices[a]],t['events'][indices[b]]=t['events'][indices[b]],t['events'][indices[a]]
            ea,eb=t['events'][indices[a]],t['events'][indices[b]]; ea['event_order'],eb['event_order']=eb.get('event_order',0),ea.get('event_order',0)
            notes.append({'kind':kind,'frame':fr,'indices':[a,b]})
        elif kind=='only_gpr_writes':
            regs={int(v) for v in action['registers']}; before=len(t['events']); t['events']=[e for e in t['events'] if e['event_type'] not in ('register_write','special_write') or e.get('register') in regs]
            notes.append({'kind':kind,'registers':sorted(regs),'events_removed':before-len(t['events'])})
        elif kind=='initial_state_only':
            before=len(t['events']); t['events']=[e for e in t['events'] if e['event_type'] not in ('firmware_write','register_write','special_write')]
            notes.append({'kind':kind,'events_removed':before-len(t['events'])})
        else: raise ValueError('unknown transformation: '+kind)
    t['diagnostic_transformations']=notes
    t['trace_id']=t['trace_id']+' [diagnostic hypothesis]'
    return t

def markdown(report):
    first=report.get('earliest_confirmed_divergence'); lines=['# ES5510 trace divergence report','',f"Classification: **{report['classification']}**",'']
    lines += [f"Left: `{report['trace_pair']['left']['trace_id']}` ({report['trace_pair']['left']['implementation']})",f"Right: `{report['trace_pair']['right']['trace_id']}` ({report['trace_pair']['right']['implementation']})",'']
    if first:
        lines += ['## Earliest confirmed divergence','',f"- Frame: {first.get('frame')}",f"- Category: `{first['category']}`",f"- Kind: `{first['kind']}`",f"- Event: `{first.get('event_type','metadata')}`",f"- Reason: {first.get('reason','Observed field values differ.')}",'','Supporting entries:', '```json',json.dumps(first.get('supporting_entries',first.get('differing_metadata',{})),indent=2),'```','']
    else: lines += ['No confirmed divergence was established from comparable observations.','']
    if report.get('timeline_around_first_divergence'):
        lines += ['## Timeline around first mismatch','', '| Side | Frame | Boundary | Type | Key observation |','|---|---:|---:|---|---|']
        for e in report['timeline_around_first_divergence']:
            detail=e.get('register',e.get('program_counter',e.get('address',e.get('value','')))); lines.append(f"| {e['side']} | {e['frame']} | {e.get('instruction_index','')} | {e['event_type']} | {detail} |")
        lines.append('')
    lines += ['## Findings','', '| Status | Frame | Category | Finding |','|---|---:|---|---|']
    for f in report['findings']: lines.append(f"| {f['status']} | {f.get('frame','')} | `{f['category']}` | {f['kind']} |")
    lines += ['', '## Missing observations and limits','']
    if report['unknown_comparisons']:
        for u in report['unknown_comparisons']: lines.append(f"- {json.dumps(u,sort_keys=True)}")
    else: lines.append('- No missing fields were encountered among compared event pairs.')
    for x in report['limitations']: lines.append('- '+x)
    return '\n'.join(lines)+'\n'

def write_svg(left,right,path):
    ev=[('left',e) for e in left['events']]+[('right',e) for e in right['events']]; ev.sort(key=lambda z:(z[1]['frame'],z[0],z[1].get('event_order',0)))
    types=sorted({e['event_type'] for _,e in ev}); maxf=max([e['frame'] for _,e in ev] or [1]); h=50+len(types)*24; w=900
    ys={t:35+i*24 for i,t in enumerate(types)}; rows=['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="%d">'%h,'<rect width="100%" height="100%" fill="white"/>','<text x="10" y="20" font-size="14">Event frame timeline (left blue, right red; frame only)</text>']
    for t,y in ys.items(): rows += [f'<text x="5" y="{y+4}" font-size="10">{t}</text>',f'<line x1="100" y1="{y}" x2="890" y2="{y}" stroke="#ddd"/>']
    for side,e in ev:
        x=100+int(e['frame']/max(1,maxf)*780); col='#2878b5' if side=='left' else '#c44'; y=ys[e['event_type']]; rows.append(f'<circle cx="{x}" cy="{y}" r="3" fill="{col}"/>')
    rows.append('</svg>'); pathlib.Path(path).write_text('\n'.join(rows))

def main():
    p=argparse.ArgumentParser(description=__doc__); s=p.add_subparsers(dest='cmd',required=True)
    q=s.add_parser('import-csv'); q.add_argument('csv'); q.add_argument('--trace-id',required=True); q.add_argument('--implementation',required=True); q.add_argument('--sample-rate',type=int,default=44100); q.add_argument('--frame-basis',default='DSP frame counter'); q.add_argument('--clock-hz',type=float); q.add_argument('--output',required=True)
    q=s.add_parser('compare'); q.add_argument('left'); q.add_argument('right'); q.add_argument('--left-id',default='left'); q.add_argument('--left-implementation',default='unknown'); q.add_argument('--right-id',default='right'); q.add_argument('--right-implementation',default='unknown'); q.add_argument('--sample-rate',type=int,default=44100); q.add_argument('--json',required=True); q.add_argument('--markdown'); q.add_argument('--svg')
    q=s.add_parser('experiment'); q.add_argument('trace'); q.add_argument('actions'); q.add_argument('--output',required=True)
    a=p.parse_args()
    if a.cmd=='import-csv':
        t=import_csv(a.csv,a.trace_id,a.implementation,a.sample_rate,a.frame_basis,a.clock_hz); pathlib.Path(a.output).write_text(json.dumps(t,indent=2)+'\n')
    elif a.cmd=='experiment':
        t=json.loads(pathlib.Path(a.trace).read_text()); acts=json.loads(pathlib.Path(a.actions).read_text()); out=transform(t,acts); pathlib.Path(a.output).write_text(json.dumps(out,indent=2)+'\n')
    else:
        def get(x,id,impl):
            if pathlib.Path(x).suffix.lower()=='.csv': return import_csv(x,id,impl,a.sample_rate)
            return load_trace(x)
        l=get(a.left,a.left_id,a.left_implementation); r=get(a.right,a.right_id,a.right_implementation); report=compare(l,r); pathlib.Path(a.json).write_text(json.dumps(report,indent=2)+'\n')
        if a.markdown: pathlib.Path(a.markdown).write_text(markdown(report))
        if a.svg: write_svg(l,r,a.svg)
        print(json.dumps({'classification':report['classification'],'earliest_confirmed_divergence':report['earliest_confirmed_divergence']},indent=2))
if __name__=='__main__': main()
