const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#status')).toContainText('READY');
});
async function chooseEffect(page,slot,name){await page.locator('#effect').selectOption(String(slot));await expect(page.locator('#editorEffect')).toContainText(name)}
async function chooseVariation(page,index){const wait=page.waitForResponse(r=>r.url().endsWith('/api/variation')&&r.request().method()==='POST');await page.locator('#variation').selectOption({index});const r=await wait;if(!r.ok())throw new Error(await r.text())}

test('renders catalog ranges, states, and controls for the selected effect', async ({ page }) => {
  await chooseEffect(page,1,'HALL REVERB');
  const decay=page.locator('[data-control="decay_time_1"]');
  await expect(decay).toContainText('0 to 99');
  await expect(decay.locator('.badge')).toHaveText('PARTIAL');
  await expect(decay.locator('input[type=range]')).toHaveAttribute('min','0');
  await expect(decay.locator('input[type=range]')).toHaveAttribute('max','99');
  await chooseEffect(page,39,'PITCH SHIFT');
  await expect(page.locator('#editorEffect')).toContainText('PITCH SHIFT');
  await expect(page.locator('#controlCount')).toContainText('manual registry descriptors');
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
  await decay.fill('40'); await decay.press('Tab');
  await expect(page.locator('.event').first()).toContainText('DSP WRITE');
  await expect(page.locator('.event').first()).toContainText('host 48');
  await expect(page.locator('.event').first()).toContainText('factory_v4_slot1_decay_time');
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
