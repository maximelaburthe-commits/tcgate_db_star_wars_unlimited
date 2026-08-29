import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
cards=json.loads((R/'data/cards.json').read_text(encoding='utf-8'))
prints=json.loads((R/'data/printings.json').read_text(encoding='utf-8'))
faces=json.loads((R/'data/faces.json').read_text(encoding='utf-8'))
minimal=[{k:c.get(k) for k in ('id','name','subtitle','type','set','number') if c.get(k) is not None} for c in cards]
vision=[{'id':f['refId'], **f} for f in faces]
(R/'runtime/cards.min.json').write_text(json.dumps(minimal,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
(R/'runtime/vision-index.json').write_text(json.dumps(vision,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
print(f'runtime cards={len(minimal)} printings={len(prints)} vision={len(vision)}')
