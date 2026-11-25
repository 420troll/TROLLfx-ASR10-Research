#!/usr/bin/env python3
"""Independent, read-only inspector for generated Akai Force skin bundles.

The preview is an approximate overlay on the supplied background. It does not
emulate MPC/Force rendering, font metrics, focus, Q-Link overlays, or scaling.
"""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

CANVAS = (1280, 628)
GRID = [(23,45),(343,45),(663,45),(983,45),(23,196),(343,196),(663,196),(983,196),
        (23,346),(343,346),(663,346),(983,346),(23,497),(343,497),(663,497),(983,497)]
SIZE = (278,107)

def bounds(component):
    raw = component.get('bounds', {}).get('bounds', '')
    try:
        vals = tuple(float(v) for v in raw.split())
        return vals if len(vals) == 4 else None
    except (TypeError, ValueError):
        return None

def param_index(component):
    for entry in component.get('handle remapping', {}).get('map', []):
        m = re.fullmatch(r'Parameter (\d+)', str(entry.get('value','')))
        if m: return int(m.group(1))
    return None

def expected_qlink(position):
    if not position: return None
    x,y,_,_=position
    for i,(gx,gy) in enumerate(GRID):
        if abs(x-gx)<=1 and abs(y-gy)<=1:
            row,col=divmod(i,4)
            return 13+col-4*row
    return None

def sha_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()

def sha_tree(path):
    root=Path(path); h=hashlib.sha256()
    for p in sorted(x for x in root.rglob('*') if x.is_file()):
        h.update(p.relative_to(root).as_posix().encode()+b'\0'); h.update(bytes.fromhex(sha_file(p)))
    return h.hexdigest()

def analyze(ui_path, tui_path, qlinks_path, asset_dir, params_path=None, registry_header=None):
    ui=json.loads(Path(ui_path).read_text()); tui=json.loads(Path(tui_path).read_text())['pageData']
    qlinks=json.loads(Path(qlinks_path).read_text())['Screen Mode Q-Links']['map']
    params=json.loads(Path(params_path).read_text()) if params_path else None
    pages={p['name']:p for p in ui.get('pages',[])}
    registry={}
    if registry_header:
        for m in re.finditer(r'\{(\d+),\s*(\d+),\s*"([^"]+)",\s*"([^"]+)"\}',Path(registry_header).read_text()):
            registry[int(m.group(1))]=(int(m.group(2)),m.group(3),m.group(4))
    tabs=tui.get('tabs',[]); findings=[]; page_rows=[]; control_rows=[]
    by_tab={int(x['fnKeyIndex'])+1:x for x in tabs}
    all_refs=set()
    for ti, tab in enumerate(tabs):
        name=tab.get('tabName',f'tab{ti}')
        components=tab.get('componentDefinition',{}).get('componentsData',[])
        page=pages.get(name,{}); controls=page.get('controls',[])
        assigned=qlinks[ti].get('Q-Links',{}) if ti < len(qlinks) else {}
        qlink_targets={int(v) for v in assigned.values() if isinstance(v,int) and v >= 0}
        param_widgets=defaultdict(list); text_count=0
        for ci,c in enumerate(components):
            cd=c.get('componentData',{}); data=cd.get('data',{}); typ=cd.get('type','')
            b=bounds(c); idx=param_index(c); label=cd.get('name','')
            bdata=c.get('bounds',{})
            invalidators=bdata.get('additionalInvalidatingHandles',[])
            when=bdata.get('whenVisible','Always')
            if invalidators: when=';'.join(invalidators)
            remap=c.get('handle remapping',{}).get('map',[])
            for e in remap:
                if str(e.get('value','')).startswith('Parameter '): all_refs.add(e['value'])
            if b:
                x,y,w,h=b
                if x < 0 or y < 0 or x+w > CANVAS[0] or y+h > CANVAS[1]:
                    findings.append({'severity':'FAIL','code':'OUT_OF_BOUNDS','page':name,'widget':label,'bounds':b})
            if idx is not None: param_widgets[idx].append((label,when,typ,ci))
            expected=expected_qlink(b) if idx is not None else None
            if idx is not None and expected is None:
                findings.append({'severity':'WARN','code':'PARAMETER_WIDGET_OFF_Q_LINK_GRID','page':name,'widget':label,'parameter_index':idx,'bounds':b})
            elif idx is not None and assigned.get(f'Q-Link {expected}') != idx:
                findings.append({'severity':'FAIL','code':'QLINK_POSITION_BINDING_MISMATCH','page':name,'widget':label,'parameter_index':idx,'grid_qlink':expected,'assigned_target':assigned.get(f'Q-Link {expected}')})
            if idx is not None and registry and idx in registry:
                m=re.search(r'IndexedEnabling/(\d+)/50/Parameter 0',when)
                if m and int(m.group(1))+1 != registry[idx][0]:
                    findings.append({'severity':'FAIL','code':'CONTROL_WRONG_EFFECT','page':name,'widget':label,'parameter_index':idx,'visibility_slot':int(m.group(1))+1,'registry_slot':registry[idx][0]})
            txt=data.get('text')
            if txt:
                text_count+=1
                font=data.get('textStyle',{}).get('font',{}); height=font.get('height',20)
                # Conservative glyph-width estimate, explicitly not SDK font rendering.
                est_width=len(txt)*height*0.56
                if b and est_width > b[2]:
                    findings.append({'severity':'WARN','code':'TEXT_MAY_OVERFLOW','page':name,'widget':label,'text':txt,'estimated_width':round(est_width,1),'available_width':b[2],'metric':'approximate 0.56em; not SDK-rendered'})
            control_rows.append({'page':name,'widget':label,'type':typ,'parameter_index':idx,'bounds':b,'when_visible':when,'text':txt})
        for idx, ws in param_widgets.items():
            if len(ws)>1:
                findings.append({'severity':'WARN','code':'DUPLICATE_PARAMETER_WIDGET','page':name,'parameter_index':idx,'widgets':[x[0] for x in ws]})
            if idx not in qlink_targets:
                findings.append({'severity':'WARN','code':'PARAMETER_WIDGET_WITHOUT_QLINK','page':name,'parameter_index':idx,'widgets':[x[0] for x in ws]})
        targets=defaultdict(list)
        for qn,target in assigned.items():
            if isinstance(target,int) and target>=0: targets[target].append(qn)
        for target,qlist in targets.items():
            if len(qlist)>1:
                findings.append({'severity':'WARN','code':'DUPLICATE_QLINK_TARGET','page':name,'parameter_index':target,'qlinks':qlist})
        for qn, target in assigned.items():
            if not isinstance(target,int) or target < 0: continue
            if target not in param_widgets:
                findings.append({'severity':'FAIL','code':'QLINK_TARGET_MISSING_WIDGET','page':name,'qlink':qn,'parameter_index':target})
            elif any(w[1] != 'Always' for w in param_widgets[target]):
                findings.append({'severity':'WARN','code':'STATIC_QLINK_CONDITIONAL_WIDGET','page':name,'qlink':qn,'parameter_index':target,'widgets':[w[0] for w in param_widgets[target]],'detail':'Q-Link map remains assigned regardless of widget visibility'})
        page_rows.append({'page':name,'tab_index':ti+1,'widget_count':len(components),'text_widget_count':text_count,'qlink_assignments':{k:v for k,v in assigned.items() if isinstance(v,int) and v>=0},'parameter_widgets':{str(k):[{'name':w[0],'when_visible':w[1]} for w in v] for k,v in param_widgets.items()}})
    # Compare authored controls with generated names/counts, not pixels.
    if len(tabs)!=len(pages): findings.append({'severity':'FAIL','code':'PAGE_COUNT_MISMATCH','authored':len(pages),'generated':len(tabs)})
    if len(qlinks)!=len(tabs): findings.append({'severity':'FAIL','code':'QLINK_TAB_COUNT_MISMATCH','tabs':len(tabs),'maps':len(qlinks)})
    edit_targets={}
    for p in page_rows:
        if p['page'] in ('EDIT','EDIT 2'):
            edit_targets[p['page']]={idx for idx in p['parameter_widgets']}
    overlap=edit_targets.get('EDIT',set()) & edit_targets.get('EDIT 2',set())
    if overlap: findings.append({'severity':'FAIL','code':'EDITOR_BANK_DUPLICATE_BINDINGS','parameter_indices':sorted(int(x) for x in overlap)})
    skin=Path(asset_dir); refs=set()
    for c in tui.get('componentDefinitions',{}).get('localComponentDefinitions',[]):
        raw=json.dumps(c)
        refs.update(re.findall(r'"(?:image|onImage|offImage)"\s*:\s*"([^"]+\.png)"',raw))
    for tab in tabs:
        refs.update(re.findall(r'"(?:image|onImage|offImage)"\s*:\s*"([^"]+\.png)"',json.dumps(tab)))
    bg=ui.get('backgroundImage')
    if bg: refs.add(bg)
    missing=sorted(r for r in refs if not (skin/r).is_file())
    present={p.name for p in skin.glob('*') if p.is_file()}
    unreferenced=sorted(present-refs-{'TUI.json','Q-Links.json'})
    if missing: findings.append({'severity':'FAIL','code':'MISSING_ARTWORK','files':missing})
    if unreferenced: findings.append({'severity':'INFO','code':'UNREFERENCED_SKIN_FILES','files':unreferenced})
    if params:
        plist=params.get('params',params.get('parameters',[])) if isinstance(params,dict) else params
        names={int(p.get('index',p.get('id',-1))):p.get('name',p.get('title','')) for p in plist if isinstance(p,dict) and str(p.get('index',p.get('id',''))).isdigit()}
        for row in control_rows:
            idx=row['parameter_index']
            if idx is not None and names and idx not in names:
                findings.append({'severity':'FAIL','code':'PARAMETER_DESCRIPTOR_MISSING','page':row['page'],'widget':row['widget'],'parameter_index':idx})
            elif idx is not None and names:
                expected=str(names[idx] or '').strip(); actual=str(row['widget'] or '').strip()
                if not actual:
                    findings.append({'severity':'FAIL','code':'PARAMETER_LABEL_MISSING','page':row['page'],'parameter_index':idx})
                elif expected and actual.casefold()!=expected.casefold():
                    findings.append({'severity':'WARN','code':'PARAMETER_LABEL_MISMATCH','page':row['page'],'parameter_index':idx,'widget_label':actual,'descriptor_name':expected})
    return {'schema':'force-skin-independent-inspection-v1','canvas':{'width':CANVAS[0],'height':CANVAS[1]},'renderer':'approximate preview only; no genuine SDK screenshot produced','inputs':{'ui':{'file':Path(ui_path).name,'sha256':sha_file(ui_path)},'tui':{'file':Path(tui_path).name,'sha256':sha_file(tui_path)},'qlinks':{'file':Path(qlinks_path).name,'sha256':sha_file(qlinks_path)},'asset_directory_name':Path(asset_dir).name,'asset_tree_sha256':sha_tree(asset_dir),'parameter_descriptors':({'file':Path(params_path).name,'sha256':sha_file(params_path)} if params_path else None)},'pages':page_rows,'controls':control_rows,'findings':findings,'summary':dict(Counter(x['severity'] for x in findings))}

def render(report, asset_dir, out_dir):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError: return False
    out=Path(out_dir); out.mkdir(parents=True,exist_ok=True); bg=Path(asset_dir)/'panel_background.png'
    font=ImageFont.load_default()
    for page in report['pages']:
        im=Image.open(bg).convert('RGBA') if bg.exists() else Image.new('RGBA',CANVAS,(25,30,34,255))
        im=im.resize(CANVAS); layer=Image.new('RGBA',CANVAS,(0,0,0,0)); d=ImageDraw.Draw(layer,'RGBA')
        for c in report['controls']:
            if c['page']!=page['page'] or not c['bounds']: continue
            x,y,w,h=c['bounds']; box=(x,y,x+w,y+h)
            d.rounded_rectangle(box,radius=5,outline=(0,220,210,180),fill=(0,0,0,35),width=2)
            label=c['text'] or c['widget'] or (f"P{c['parameter_index']}" if c['parameter_index'] is not None else c['type'])
            if c['parameter_index'] is not None and not c['text']: label=f"P{c['parameter_index']} {label}"
            d.text((x+6,y+5),label[:50],font=font,fill=(235,255,252,255))
        im=Image.alpha_composite(im,layer); d=ImageDraw.Draw(im,'RGBA')
        d.text((8,8),f"APPROXIMATE LAYOUT — {page['page']} — not Force/SDK rendered",font=font,fill=(255,90,80,255))
        im.convert('RGB').save(out/f"{page['page'].lower().replace(' ','_')}.png")
    return True

def main():
    a=argparse.ArgumentParser(); a.add_argument('--ui',required=True); a.add_argument('--tui',required=True); a.add_argument('--qlinks',required=True); a.add_argument('--assets',required=True); a.add_argument('--params'); a.add_argument('--out',required=True); a.add_argument('--preview-dir')
    a.add_argument('--registry-header')
    x=a.parse_args(); r=analyze(x.ui,x.tui,x.qlinks,x.assets,x.params,x.registry_header); Path(x.out).parent.mkdir(parents=True,exist_ok=True); Path(x.out).write_text(json.dumps(r,indent=2)+'\n')
    if x.preview_dir and render(r,x.assets,x.preview_dir): print('approximate preview PNGs generated (not SDK rendered)')
    md=Path(x.out).with_suffix('.md'); lines=['# Generated Force Skin Inspection','',f"Renderer: {r['renderer']}",'',f"Findings: {r['summary']}",'','| Page | Widgets | Q-Link assignments |','|---|---:|---:|']
    for p in r['pages']: lines.append(f"| {p['page']} | {p['widget_count']} | {len(p['qlink_assignments'])} |")
    lines += ['', '## Findings','']+[f"- **{f['severity']} `{f['code']}`** — {json.dumps(f,sort_keys=True)}" for f in r['findings']]
    md.write_text('\n'.join(lines)+'\n'); print(f"{r['summary']} -> {x.out}")
if __name__=='__main__': main()
