"""Capture generated TUI previews for Hall and Room; outputs contain UI only."""
from pathlib import Path
from server import Simulator

root=Path(__file__).resolve().parents[2]
out=root/'docs/force_simulator/screenshots'
assets=Path.home()/'asr10-force-assets-v1'
sim=Simulator(assets)
try:
 for slot,label in ((1,'hall'),(3,'room')):
  sim.set_param(0,(slot-1)/49,page='BROWSE')
  for index,page in enumerate(sim.model['pages']):
   (out/f'{label}-{page["name"].lower()}.png').write_bytes(sim.screenshot(index))
finally: sim.close()
print(f'Wrote 6 generated-skin previews to {out}')
