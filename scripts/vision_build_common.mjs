import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright-core';
import { fileURLToPath } from 'node:url';
export const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export const SOURCE_COMMIT='b63435e2796e0bf4f5118fcc8106a8eec44d1d2f';
export const SOURCE_PATH='public/identification-worker.js';
export const SOURCE_SHA256='306eafe4decdcce26287683bc581cd8ca24a0c2f58cd299873b093942127a14a';
export const DESCRIPTOR_VERSION='tcgate-ident-v5-fast-72x108-b63435e';
export const CHROME=process.env.TCGATE_CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe';
export const readJson=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
export const sha256=data=>import('node:crypto').then(({createHash})=>createHash('sha256').update(data).digest('hex'));
export async function browserPage(){const browser=await chromium.launch({headless:true,executablePath:CHROME,args:['--disable-web-security']});const page=await browser.newPage();await page.addScriptTag({path:path.join(ROOT,'scripts/tcgate_descriptor_compiler.js')});return{browser,page}}
export async function compileUrls(page,entries,concurrency=16,detailed=false){
  return page.evaluate(async({entries,concurrency,detailed})=>{const out=new Array(entries.length);let cursor=0;async function worker(){while(true){const i=cursor++;if(i>=entries.length)return;const e=entries[i],d=await globalThis.TCGateDescriptor.descriptorFromUrl(e.imageUrl);out[i]=detailed?d:d.coarse}}await Promise.all(Array.from({length:concurrency},worker));return out},{entries,concurrency,detailed});
}
