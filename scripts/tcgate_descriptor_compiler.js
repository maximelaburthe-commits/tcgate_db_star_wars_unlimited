(function(global){
  'use strict';
  const REF_W=72,REF_H=108,COARSE_COLS=6,COARSE_ROWS=9;
  const clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));
  function mean(xs){let s=0;for(let i=0;i<xs.length;i++)s+=xs[i];return xs.length?s/xs.length:0}
  function stddev(xs,m=mean(xs)){let s=0;for(let i=0;i<xs.length;i++){const d=xs[i]-m;s+=d*d}return xs.length?Math.sqrt(s/xs.length):0}
  function drawCanonical(source,inset=.04,rotate180=false){
    const c=new OffscreenCanvas(REF_W,REF_H),ctx=c.getContext('2d',{willReadFrequently:true,alpha:false});
    ctx.fillStyle='#777';ctx.fillRect(0,0,REF_W,REF_H);
    const sw=source.width||REF_W,sh=source.height||REF_H,sx=sw*inset,sy=sh*inset,sww=Math.max(1,sw*(1-inset*2)),shh=Math.max(1,sh*(1-inset*2));
    if(rotate180){ctx.translate(REF_W/2,REF_H/2);ctx.rotate(Math.PI);ctx.translate(-REF_W/2,-REF_H/2)}
    ctx.drawImage(source,sx,sy,sww,shh,0,0,REF_W,REF_H);return c;
  }
  function buildGrayAndChroma(canvas){
    const px=canvas.getContext('2d',{willReadFrequently:true}).getImageData(0,0,REF_W,REF_H).data;
    const gray=new Float32Array(REF_W*REF_H),chroma=new Float32Array(REF_W*REF_H*2);
    for(let p=0;p<REF_W*REF_H;p++){const i=p*4,r=px[i]/255,g=px[i+1]/255,b=px[i+2]/255,lum=.299*r+.587*g+.114*b,sum=r+g+b+.15;gray[p]=lum;chroma[p*2]=(r-g)/sum;chroma[p*2+1]=(b-g)/sum}return{gray,chroma};
  }
  function blurGray(src){const out=new Float32Array(src.length);for(let y=0;y<REF_H;y++)for(let x=0;x<REF_W;x++){let sum=0,n=0;for(let dy=-1;dy<=1;dy++){const yy=clamp(y+dy,0,REF_H-1);for(let dx=-1;dx<=1;dx++){const xx=clamp(x+dx,0,REF_W-1);sum+=src[yy*REF_W+xx];n++}}out[y*REF_W+x]=sum/n}return out}
  function gradientMagnitude(gray){const out=new Float32Array(gray.length);for(let y=1;y<REF_H-1;y++)for(let x=1;x<REF_W-1;x++){const i=y*REF_W+x,gx=-gray[(y-1)*REF_W+x-1]+gray[(y-1)*REF_W+x+1]-2*gray[y*REF_W+x-1]+2*gray[y*REF_W+x+1]-gray[(y+1)*REF_W+x-1]+gray[(y+1)*REF_W+x+1],gy=-gray[(y-1)*REF_W+x-1]-2*gray[(y-1)*REF_W+x]-gray[(y-1)*REF_W+x+1]+gray[(y+1)*REF_W+x-1]+2*gray[(y+1)*REF_W+x]+gray[(y+1)*REF_W+x+1];out[i]=Math.sqrt(gx*gx+gy*gy)}return out}
  function regionVector(arr,channels,x0,y0,x1,y1,step=1){const out=[];for(let y=y0;y<y1;y+=step)for(let x=x0;x<x1;x+=step){const base=(y*REF_W+x)*channels;for(let c=0;c<channels;c++)out.push(arr[base+c])}return out}
  function buildCoarseDescriptor(gray,gradient,chroma){
    const cells=[],lums=[];for(let row=0;row<COARSE_ROWS;row++){const y0=Math.floor(row*REF_H/COARSE_ROWS),y1=Math.floor((row+1)*REF_H/COARSE_ROWS);for(let col=0;col<COARSE_COLS;col++){const x0=Math.floor(col*REF_W/COARSE_COLS),x1=Math.floor((col+1)*REF_W/COARSE_COLS);let lum=0,edge=0,cr=0,cb=0,n=0;for(let y=y0;y<y1;y+=2)for(let x=x0;x<x1;x+=2){const idx=y*REF_W+x;lum+=gray[idx];edge+=gradient[idx];cr+=chroma[idx*2];cb+=chroma[idx*2+1];n++}n=Math.max(1,n);const c=[lum/n,edge/n,cr/n,cb/n];cells.push(c);lums.push(c[0])}}
    const lm=mean(lums),ls=Math.max(.055,stddev(lums,lm)),out=[];for(const c of cells)out.push(clamp((c[0]-lm)/ls,-2.8,2.8)/2.8,clamp(c[1]*5,0,1),clamp(c[2],-.8,.8),clamp(c[3],-.8,.8));return out;
  }
  function descriptorFromBitmap(source,inset=.04,rotate180=false){const canonical=drawCanonical(source,inset,rotate180),{gray,chroma}=buildGrayAndChroma(canonical),blurred=blurGray(gray),gradient=gradientMagnitude(gray),ax0=Math.floor(REF_W*.05),ax1=Math.floor(REF_W*.95),ay0=Math.floor(REF_H*.08),ay1=Math.floor(REF_H*.68);return{full:Array.from(blurred),art:regionVector(blurred,1,ax0,ay0,ax1,ay1,1),gradient:Array.from(gradient),chroma:Array.from(chroma),coarse:buildCoarseDescriptor(blurred,gradient,chroma)}}
  function normalizedCorrelation(a,b){if(!a||!b||a.length!==b.length||!a.length)return-1;const ma=mean(a),mb=mean(b),sa=Math.max(1e-5,stddev(a,ma)),sb=Math.max(1e-5,stddev(b,mb));let acc=0;for(let i=0;i<a.length;i++)acc+=((a[i]-ma)/sa)*((b[i]-mb)/sb);return acc/a.length}
  function patchCorrelations(a,b){const scores=[];for(let ry=0;ry<6;ry++){const y0=Math.floor(ry*REF_H/6),y1=Math.floor((ry+1)*REF_H/6);for(let cx=0;cx<4;cx++){const x0=Math.floor(cx*REF_W/4),x1=Math.floor((cx+1)*REF_W/4),v=normalizedCorrelation(regionVector(a,1,x0,y0,x1,y1),regionVector(b,1,x0,y0,x1,y1));if(Number.isFinite(v))scores.push(v)}}scores.sort((a,b)=>b-a);return mean(scores.slice(0,Math.max(1,Math.floor(scores.length*.60))))}
  function chromaSimilarity(a,b){let d=0,n=0;for(let p=0;p<REF_W*REF_H;p+=6){const i=p*2;d+=Math.abs(a[i]-b[i])+Math.abs(a[i+1]-b[i+1]);n+=2}return clamp(1-(d/Math.max(1,n))/.50,0,1)}
  function compareDescriptors(obs,ref){const full=normalizedCorrelation(obs.full,ref.full),art=normalizedCorrelation(obs.art,ref.art),gradient=normalizedCorrelation(obs.gradient,ref.gradient),patches=patchCorrelations(obs.full,ref.full),color=chromaSimilarity(obs.chroma,ref.chroma),total=.25*full+.35*art+.15*gradient+.20*patches+.05*color;return{total,full,art,gradient,patches,color}}
  function coarseSimilarity(a,b){let d=0;const cells=a.length/4;for(let i=0;i<a.length;i+=4){const dl=(a[i]-b[i])*.90,de=(a[i+1]-b[i+1])*.48,dr=(a[i+2]-b[i+2])*.62,db=(a[i+3]-b[i+3])*.62;d+=dl*dl+de*de+dr*dr+db*db}return Math.exp(-1.6*d/Math.max(1,cells))}
  async function descriptorFromUrl(url,inset=.04){const response=await fetch(url);if(!response.ok)throw new Error(`HTTP ${response.status} ${url}`);const bitmap=await createImageBitmap(await response.blob());try{return descriptorFromBitmap(bitmap,inset,false)}finally{bitmap.close()}}
  global.TCGateDescriptor={REF_W,REF_H,COARSE_COLS,COARSE_ROWS,descriptorFromBitmap,descriptorFromUrl,compareDescriptors,coarseSimilarity};
})(globalThis);
