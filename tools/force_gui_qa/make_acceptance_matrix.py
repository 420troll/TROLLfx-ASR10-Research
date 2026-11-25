#!/usr/bin/env python3
"""Emit effect-level and available-control V3/V4 acceptance rows."""
import argparse,csv,json,re
from pathlib import Path
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--coverage',required=True); ap.add_argument('--registry-header',required=True); ap.add_argument('--out',required=True); ap.add_argument('--candidate',default='V3 baseline; V4 pending'); a=ap.parse_args()
 coverage=json.loads(Path(a.coverage).read_text()); src=Path(a.registry_header).read_text()
 controls=[]
 for m in re.finditer(r'\{(\d+),\s*(\d+),\s*"([^"]+)",\s*"([^"]+)"\}',src):
  idx,slot,pid,label=m.groups(); idx=int(idx);slot=int(slot)
  controls.append({'row_type':'control','slot':slot,'effect':next((e['factory_effect'] for e in coverage['effects'] if e['slot']==slot),''),'control_id':pid,'label':label,'parameter_index':idx,'page':'EDIT' if idx<=23 else 'EDIT 2','bank':'1' if idx<=23 else '1','qlink':int(idx)-7 if idx<=23 else int(idx)-23,'visibility_vs_effect':'FAIL: Q-Link map is static while control visibility is effect-conditional','physical_q_link_to_dsp':'NOT TESTED','save_reload_and_reverse':'NOT TESTED','candidate':a.candidate})
 rows=[]
 for e in coverage['effects']:
  rows.append({'row_type':'effect','slot':e['slot'],'effect':e['factory_effect'],'control_id':'','label':'','parameter_index':'','page':'','bank':'','qlink':'','visibility_vs_effect':'PASS: no conditional V3 control assignment' if not e['register_mapped_control_count'] else 'FAIL: see control rows','physical_q_link_to_dsp':'NOT TESTED','save_reload_and_reverse':'NOT TESTED','candidate':a.candidate})
 rows += controls
 out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['row_type','slot','effect','control_id','label','parameter_index','page','bank','qlink','visibility_vs_effect','physical_q_link_to_dsp','save_reload_and_reverse','candidate'],lineterminator='\n');w.writeheader();w.writerows(rows)
 print(f'{len(coverage["effects"])} effects and {len(controls)} mapped controls -> {out}')
if __name__=='__main__':main()
