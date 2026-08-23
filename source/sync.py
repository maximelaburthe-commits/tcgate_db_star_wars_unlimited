import requests, json, hashlib, re
from pathlib import Path
R=Path(__file__).resolve().parents[1]
URL='https://api.swuapi.com/export/all'
def slug(s): return re.sub(r'[^a-z0-9]+','-',(s or '').lower()).strip('-')
def val(o,*keys):
 for k in keys:
  if isinstance(o,dict) and k in o and o[k] is not None: return o[k]
 return None
j=requests.get(URL,timeout=120).json(); raw=j.get('cards',[]); sets=j.get('sets',[])
byid={str(val(x,'externalId','external_id','id','uuid')):x for x in raw}
def parent_id(x):
 p=val(x,'variantOf','variant_of','reprintOf','reprint_of')
 return str(p) if p not in (None,'') else None
def root(x):
 seen=set(); cur=x
 while True:
  pid=parent_id(cur)
  if not pid or pid in seen or pid not in byid: return cur
  seen.add(pid); cur=byid[pid]
def gameplay_key(x):
 r=root(x)
 rid=str(val(r,'externalId','external_id','id','uuid'))
 if rid not in ('None',''): return 'swu-'+slug(rid)
 return 'swu-'+hashlib.sha1((str(val(r,'name'))+'|'+str(val(r,'subtitle'))+'|'+str(val(r,'text'))).encode()).hexdigest()[:16]
cards={}; prints=[]
for x in raw:
 cid=gameplay_key(x)
 if cid not in cards:
  cards[cid]={'id':cid,'name':val(x,'name'),'subtitle':val(x,'subtitle'),'type':val(x,'type'),'aspects':val(x,'aspects'),'traits':val(x,'traits'),'cost':val(x,'cost'),'hp':val(x,'hp'),'power':val(x,'power'),'text':val(x,'text'),'deployBox':val(x,'deployBox','deploy_box'),'epicAction':val(x,'epicAction','epic_action')}
 eid=str(val(x,'uuid','externalId','external_id','id'))
 setv=val(x,'setCode','set_code','set')
 if isinstance(setv,dict): setv=val(setv,'code','name')
 prints.append({'id':'swup-'+slug(eid),'cardId':cid,'sourceId':eid,'set':setv,'number':val(x,'collectorNumber','collector_number'),'variant':val(x,'variantType','variant_type') or 'Standard','rarity':val(x,'rarity'),'artist':val(x,'artist'),'frontImageUrl':val(x,'frontImageUrl','front_image_url'),'backImageUrl':val(x,'backImageUrl','back_image_url')})
(R/'data/cards.json').write_text(json.dumps(list(cards.values()),ensure_ascii=False,indent=2),encoding='utf-8')
(R/'data/printings.json').write_text(json.dumps(prints,ensure_ascii=False,indent=2),encoding='utf-8')
(R/'data/sets.json').write_text(json.dumps(sets,ensure_ascii=False,indent=2),encoding='utf-8')
meta=j.get('meta',{}); meta.update({'normalizedGameplayCards':len(cards),'normalizedPrintings':len(prints)})
(R/'data/coverage.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print(meta)
