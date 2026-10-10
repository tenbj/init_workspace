import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {validateReport,compileReport} from './lib/model.mjs';
export {validateReport};
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 try{const input=process.argv[2];if(!input)throw Error('Usage: node validate.mjs <report.json>');const r=JSON.parse(await fs.readFile(input,'utf8'));const theme=JSON.parse(await fs.readFile(new URL('../assets/theme.json',import.meta.url),'utf8'));const v=validateReport(r);if(v.errors.length)throw Error(v.errors.join('\n'));const m=compileReport(r,theme);console.log(JSON.stringify({validation:'passed',sheets:m.sheets.length,warnings:v.warnings}));}catch(e){console.error(e.message);process.exitCode=1;}
}
