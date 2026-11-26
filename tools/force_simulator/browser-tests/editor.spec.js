const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#status')).toContainText('READY');
});
async function chooseEffect(page,slot,name){await page.locator('#effect').selectOption(String(slot));await expect(page.locator('#editorEffect')).toContainText(name)}
async function chooseVariation(page,index){const wait=page.waitForResponse(r=>r.url().endsWith('/api/variation')&&r.request().method()==='POST');await page.locator('#variation').selectOption({index});const r=await wait;if(!r.ok())throw new Error(await r.text())}
function pcmWavBase64(level,frames=48000,rate=48000){let b=Buffer.alloc(44+frames*4);b.write('RIFF',0);b.writeUInt32LE(36+frames*4,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(2,22);b.writeUInt32LE(rate,24);b.writeUInt32LE(rate*4,28);b.writeUInt16LE(4,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(frames*4,40);for(let i=0;i<frames;i++){let s=Math.round(level*Math.sin(2*Math.PI*440*i/rate)*32767);b.writeInt16LE(s,44+i*4);b.writeInt16LE(Math.round(s*.7),46+i*4)}return b.toString('base64')}
function labFixture(){const wavA=pcmWavBase64(.5),wavB=pcmWavBase64(.25);const render=(display,raw,wav,frame)=>({display_value:display,raw_code:raw,raw_code_basis:'runtime_state',wav_base64:wav,dsp_status:'applied',runtime_status:'ready',firmware_status:'initialized',processing_rate_hz:48000,package_provenance:'synthetic_fixture',provenance_id:'synthetic-ui-fixture',source_commit:'abcdef1',register_updates:[{frame,register:'0x6E'}]});return{schema:'trollfx-asr10-hall-audio-artifacts-v1',source:'ui_fixture',effect_slot:1,effect_name:'HALL REVERB',variation:1,cases:[{case_id:'10_vs_90_impulse',stimulus:'impulse',a:render(10,17,wavA,1),b:render(90,113,wavB,2)},{case_id:'40_vs_41_sweep',stimulus:'sine_sweep',a:render(40,64,wavA,3),b:render(41,65,wavB,4)}]}}

test('renders catalog ranges, states, and controls for the selected effect', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  const decay=page.locator('[data-control="decay_time_1"]');
  await expect(decay).toContainText('0 to 99');
  await expect(decay.locator('.badge').first()).toHaveText('DSP PARTIAL');
  await expect(decay.locator('input[type=range]')).toHaveAttribute('min','0');
  await expect(decay.locator('input[type=range]')).toHaveAttribute('max','99');
  await chooseEffect(page,39,'PITCH SHIFT');
  await expect(page.locator('#editorEffect')).toContainText('PITCH SHIFT');
  await expect(page.locator('#controlCount')).toContainText('base descriptors');
  await expect(page.locator('[data-control="vc_1_semi_1"]')).toHaveCount(1);
});

test('unsupported full-range values stay inspection-only and preserve per-effect drafts', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  const decay=page.locator('[data-control="decay_time_1"] input.numeric');
  await decay.fill('42'); await decay.press('Tab');
  await expect(page.locator('.event').first()).toContainText('DECAY TIME = 42');
  await expect(page.locator('.event').first()).toContainText('No DSP register writes sent');
  await chooseEffect(page,3,'ROOM REVERB');
  await chooseEffect(page,1,'HALL REVERB');
  await expect(page.locator('[data-control="decay_time_1"] input.numeric')).toHaveValue('42');
});

test('exact verified VST point routes to native host and register trace', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  const decay=page.locator('[data-control="decay_time_1"] input.numeric');
  // The seeded HALL draft is already 40. Move through the other exact point
  // first so the browser emits a real edit event for the 40 callback too.
  await decay.fill('41'); await decay.press('Tab');
  await decay.fill('40'); await decay.press('Tab');
  await expect(page.locator('.event').first()).toContainText('DSP WRITE');
  await expect(page.locator('.event').first()).toContainText('host 48');
  await expect(page.locator('.event').first()).toContainText('factory_v4_slot1_decay_time');
});

test('mapped to unmapped value transition preserves applied VST state', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  const decay=page.locator('[data-control="decay_time_1"] input.numeric');
  await decay.fill('41');await decay.press('Tab');
  await expect(page.locator('.event').first()).toContainText('DSP WRITE');
  const applied=await page.request.get('/api/state');
  expect((await applied.json()).values['48']).toBeCloseTo(1,6);
  await decay.fill('42');await decay.press('Tab');
  await expect(page.locator('.event').first()).toContainText('INSPECT ONLY');
  await expect(page.locator('.event').first()).toContainText('No DSP register writes sent');
  const pending=await page.request.get('/api/state');
  expect((await pending.json()).values['48']).toBeCloseTo(1,6);
});

test('Codex 1 runtime_ready evidence cannot substitute for a native VST route', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  const field=page.locator('[data-control="low_freq_decay_1"] input.numeric');
  await field.fill('6');await field.press('Tab');
  await expect(page.locator('.event').first()).toContainText('PENDING_HOST_ROUTE');
  await expect(page.locator('.event').first()).toContainText('No DSP register writes sent');
});

test('diagnostic panel reports original OS identity and keeps the monitor read-only', async ({ page }) => {
  await chooseEffect(page,4,'DUAL DELAYS');
  await page.getByRole('button',{name:'Delay',exact:true}).click();
  await page.locator('[data-control="dual_bus1_delay_time_r"]').click();
  await expect(page.locator('#diagContent')).toContainText('ASR10:ROM-04:dual_bus1_delay_time_r');
  await expect(page.locator('#diagContent')).toContainText('BS1 TIME R');
  await expect(page.locator('#osMonitor')).toContainText(/read-only/i);
  await expect(page.locator('#osMonitor')).toContainText('disconnected');
});

test('preserves the existing verified HALL bus control identity and exact points', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  const bus=page.locator('[data-control="reverb_mix_bus1"] select');
  await bus.selectOption({index:1});
  await expect(page.locator('.event').first()).toContainText('DSP WRITE');
  await expect(page.locator('.event').first()).toContainText('host 46');
  await expect(page.locator('.event').first()).toContainText('factory_v4_slot1_reverb_mix_bus1');
});

test('enumerated native VST labels map only to their registered verified points', async ({ page }) => {
  await chooseEffect(page,39,'PITCH SHIFT');
  await page.getByRole('button',{name:'BANK 2'}).click();
  const quality=page.locator('[data-control="quality_1"] select');
  await quality.selectOption({index:1});
  await expect(page.locator('.event').first()).toContainText('DSP WRITE');
  await expect(page.locator('.event').first()).toContainText('SHORT/COARSER');
  await expect(page.locator('.event').first()).toContainText('host 46');
});

test('banks switch controls immediately and Q-Link gestures edit the assigned bank control', async ({ page }) => {
  await chooseEffect(page,39,'PITCH SHIFT');
  await page.getByRole('button',{name:'Pitch & voice',exact:true}).click();
  await expect(page.locator('#banks button')).toHaveCount(2);
  await expect(page.locator('#controls .control-card')).toHaveCount(8);
  await page.getByRole('button',{name:'BANK 2'}).click();
  await expect(page.locator('#controls .control-card')).toHaveCount(1);
  await expect(page.locator('.qlink[data-q="1"] .qname')).toContainText('QUALITY');
  await page.getByRole('button',{name:'BANK 1'}).click();
  const dial=page.locator('.qlink[data-q="5"] .dial'),box=await dial.boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2-30,{steps:4});await page.mouse.up();
  await expect(page.locator('.event').first()).toContainText('INSPECT ONLY');
  await expect(page.locator('.event').first()).toContainText('VC 2');
});

test('supports observed enumerated choices without pretending they are DSP mapped', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  const variation=page.locator('#variation');
  await expect(variation.locator('option')).toHaveCount(4);
  const edited=page.waitForResponse(r=>r.url().endsWith('/api/variation')&&r.request().method()==='POST');
  await variation.selectOption({index:1});const response=await edited;
  if(!response.ok())throw new Error(await response.text());const result=await response.json();expect(result.event.event_type).toBe('pc_variation_select');expect(result.event.dsp_sent).toBe(false);
  await expect(page.locator('#variationNote')).toContainText('PC-only');
});

test('HALL to ROOM to PITCH to HALL restores independent editor state', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  await page.locator('[data-control="decay_time_1"] input.numeric').fill('41');
  await page.locator('[data-control="decay_time_1"] input.numeric').press('Tab');
  await chooseEffect(page,3,'ROOM REVERB');
  await page.locator('[data-control="decay_time_1"] input.numeric').fill('42');
  await page.locator('[data-control="decay_time_1"] input.numeric').press('Tab');
  await chooseEffect(page,39,'PITCH SHIFT');
  await page.locator('[data-control="vc_1_semi_1"] input.numeric').fill('7');
  await page.locator('[data-control="vc_1_semi_1"] input.numeric').press('Tab');
  await chooseEffect(page,1,'HALL REVERB');
  await expect(page.locator('[data-control="decay_time_1"] input.numeric')).toHaveValue('41');
  await chooseEffect(page,3,'ROOM REVERB');
  await expect(page.locator('[data-control="decay_time_1"] input.numeric')).toHaveValue('42');
  await chooseEffect(page,39,'PITCH SHIFT');
  await expect(page.locator('[data-control="vc_1_semi_1"] input.numeric')).toHaveValue('7');
});

test('full editor controls have non-overlapping visible bounds', async ({ page }) => {
  await chooseEffect(page,39,'PITCH SHIFT');
  const boxes=await page.locator('#controls .control-card').evaluateAll(els=>els.map(e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,right:r.right,bottom:r.bottom}}));
  for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++){
    const a=boxes[i],b=boxes[j],overlap=Math.min(a.right,b.right)-Math.max(a.x,b.x)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>1;
    expect(overlap,'control cards overlap').toBe(false);
  }
  const clipped=await page.locator('#controls .control-card').evaluateAll(cards=>cards.flatMap(card=>[...card.querySelectorAll('h3,.range-label,.mapping,.dsp-state,.live-value')].filter(el=>el.clientWidth&&el.scrollWidth>el.clientWidth+2).map(el=>el.textContent.trim())));
  expect(clipped,'parameter labels or values clip horizontally').toEqual([]);
});

test('keeps the three generated SDK skin pages available as a distinct preview', async ({ page }) => {
  await page.locator('details.skin-preview summary').click();
  for(const name of ['BROWSE','EDIT','MIX']){const tab=page.getByRole('button',{name,exact:true});await tab.click();await expect(tab).toHaveClass(/active/);}
});

test('variation buffers remain independent and draft reset/undo are PC-only', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  await page.locator('#resetDraft').click();
  await chooseVariation(page,1);
  const decay=page.locator('[data-control="decay_time_1"] input.numeric');
  await decay.fill('42');await decay.press('Tab');
  await chooseVariation(page,2);
  await page.locator('[data-control="decay_time_1"] input.numeric').fill('43');
  await page.locator('[data-control="decay_time_1"] input.numeric').press('Tab');
  await chooseVariation(page,1);
  await expect(page.locator('[data-control="decay_time_1"] input.numeric')).toHaveValue('42');
  await page.locator('#undoDraft').click();
  await expect(page.locator('[data-control="decay_time_1"] input.numeric')).toHaveValue('40');
  await expect(page.locator('.event').first()).toContainText('pc draft undo');
  await page.locator('[data-control="decay_time_1"] input.numeric').fill('45');
  await page.locator('[data-control="decay_time_1"] input.numeric').press('Tab');
  await page.locator('#resetDraft').click();
  await expect(page.locator('[data-control="decay_time_1"] input.numeric')).toHaveValue('40');
  await expect(page.locator('.event').first()).toContainText('Reset to editor seed values');
  await expect(page.locator('.event').first()).toContainText('No DSP register writes sent');
});

test('exact mapped value in a non-native PC variation stays pending', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  await page.locator('#variation').selectOption({index:1});
  const before=(await (await page.request.get('/api/state')).json()).values['48'];
  const input=page.locator('[data-control="decay_time_1"] input.numeric');
  await input.fill('41');await input.press('Tab');
  await expect(page.locator('.event').first()).toContainText('PC_ONLY_VARIATION');
  await expect(page.locator('.event').first()).toContainText('No DSP register writes sent');
  const state=await (await page.request.get('/api/state')).json();
  expect(state.values['48']).toBe(before);
  await expect(page.locator('#diagContent')).toContainText('PC-only variation');
});

test('manual-derived DUAL DELAYS has independent BUS1/BUS2 and left/right controls', async ({ page }) => {
  await chooseEffect(page,4,'DUAL DELAYS');
  await page.getByRole('button',{name:'Delay',exact:true}).click();
  for(const id of ['delay_time_l','dual_bus1_delay_time_r','dual_bus2_delay_time_l','dual_bus2_delay_time_r']) await expect(page.locator(`[data-control="${id}"]`)).toHaveCount(1);
  await expect(page.locator('[data-control="delay_time_l"]')).toContainText('0 to 2000 ms');
  await expect(page.locator('[data-control="dual_bus2_delay_time_l"]')).toContainText('0 to 150 ms');
  await page.getByRole('button',{name:'Bus mixing & routing',exact:true}).click();
  await expect(page.locator('#controls .control-card')).toHaveCount(4);
  await expect(page.locator('[data-control="dual_bus1_delay_mix"]')).toBeVisible();
  await expect(page.locator('[data-control="dual_bus2_delay_mix"]')).toBeVisible();
});

test('nonlinear reverb displays five captured envelope values and flags four unresolved manual fields', async ({ page }) => {
  await chooseEffect(page,22,'NLIN REVRB 1');
  const response=await page.request.get('/api/state'),state=await response.json(),ids=state.inspector_controls.map(x=>x.id);
  for(let n=1;n<=5;n++)expect(ids).toContain(`manual_env_lev_${n}`);
  for(let n=6;n<=9;n++)expect(ids).not.toContain(`manual_env_lev_${n}`);
  await expect(page.locator('#controlCount')).toContainText('five values');
  await page.getByRole('button',{name:'Main effect',exact:true}).click();
  const banks=page.locator('#banks button');
  for(let i=0;i<await banks.count();i++){
    await banks.nth(i).click();
    if(await page.locator('[data-control="manual_env_lev_1"]').count())break;
  }
  await page.locator('[data-control="manual_env_lev_1"]').click();
  await expect(page.locator('#diagContent')).toContainText('ENV LEV');
});

test('modulation is shown only for algorithms with an explicit Section 6 block', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  await expect(page.locator('#sections button[data-group="Modulation"]')).toHaveCount(0);
  await chooseEffect(page,14,'SMALL ROOM');
  await page.getByRole('button',{name:'Modulation',exact:true}).click();
  await expect(page.locator('#controls .control-card')).toHaveCount(8);
  await expect(page.locator('[data-control="mod_mod_src_1"] select option')).toHaveCount(12);
  await expect(page.locator('[data-control="mod_dst_1"] input')).toBeDisabled();
  await chooseEffect(page,27,'VCF+DISTORT');
  await expect(page.locator('#sections button[data-group="Modulation"]')).toHaveCount(0);
});

test('mixed time units are converted to a precise PC display domain without DSP writes', async ({ page }) => {
  await chooseEffect(page,42,'EQ+CMPRESSOR');
  await page.getByRole('button',{name:'Dynamics',exact:true}).click();
  const attack=page.locator('[data-control="comp_attack_1"]');
  await expect(attack).toContainText('50µs to 100ms');
  await expect(attack.locator('.range-label')).toContainText('s');
  const input=attack.locator('input.numeric');
  const bounds=await input.evaluate(el=>[Number(el.min),Number(el.max)]);
  expect(bounds[0]).toBeCloseTo(0.00005,9);expect(bounds[1]).toBeCloseTo(0.1,9);
  await input.fill('0.00005');await input.press('Tab');
  await expect(page.locator('.event').first()).toContainText('INSPECT ONLY');
  await expect(page.locator('.event').first()).toContainText('No DSP register writes sent');
});

test('all fifty factory effects expose selected-effect controls', async ({ page }) => {
  await expect(page.locator('#effect option')).toHaveCount(50);
  for(let slot=1;slot<=50;slot++){
    await page.locator('#effect').selectOption(String(slot));
    await expect(page.locator('#editorEffect')).not.toHaveText('—');
    await expect(page.locator('#controls .control-card').first()).toBeVisible();
    expect(await page.locator('#sections button').count()).toBeGreaterThan(1);
    const clipped=await page.locator('#controls .control-card').evaluateAll(cards=>cards.flatMap(card=>[...card.querySelectorAll('h3,.range-label,.description,.mapping,.dsp-state,.live-value')].filter(el=>el.clientWidth&&el.scrollWidth>el.clientWidth+2).map(el=>el.textContent.trim())));
    expect(clipped,`clipped text in factory effect slot ${slot}`).toEqual([]);
  }
});

test('captures Hall, Room, and multi-bank Pitch Shift editor evidence', async ({ page }) => {
  const out=path.resolve(__dirname,'../../../docs/force_simulator/screenshots');fs.mkdirSync(out,{recursive:true});
  await chooseEffect(page,1,'HALL REVERB');
  await chooseVariation(page,0);
  await page.locator('[data-control="decay_time_1"] input.numeric').fill('41');await page.locator('[data-control="decay_time_1"] input.numeric').press('Tab');
  await page.locator('[data-control="low_freq_decay_1"] input.numeric').fill('6');await page.locator('[data-control="low_freq_decay_1"] input.numeric').press('Tab');
  await page.locator('[data-control="diffusion_1"] input.numeric').fill('78');await page.locator('[data-control="diffusion_1"] input.numeric').press('Tab');
  await page.screenshot({path:path.join(out,'pc-editor-hall-bank-1.png'),fullPage:true});
  await chooseEffect(page,4,'DUAL DELAYS');
  await page.getByRole('button',{name:'Delay',exact:true}).click();
  await page.screenshot({path:path.join(out,'pc-editor-dual-delays.png'),fullPage:true});
  await chooseEffect(page,6,'CHORUS+REVRB');
  await page.getByRole('button',{name:'Reverb',exact:true}).click();
  await page.screenshot({path:path.join(out,'pc-editor-chorus-reverb.png'),fullPage:true});
  await chooseEffect(page,8,'FLANGER+REV');
  await page.screenshot({path:path.join(out,'pc-editor-flanger-reverb.png'),fullPage:true});
  await chooseEffect(page,3,'ROOM REVERB');
  await chooseVariation(page,0);
  await page.locator('[data-control="decay_time_1"] input.numeric').fill('64');await page.locator('[data-control="decay_time_1"] input.numeric').press('Tab');
  await page.screenshot({path:path.join(out,'pc-editor-room-bank-1.png'),fullPage:true});
  await chooseEffect(page,39,'PITCH SHIFT');
  await chooseVariation(page,0);
  await page.locator('[data-control="vc_1_semi_1"] input.numeric').fill('7');await page.locator('[data-control="vc_1_semi_1"] input.numeric').press('Tab');
  await page.screenshot({path:path.join(out,'pc-editor-pitch-bank-1.png'),fullPage:true});
  await page.getByRole('button',{name:'BANK 2'}).click();await page.screenshot({path:path.join(out,'pc-editor-pitch-bank-2.png'),fullPage:true});
});

test('AUDIO LAB imports explicit artifacts, preserves source/raw labels, plots and plays WAV, exports path-free measurements without DSP writes', async ({ page }) => {
  let controlPosts=0;page.on('request',r=>{if(r.url().endsWith('/api/control')||r.url().endsWith('/api/set'))controlPosts++});
  await page.locator('#audioLabMode').click();
  await expect(page.locator('#audioLab')).toBeVisible();
  await expect(page.locator('#labCase')).toBeDisabled();
  await page.locator('#labBundle').setInputFiles({name:'hall-lab-fixture.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(labFixture()))});
  await expect(page.locator('#labSource')).toContainText('UI TEST FIXTURE · synthetic only');
  await expect(page.locator('#labAValue')).toHaveText('DECAY 10');
  await expect(page.locator('#labBValue')).toHaveText('DECAY 90');
  await expect(page.locator('#labARaw')).toContainText('Raw code 17');
  await expect(page.locator('#labBRaw')).toContainText('Raw code 113');
  await expect(page.locator('#labAMetrics')).toContainText('RMS 0.305');
  const plotted=await page.locator('#labWave').evaluate(el=>{const d=el.getContext('2d').getImageData(0,0,el.width,el.height).data;let teal=0,amber=0;for(let i=0;i<d.length;i+=4){if(d[i+1]>d[i]*1.2&&d[i+2]>d[i]*1.2&&d[i+1]>100)teal++;if(d[i]>d[i+1]*1.2&&d[i+1]>d[i+2]*1.2&&d[i]>100)amber++}return{teal,amber}});
  expect(plotted.teal).toBeGreaterThan(0);expect(plotted.amber).toBeGreaterThan(0);
  await expect(page.locator('#labAPlayer')).toHaveJSProperty('readyState',4);
  await expect(page.locator('#labBPlayer')).toHaveJSProperty('readyState',4);
  await page.locator('#labAPlayer').evaluate(el=>el.play());
  await expect(page.locator('#labAPlayer')).toHaveJSProperty('paused',false);
  await expect(page.locator('#labDelta')).toContainText('Difference RMS:');
  await expect(page.locator('#labRegisterStatus')).toContainText('0X6E @ frame 1');
  await page.locator('#labStimulus').selectOption('sine_sweep');
  await expect(page.locator('#labCase option')).toHaveCount(1);
  await expect(page.locator('#labCase')).toHaveValue('40_vs_41_sweep');
  await page.locator('#labStimulus').selectOption('impulse');
  await page.locator('#labDuration').fill('0.5');
  const downloaded=page.waitForEvent('download');await page.locator('#labExportReport').click();const dl=await downloaded;
  const reportPath=path.join('/tmp',`audio-lab-${Date.now()}.json`);await dl.saveAs(reportPath);const report=JSON.parse(fs.readFileSync(reportPath,'utf8'));
  expect(report.cases[0].display_values).toEqual([10,90]);expect(report.analysis_metrics.a.rms).toBeGreaterThan(0);expect(report.analysis_metrics.difference.rms).toBeGreaterThan(0);expect(JSON.stringify(report)).not.toMatch(/Users\\\\|home\\\\|wav_base64|local_path|checkpoint_path/);
  expect(controlPosts).toBe(0);
  const out=path.resolve(__dirname,'../../../docs/force_simulator/screenshots');fs.mkdirSync(out,{recursive:true});
  await page.screenshot({path:path.join(out,'pc-editor-audio-lab-fixture.png'),fullPage:true});
});

test('imports Codex 3 real HALL AUDIO LAB bundles and reconciles browser playback, tail plots, and hashes', async ({ page }) => {
  const bundleDir=process.env.TROLLFX_HALL_AUDIO_LAB_BUNDLE_DIR,qaPath=process.env.TROLLFX_HALL_AUDIO_LAB_QA_REPORT;
  test.skip(!bundleDir||!qaPath,'Set TROLLFX_HALL_AUDIO_LAB_BUNDLE_DIR and TROLLFX_HALL_AUDIO_LAB_QA_REPORT to run against local Codex 3 artifacts');
  test.setTimeout(180000);
  const qa=JSON.parse(fs.readFileSync(qaPath,'utf8'));
  const files=fs.readdirSync(bundleDir).filter(x=>/^hall-audio-lab-.*\.json$/.test(x)).sort();
  expect(files).toHaveLength(4);
  expect(qa.validator.bundle_analysis).toBe('PASS_FOR_ALL_FOUR_BUNDLES');
  expect(qa.startup.schedule_events_applied).toBe(qa.startup.schedule_events_expected);
  expect(qa.startup.schedule_events_applied).toBe(213);
  expect(qa.startup.explicit_runtime_reset_each_run).toBe(true);
  expect(qa.startup.post_schedule_initial_register_state_identical).toBe(true);
  const manifest=qa.audio_lab_bundles;
  const expectedRows=qa.audio_lab_measurements.flatMap(x=>x.cases);
  const renders=qa.render_manifest;
  const posted=[];let forbiddenWrites=0;
  page.on('request',r=>{if(r.url().endsWith('/api/control')||r.url().endsWith('/api/set'))forbiddenWrites++});
  await page.locator('#audioLabMode').click();
  for(const filename of files){
    const fullPath=path.join(bundleDir,filename),bytes=fs.readFileSync(fullPath),bundle=JSON.parse(bytes.toString('utf8'));
    const bundleSha=crypto.createHash('sha256').update(bytes).digest('hex');
    const manifestRow=manifest.find(x=>x.filename===filename);
    expect(manifestRow,`QA bundle manifest missing ${filename}`).toBeTruthy();
    expect(bundleSha).toBe(manifestRow.sha256);
    expect(bundle.source).toBe('standalone_experimental_runtime');
    expect(bundle.effect_slot).toBe(1);expect(bundle.effect_name).toBe('HALL REVERB');expect(bundle.variation).toBe(1);
    const mode=manifestRow.rate_mode,shotStimulus=manifestRow.stimulus;
    const upload=page.waitForResponse(r=>r.url().endsWith('/api/audio-lab/import')&&r.request().method()==='POST');
    await page.locator('#labBundle').setInputFiles(fullPath);
    const response=await upload;expect(response.status(),`AUDIO LAB import failed for ${filename}`).toBe(200);
    await expect(page.locator('#labSource')).toContainText('Standalone experimental native ES5510 runtime');
    expect(await page.locator('#labSource').textContent()).not.toMatch(/synthetic|VST audio/i);
    // The API response resolves before the file-input handler finishes its
    // follow-up UI update. Wait for the selector state rather than reading a
    // stale value from the preceding imported bundle.
    await expect(page.locator('#labStimulus')).toHaveValue(bundle.cases[0].stimulus);
    expect(await page.locator('#labCase option')).toHaveCount(4);
    const sourceCaseRows=[];
    for(let i=0;i<bundle.cases.length;i++){
      const inputCase=bundle.cases[i];
      await page.locator('#labCase').selectOption(inputCase.case_id);
      const expected=expectedRows.find(x=>x.stimulus===inputCase.stimulus&&
        JSON.stringify(x.display_values)==JSON.stringify([inputCase.a.display_value,inputCase.b.display_value])&&
        Math.abs(x.processing_rates_hz[0]-inputCase.a.processing_rate_hz)<0.01&&
        Math.abs(x.processing_rates_hz[1]-inputCase.b.processing_rate_hz)<0.01);
      expect(expected,`${inputCase.case_id}: QA measurement row missing`).toBeTruthy();
      await expect(page.locator('#labAValue')).toHaveText(`DECAY ${inputCase.a.display_value}`);
      await expect(page.locator('#labBValue')).toHaveText(`DECAY ${inputCase.b.display_value}`);
      await expect(page.locator('#labARaw')).toContainText(`Raw code ${inputCase.a.raw_code}`);
      await expect(page.locator('#labBRaw')).toContainText(`Raw code ${inputCase.b.raw_code}`);
      await expect(page.locator('#labAStatus')).toContainText('DSP APPLIED');
      await expect(page.locator('#labAStatus')).toContainText('runtime READY');
      await expect(page.locator('#labAStatus')).toContainText('firmware INITIALIZED');
      await expect(page.locator('#labRegisterStatus')).toContainText('5 updates');
      const loaded=await page.evaluate(()=>({a:labDecoded.get('a').frames,b:labDecoded.get('b').frames,
        ar:labDecoded.get('a').rate,br:labDecoded.get('b').rate,computed:labComputed,
        wavHashes:[labCase.a.wav_sha256,labCase.b.wav_sha256],
        provenance:[labCase.a.package_provenance,labCase.b.package_provenance],
        provenanceIds:[labCase.a.provenance_id,labCase.b.provenance_id],
        sourceCommit:[labCase.a.source_commit,labCase.b.source_commit],
        processingRates:[labCase.a.processing_rate_hz,labCase.b.processing_rate_hz],
        registerRows:[labCase.a.register_updates,labCase.b.register_updates]}));
      expect(loaded.a).toBe(loaded.b);expect(loaded.ar).toBe(loaded.br);
      expect(loaded.ar).toBe(expected.sample_rate_hz);
      expect(loaded.computed.a.rms).toBeCloseTo(expected.rms[0],11);
      expect(loaded.computed.b.rms).toBeCloseTo(expected.rms[1],11);
      expect(loaded.computed.a.peak).toBeCloseTo(expected.peak[0],11);
      expect(loaded.computed.b.peak).toBeCloseTo(expected.peak[1],11);
      expect(loaded.computed.difference.rms).toBeCloseTo(expected.difference_rms,11);
      expect(loaded.computed.difference.peak).toBeCloseTo(expected.difference_peak,11);
      expect(loaded.wavHashes).toEqual(expected.wav_sha256);
      expect(loaded.provenance).toEqual(['validated_factory_checkpoint','validated_factory_checkpoint']);
      expect(loaded.provenanceIds).toEqual(expected.provenance_ids);
      expect(loaded.sourceCommit).toEqual([qa.provenance.runtime_source_commit,qa.provenance.runtime_source_commit]);
      expect(loaded.processingRates).toEqual(expected.processing_rates_hz);
      expect(loaded.registerRows[0]).toHaveLength(5);
      expect(loaded.registerRows[0].map(x=>x.register)).toEqual(qa.provenance.register_order.map(x=>x.toUpperCase()));
      const renderA=renders.find(x=>x.wav_pcm32_sha256===expected.wav_sha256[0]);
      expect(renderA,`${inputCase.case_id}: PCM32 render hash absent from QA manifest`).toBeTruthy();
      expect(renderA.late_tail_rms_8_10s).toBeGreaterThan(0);
      const tail=await page.evaluate(()=>{const d=labDecoded.get('a'),start=Math.min(d.frames,Math.floor(d.rate*8)),end=d.frames;let sum=0;for(let i=start;i<end;i++)sum+=(d.left[i]**2+d.right[i]**2)/2;return Math.sqrt(sum/Math.max(1,end-start))});
      // Browser Float32 decoding and the independent PCM32 analyzer differ by
      // at most a few 1e-10 here; keep a 1e-8 absolute tolerance.
      expect(Math.abs(tail-renderA.late_tail_rms_8_10s)).toBeLessThan(1e-8);
      const plots=await page.evaluate(()=>{function colors(id){let c=document.querySelector(id),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data,t=0,o=0,r=0;for(let i=0;i<d.length;i+=4){if(d[i+1]>d[i]*1.2&&d[i+2]>d[i]*1.2&&d[i+1]>100)t++;if(d[i]>d[i+1]*1.2&&d[i+1]>d[i+2]*1.2&&d[i]>100)o++;if(d[i]>d[i+1]*1.2&&d[i]>d[i+2]*1.2&&d[i]>100)r++}return{teal:t,amber:o,red:r}}return{wave:colors('#labWave'),envelope:colors('#labEnvelope'),difference:colors('#labDifference')}});
      expect(plots.wave.teal).toBeGreaterThan(0);
      expect(loaded.a).toBeGreaterThan(0);expect(loaded.b).toBe(loaded.a);
      expect(plots.envelope.teal).toBeGreaterThan(0);expect(plots.envelope.amber).toBeGreaterThan(0);
      expect(plots.difference.red).toBeGreaterThan(0);
      for(const selector of ['#labAPlayer','#labBPlayer']){
        await expect(page.locator(selector)).toHaveJSProperty('readyState',4);
        const playing=await page.locator(selector).evaluate(async el=>{await el.play();let ok=!el.paused;el.pause();return ok});expect(playing).toBe(true);
      }
      const rowCase={file:filename,case:inputCase.case_id,display:[inputCase.a.display_value,inputCase.b.display_value],
        raw:[inputCase.a.raw_code,inputCase.b.raw_code],difference_rms:loaded.computed.difference.rms,
        difference_peak:loaded.computed.difference.peak,tail_rms_8_10s:tail};
      sourceCaseRows.push(rowCase);
      if(i===0){
        const modeName=mode==='FactoryReference'?'factoryreference':'experimental48000';
        const stimName=shotStimulus;
        const out=path.resolve(__dirname,'../../../docs/force_simulator/screenshots');fs.mkdirSync(out,{recursive:true});
        await page.screenshot({path:path.join(out,`pc-editor-audio-lab-real-${modeName}-${stimName}.png`),fullPage:true});
      }
    }
    posted.push({file:filename,sha256:bundleSha,source:bundle.source,rate_mode:mode,stimulus:shotStimulus,cases:sourceCaseRows});
  }
  expect(forbiddenWrites).toBe(0);
  const repeatRows=renders.filter(x=>x.raw_code===51&&x.repeat===true);
  for(const repeated of repeatRows){
    const original=renders.find(x=>x.rate_mode===repeated.rate_mode&&x.stimulus===repeated.stimulus&&x.raw_code===51&&x.repeat===false);
    expect(original).toBeTruthy();expect(repeated.wav_pcm32_sha256).toBe(original.wav_pcm32_sha256);
  }
  fs.writeFileSync(path.resolve(__dirname,'../../../docs/force_simulator/real-audio-lab-browser-results.json'),JSON.stringify({schema:'trollfx-asr10-real-audio-lab-browser-qa-v1',source:'Codex 3 standalone experimental native ES5510 artifacts',bundles:posted,repeatability:'PCM32 exact hashes checked against Codex 3 render manifest',startup:qa.startup},null,2)+'\n');
});
