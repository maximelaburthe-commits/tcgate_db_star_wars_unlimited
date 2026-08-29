import fs from 'node:fs';
import path from 'node:path';
import {browserPage,ROOT,SOURCE_COMMIT,SOURCE_PATH,SOURCE_SHA256,sha256} from './vision_build_common.mjs';
const tcgate=path.resolve(ROOT,'../TCGate'),cyberpunk=path.resolve(ROOT,'../tcgate_db_cyberpunk');
const source=fs.readFileSync(path.join(tcgate,SOURCE_PATH),'utf8');
const actualHash=await sha256(Buffer.from(source));
if(actualHash!==SOURCE_SHA256)throw new Error(`TCGate worker hash mismatch ${actualHash}`);
const cp=JSON.parse(fs.readFileSync(path.join(cyberpunk,'runtime/canonical-vision-index.json'),'utf8')).references.slice(0,8);
const entries=cp.map(x=>({name:x.name,imageUrl:`data:image/webp;base64,${fs.readFileSync(path.join(cyberpunk,x.visionAssetPath)).toString('base64')}`}));
const {browser,page}=await browserPage();
try{
  const original=await browser.newPage();
  await original.evaluate(code=>(0,eval)(code+'\n;globalThis.__originalDescriptor={descriptorFromBitmap,compareDescriptors};'),source);
  let maxDescriptorDelta=0,maxScoreDelta=0;
  for(const entry of entries){
    const compiled=await page.evaluate(url=>globalThis.TCGateDescriptor.descriptorFromUrl(url),entry.imageUrl);
    const expected=await original.evaluate(async url=>{const r=await fetch(url),b=await createImageBitmap(await r.blob());try{return globalThis.__originalDescriptor.descriptorFromBitmap(b)}finally{b.close()}},entry.imageUrl);
    for(const key of ['full','art','gradient','chroma','coarse'])for(let i=0;i<compiled[key].length;i++)maxDescriptorDelta=Math.max(maxDescriptorDelta,Math.abs(compiled[key][i]-expected[key][i]));
    const scores=await page.evaluate(([a,b])=>[globalThis.TCGateDescriptor.compareDescriptors(a,b).total,globalThis.TCGateDescriptor.compareDescriptors(b,a).total],[compiled,expected]);
    maxScoreDelta=Math.max(maxScoreDelta,Math.abs(scores[0]-scores[1]),Math.abs(1-scores[0]));
  }
  if(maxDescriptorDelta>1e-7||maxScoreDelta>1e-7)throw new Error(`parity failed descriptor=${maxDescriptorDelta} score=${maxScoreDelta}`);
  console.log(JSON.stringify({sourceCommit:SOURCE_COMMIT,sourcePath:SOURCE_PATH,sourceSha256:SOURCE_SHA256,samples:entries.length,maxDescriptorDelta,maxScoreDelta}));
}finally{await browser.close()}
