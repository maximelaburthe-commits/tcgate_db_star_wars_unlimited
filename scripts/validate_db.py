import json, sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
cards=json.loads((R/'data/cards.json').read_text(encoding='utf-8'))
prints=json.loads((R/'data/printings.json').read_text(encoding='utf-8'))
ids=[x['id'] for x in cards]; pids=[x['id'] for x in prints]
errs=[]
if len(ids)!=len(set(ids)): errs.append('duplicate card ids')
if len(pids)!=len(set(pids)): errs.append('duplicate printing ids')
known=set(ids)
orph=[p['id'] for p in prints if p.get('cardId') not in known]
if orph: errs.append(f'{len(orph)} orphan printings')
print(f'cards={len(cards)} printings={len(prints)} orphans={len(orph)}')
if errs:
 print('FAIL:', '; '.join(errs)); sys.exit(1)
print('OK')
