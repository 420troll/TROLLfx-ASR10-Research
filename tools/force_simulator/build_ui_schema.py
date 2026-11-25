"""Build the PC presentation schema from Codex 1 metadata and the supplied manual PDF.

DSP evidence remains a separate namespace. The PDF is an optional build input; the
checked-in schema is runtime data and does not require a PDF parser.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=HERE/'data/ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json'
CATALOG=ROOT/'docs/ASR10_FACTORY_PARAMETER_CATALOG_V1.json'
OUT=HERE/'data/ASR10_PC_EDITOR_PARAMETER_SCHEMA_V1.json'

def norm(s): return re.sub(r'[^a-z0-9]+',' ',s.casefold()).strip()
def extract_manual(pdf_path, labels):
    if not pdf_path: return {}, None
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise SystemExit('Install pypdf to build manual descriptions: python3 -m pip install pypdf') from e
    reader=PdfReader(str(pdf_path)); pages=[]
    # Printed Section 6 begins on PDF page 98 and ends at printed page 47 / PDF 153.
    for p in reader.pages[97:153]: pages.append(p.extract_text() or '')
    text='\n'.join(pages)
    # Remove repeating page headers while preserving parameter paragraphs.
    text=re.sub(r'Section 6\s*[—-]\s*Effect Parameters',' ',text,flags=re.I)
    text=re.sub(r'ASR-10 Musician.?s Manual',' ',text,flags=re.I)
    candidates=[]
    for label in labels:
        words=re.escape(label).replace(r'\ ',r'\s+')
        # Match the manual's parameter heading only when a Range follows it.
        pat=re.compile(r'(?<![A-Za-z0-9])('+words+r')(?:[^\n]{0,70}?)?\s+(?:Range|Ranges)\s*:\s*([^\n]+)',re.I)
        for m in pat.finditer(text):
            candidates.append((m.start(),m.end(),label,m.group(2).strip()))
    candidates.sort()
    descriptions={}
    # Multiple algorithms reuse a label at one exact text position; collapse those
    # hits before taking the next-heading boundary.
    by_start={}
    for hit in candidates:
        # When a generic label and a range-qualified variant start at the same
        # position, keep the longest exact heading so it defines one boundary.
        old=by_start.get(hit[0])
        if old is None or len(norm(hit[2]))>len(norm(old[2])): by_start[hit[0]]=hit
    candidates=sorted(by_start.values())
    for i,(start,end,label,rng) in enumerate(candidates):
        stop=candidates[i+1][0] if i+1<len(candidates) else min(len(text),end+1800)
        desc=text[end:stop]
        desc=re.sub(r'ROM[- ]\d{2}.*',' ',desc,flags=re.I|re.S)
        desc=re.sub(r'Section\s+\d+.*',' ',desc,flags=re.I|re.S)
        desc=re.sub(r'Edit/Effects Parameters\s+\d+.*$',' ',desc,flags=re.I)
        desc=' '.join(desc.split()).strip(' .\n-')
        # Keep only the first self-contained definition paragraph.
        if len(desc)>750: desc=desc[:747].rsplit(' ',1)[0]+'…'
        if desc and label not in descriptions: descriptions[label]=desc
    digest=hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
    return descriptions, {'filename':Path(pdf_path).name,'sha256':digest,'pdf_pages':len(reader.pages),'section6_pdf_pages':[98,153]}


MANUAL_PARAPHRASES={
 'PRE-DELAY TIME':'Delays the original signal before it enters the reverb; the displayed range is measured in milliseconds.',
 'DELAY TIME':'Sets the interval between delay repeats. The manual states that the left and right channels can be adjusted independently.',
 'PHASE WIDTH':'Sets how much modulation is applied to the phaser poles.',
 'PHASE DEPTH':'Sets the depth of the notches created by the phasing effect.',
 'FLANGE WIDTH':'Sets the range of the high-to-low frequency sweep in the flanger.',
 'FLANGE DEPTH':'Sets the depth of the notches created by the flanging effect.',
 'SPEAKER GAIN':'Sets the signal level sent to the rotary speaker; high settings can make the speaker sound damaged.',
 'DIST FLANGE RATE':'Sets the flanger notch-modulation rate; zero effectively turns the flanger off.',
 'DECAY TIME Small Room':'Sets the time for the reverb to decay to a very low level after the input stops.',
 'Large Room':'Sets the room reverb decay time; the manual advises restraint for natural room sounds.',
 'LF DECAY TIME':'Boosts low-frequency decay rate with positive values and reduces it with negative values.',
 'DECAY DEFINITION':'Sets how quickly echo density builds during the decay.',
 'DETUNE DEPTH':'Sets the amount of pitch change introduced by reverb detuning.',
 'DECAY TIME Small Plate':'Sets the time for the plate reverberation to decay.',
 'PREDELAY TIME Small Plate':'Sets the delay before the input signal reaches the plate reverb.',
 'TRIGGER THRESHOLD':'Sets the input level that triggers the reverse reverb envelope.',
 'PRE-TRIGGER TIME':'Sets the amount of audio time captured before a reverse-reverb trigger.',
 'REFL 1 TIME Non Lin 1, 3':'Sets the time delay for the first pre-echo.',
 'REFL 2 TIME Non Lin 1, 3':'Sets the time delay for the second pre-echo.',
 'LFO WIDTH':'Sets the excursion width of the LFO modulation.',
 'R OUTPUT LEVEL':'Sets the right-channel output level.',
 'PREAMP GAIN':'Sets the amount of gain in the preamp stage.',
 'PRE-EQ TRIM':'Adjusts the level entering the preamp EQ to reduce clipping risk.',
 'PRE-EQ GAIN':'Adjusts boost or cut applied by the preamp parametric EQ.',
 'GATE RELEASE':'Sets how long the gate takes to release after the signal falls below threshold.',
 'OUTPUT GAIN':'Sets output boost or cut to compensate for level changes through the effect.',
 'CHOR WIDTH':'Sets the excursion width of the chorus pitch modulation.',
 'BASS GAIN':'Adjusts boost or cut in the bass EQ band.',
 'TREBLE GAIN':'Adjusts boost or cut in the treble EQ band.',
 'NOTCH DEPTH':'Sets the depth of the notches in the modulated filter.',
 'COMP GAIN':'Sets gain applied by the compressor.',
 'COMP THRESHOLD':'Sets the level at which compression begins.',
 'COMP ATTACK':'Sets how quickly the compressor responds after the signal crosses threshold.',
 'COMP RELEASE':'Sets how quickly compression is released after the signal falls below threshold.',
 'EQ GAIN':'Adjusts boost or cut applied by the equalizer band.',
 'MASK THRESHOLD':'Sets the threshold used by the keyed expander side-chain detector.',
 'FILTER GAIN':'Sets boost or cut at the filter output to compensate for insertion loss.'
 ,'DIST GAIN IN/OUT In and Out':'Sets the input and output gain of the distortion stage. These controls change the signal level entering distortion and the level leaving it.'
 ,'DIST GAIN IN and OUT':'Sets the input and output gain of the distortion stage. These controls change the signal level entering distortion and the level leaving it.'
}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manual-pdf'); ap.add_argument('--output',default=str(OUT)); args=ap.parse_args()
    registry=json.loads(SOURCE.read_text()); catalog=json.loads(CATALOG.read_text())
    labels=sorted({p['display_name'] for e in registry['effects'] for p in e['parameters']})
    descriptions,pdf_source=extract_manual(args.manual_pdf,labels)
    shared=[]
    for x in catalog.get('shared_documented_controls',[]):
        shared.append({'id':x['id'],'name':x['name'],'documented_range':x['range'],'kind':x['kind'],'availability':x['status']})
    modulation_pages={14:109,15:109,16:109,17:111,18:111,19:112,20:113,21:115,22:117,23:117,24:117,25:118,26:120,28:122,29:122,30:124,31:126,32:126,33:127,34:129,37:134,38:136,39:137,40:139,41:140,42:141,44:145,45:148,46:149,47:151,48:152,49:153}
    result={'schema':'trollfx-asr10-pc-editor-parameter-schema-v1','source_registry':{'path':'ASR10_FULL_FACTORY_PARAMETER_REGISTRY_V1.json','sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'commit':'7d38ec2bc3369ecd16f9e284ba85ccfd6fe46b55'},'manual_source':pdf_source or {'filename':None,'note':'PDF not supplied to schema generator; ranges come from existing manual-derived catalog.'},'coverage':{'factory_effects':50,'manual_registry_parameters':sum(len(e['parameters']) for e in registry['effects']),'shared_documented_modulation_controls':len(shared),'description_labels_matched':len(descriptions),'manual_paraphrase_labels':len(MANUAL_PARAPHRASES),'manual_section6_has_rom50_entry':False},'shared_controls':shared,'effects':[]}
    for effect in registry['effects']:
        controls=[]
        for p in effect['parameters']:
            manual={k:p.get(k) for k in ('display_name','documented_range','documented_numeric_domain','display_type','units','documented_step','step_confidence','discrete_choices','default_value','ui_range_status','ui_range_confidence','normalized_ui_mapping','evidence')}
            manual['description']=descriptions.get(p['display_name']) or MANUAL_PARAPHRASES.get(p['display_name'])
            manual['description_source']='manual_text' if p['display_name'] in descriptions else ('manual_paraphrase' if p['display_name'] in MANUAL_PARAPHRASES else 'unavailable')
            if p['id']=='effect_variation': manual['description']='Selects one of four preset setups. The manual states that each variation is individually editable and acts as its own effect edit buffer.'; manual['description_source']='manual_text'
            dsp={k:p.get(k) for k in ('dsp_mapping_status','dsp_mapping_confidence','supported_values','mapping_sources','audio_status','runtime_ready')}
            controls.append({'id':p['id'],'order':p.get('editor_order',0),'manual':manual,'dsp_evidence':dsp})
        slot=int(effect['slot']); mod_page=modulation_pages.get(slot)
        if slot==50:
            for control in controls:
                control['manual']['description']=None
                control['manual']['description_source']='manual_scope_gap'
        result['effects'].append({'slot':slot,'factory_name':effect['factory_name'],'parameters':controls,'modulation_metadata':{'source_note':effect.get('modulation_controls'),'controls':shared if mod_page else [],'availability':'manual block present' if mod_page else 'no modulation block identified in Section 6; no universal controls exposed','manual_pdf_page':mod_page,'destination_options':'not exhaustively established by manual-derived registry'}})
    all_manual=[p for e in result['effects'] for p in e['parameters']]
    result['coverage']['manual_described_parameter_entries']=sum(bool(p['manual'].get('description')) for p in all_manual)
    result['coverage']['manual_description_gap_entries']=sum(not bool(p['manual'].get('description')) for p in all_manual)
    result['coverage']['manual_description_gap_effects']=[50]
    output=Path(args.output)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    # Materialize the fully editable manual presentation (including explicit
    # independent subparameters) while keeping DSP verification in its sibling
    # evidence namespace and in the runtime mapping registry.
    import sys
    sys.path.insert(0,str(HERE))
    from parameter_registry import load_registry
    effects=load_registry(); presentation_keys=('id','name','order','range_text','range','type','format','domain','range_variants','units','description','description_source','manual_confidence','default_value','observed_choices','documented_choices','evidence','group','catalog_descriptor','manual_subparameter','editor_visible','input_disabled')
    effect_rows={int(e['slot']):e for e in result['effects']}
    edit_count=0
    for runtime_effect in effects:
        schema_effect=effect_rows[int(runtime_effect['slot'])]
        schema_effect['editable_controls']=[{k:c.get(k) for k in presentation_keys if k in c} for c in runtime_effect['controls']]
        var=next((c for c in runtime_effect['controls'] if c['id']=='effect_variation'),None)
        schema_effect['variation_choices']=(var or {}).get('observed_choices',[])
        schema_effect['available_sections']=sorted({c.get('group','Main effect') for c in runtime_effect['controls'] if c.get('editor_visible',True)})
        edit_count+=sum(c.get('editor_visible',True) for c in runtime_effect['controls'])
    result['coverage']['editable_controls_including_manual_subparameters']=edit_count
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(f"wrote {args.output}; descriptions {len(descriptions)}/{len(labels)} labels; manual descriptors {result['coverage']['manual_registry_parameters']}; editable controls {edit_count}")
if __name__=='__main__': main()
