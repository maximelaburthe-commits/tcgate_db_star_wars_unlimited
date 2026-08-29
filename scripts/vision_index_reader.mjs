export function readCoarseIndex(manifest,buffer){
  if(manifest.format!=='float32-le-row-major')throw new Error('unsupported coarse format');
  const expected=manifest.referenceCount*manifest.dimension*4;
  if(buffer.byteLength!==expected)throw new Error(`truncated coarse binary: ${buffer.byteLength} != ${expected}`);
  const view=new DataView(buffer.buffer,buffer.byteOffset,buffer.byteLength),values=new Float32Array(manifest.referenceCount*manifest.dimension);
  for(let i=0;i<values.length;i++){const value=view.getFloat32(i*4,true);if(!Number.isFinite(value))throw new Error(`non-finite coarse value at ${i}`);values[i]=value}
  return values;
}
