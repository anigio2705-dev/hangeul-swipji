'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..');
const courses=['intro','beginner1','beginner2','intermediate1','intermediate2','advanced1','advanced2'];
function lessons(name){return JSON.parse(fs.readFileSync(path.join(root,name+'.html'),'utf8').match(/const units=(\[.*?\]);/s)[1]);}
function reading(language='ko'){
 const html=fs.readFileSync(path.join(root,'reading.html'),'utf8');
 const src=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1].split('function icon(')[0];
 const ctx={document:{getElementById(){return {}}},localStorage:{getItem(){return null}},window:{}};
 vm.createContext(ctx);
 const extra=html.includes('reading-curriculum.js')?fs.readFileSync(path.join(root,'reading-curriculum.js'),'utf8'):'';
 vm.runInContext(extra+'\n'+src+'\nlang='+JSON.stringify(language)+';globalThis.getReading=content;globalThis.getLegacyReading=typeof legacyContent!=="undefined"?legacyContent:content;',ctx);
 return {get:ctx.getReading,legacy:ctx.getLegacyReading};
}
module.exports={root,courses,lessons,reading};
