import fs from 'node:fs';
import path from 'node:path';
import {performance} from 'node:perf_hooks';
import {ROOT,SOURCE_COMMIT,SOURCE_PATH,SOURCE_SHA256,DESCRIPTOR_VERSION,browserPage,compileUrls,readJson,sha256} from './vision_build_common.mjs';
const refs=readJson('runtime/canonical-vision-index.json').slice().sort((a,b)=>a.refId.localeCompare(b.refId));
if(refs.length!==7180||new Set(refs.map(x=>x.refId)).size!==refs.length)throw new Error('expected 7180 unique canonical refs');
const {browser,page}=await browserPage(),started=performance.now();
let descriptors;
try{descriptors=await compileUrls(page,refs,24,false)}finally{await browser.close()}
const dimension=216,buffer=Buffer.allocUnsafe(refs.length*dimension*4);
for(let row=0;row<descriptors.length;row++){
  if(descriptors[row].length!==dimension)throw new Error(`dimension mismatch ${refs[row].refId}`);
  for(let col=0;col<dimension;col++){const value=descriptors[row][col];if(!Number.isFinite(value))throw new Error(`non-finite ${refs[row].refId}`);buffer.writeFloatLE(value,(row*dimension+col)*4)}
}
const binPath=path.join(ROOT,'runtime/vision-coarse-index.bin');fs.writeFileSync(binPath,buffer);
const binSha256=await sha256(buffer);
const manifest={descriptorVersion:DESCRIPTOR_VERSION,descriptorSourceCommit:SOURCE_COMMIT,descriptorSourcePath:SOURCE_PATH,descriptorSourceSha256:SOURCE_SHA256,recognitionProfileId:'swu-v1-canonical-dev',format:'float32-le-row-major',referenceWidth:72,referenceHeight:108,coarseColumns:6,coarseRows:9,channelsPerCell:4,dimension,referenceCount:refs.length,byteLength:buffer.length,binarySha256:binSha256,references:refs.map((x,index)=>({index,refId:x.refId,cardId:x.cardId,side:x.side,visualFamilyId:x.visualFamilyId,recognitionGroupId:x.recognitionGroupId}))};
const manifestText=JSON.stringify(manifest);fs.writeFileSync(path.join(ROOT,'runtime/vision-coarse-index.json'),manifestText);
const buildMilliseconds=Number((performance.now()-started).toFixed(3));
const descriptorManifest={descriptorVersion:DESCRIPTOR_VERSION,descriptorSourceCommit:SOURCE_COMMIT,descriptorSourcePath:SOURCE_PATH,descriptorSourceSha256:SOURCE_SHA256,coarseIndex:'runtime/vision-coarse-index.bin',coarseManifest:'runtime/vision-coarse-index.json',detailedStrategy:'B/C-hybrid-recommended',detailedDescriptorDimension:{full:7776,art:4225,gradient:7776,chroma:15552,coarse:216,totalFloat32:35545,bytesPerReference:142180}};
fs.writeFileSync(path.join(ROOT,'runtime/vision-descriptor-manifest.json'),JSON.stringify(descriptorManifest,null,2)+'\n');
console.log(JSON.stringify({refs:refs.length,dimension,bytes:buffer.length,sha256:binSha256,buildMilliseconds}));
