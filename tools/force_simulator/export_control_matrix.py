"""Export the current effect/control capability matrix for QA handoffs."""
import csv, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from parameter_registry import load_registry

out=ROOT/'docs/force_simulator/factory-control-mapping-matrix.csv'
with out.open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=['slot','factory_effect','catalog_parameters','runtime_additions','editor_controls','pc_banks','native_vst_route_count','v05_runtime_ready_count','partial_count','unmapped_count','native_routes'],lineterminator='\n')
    writer.writeheader()
    for effect in load_registry():
        controls=effect['controls'];routes=[c for c in controls if c['route']]
        writer.writerow({'slot':effect['slot'],'factory_effect':effect['name'],'catalog_parameters':sum(c['catalog_descriptor'] for c in controls),
            'runtime_additions':sum(not c['catalog_descriptor'] for c in controls),'editor_controls':len(controls),
            'pc_banks':max(1,(len(controls)+7)//8),'native_vst_route_count':len(routes),
            'v05_runtime_ready_count':sum(c['v05_runtime_ready'] for c in controls),
            'partial_count':sum(c['status']=='PARTIAL' for c in controls),
            'unmapped_count':sum(c['status']=='UNMAPPED' for c in controls),
            'native_routes':'; '.join(f"{c['name']} -> host {c['route']['host_parameter_index']} bank {c['route']['bank']+1} [{','.join(map(str,c['route']['point_values']))}]" for c in routes)})
print(out)
