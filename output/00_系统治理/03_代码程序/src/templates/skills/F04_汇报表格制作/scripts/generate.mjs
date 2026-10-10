import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {compileReport} from './lib/model.mjs';
import {loadRuntime} from './lib/runtime.mjs';
import {authorWorkbook} from './lib/workbook.mjs';
const run=promisify(execFile),hash=b=>crypto.createHash('sha256').update(b).digest('hex');
function args(argv){const o={};for(let i=0;i<argv.length;i++){const k=argv[i];if(k==='--overwrite')o.overwrite=true;else if(['--input','--output-dir','--runtime-root'].includes(k)){if(!argv[i+1]||argv[i+1].startsWith('--'))throw Error(`${k}: missing value`);o[k.slice(2)]=argv[++i];}else throw Error(`Unknown option ${k}`);}if(!o.input||!o['output-dir'])throw Error('Usage: node generate.mjs --input <report.json> --output-dir <report directory> [--runtime-root <bundled dependencies>] [--overwrite]');return o;}
export async function generate(options){
 const input=path.resolve(options.input),out=path.resolve(options['output-dir']);
 const bytes=await fs.readFile(input),report=JSON.parse(bytes.toString('utf8'));
 const themeBytes=await fs.readFile(new URL('../assets/theme.json',import.meta.url)),theme=JSON.parse(themeBytes);
 const model=compileReport(report,theme);const target=path.join(out,model.filename);
 try{await fs.access(target);if(!options.overwrite)throw Error('Output already exists; choose another directory or explicitly use --overwrite');}catch(e){if(e.code!=='ENOENT')throw e;}
 await fs.mkdir(out,{recursive:true});const mid=path.join(out,'intermediates'),logs=path.join(out,'logs');await fs.mkdir(mid,{recursive:true});await fs.mkdir(logs,{recursive:true});
 const lock=path.join(out,'.r01-generation.lock');const fd=await fs.open(lock,'wx');
 const runId=new Date().toISOString().replace(/[:.]/g,'-')+'-'+crypto.randomBytes(3).toString('hex');
 const runDir=path.join(mid,runId);
 const log={runId,engineVersion:model.engineVersion,schemaVersion:model.schemaVersion,themeVersion:model.themeVersion,inputSha256:hash(bytes),themeSha256:hash(themeBytes),status:'running',visualReview:'pending',warnings:model.warnings};
 try{
  await fs.mkdir(runDir);
  await fs.writeFile(path.join(runDir,'input.json'),bytes);
  const rt=await loadRuntime(options['runtime-root'],mid);const {Workbook,SpreadsheetFile,FileBlob}=rt.artifact;
  const wb=authorWorkbook(Workbook,model,theme);
  const staged=path.join(runDir,'workbook.xlsx'),modelFile=path.join(runDir,'compiled.json');
  await fs.writeFile(modelFile,JSON.stringify({...model,theme},null,2));
  const scan=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!',options:{useRegex:true,maxResults:20}});
  await fs.writeFile(path.join(logs,runId+'-inspect.ndjson'),scan.ndjson);
  await(await SpreadsheetFile.exportXlsx(wb)).save(staged);
  const nativeFile=path.join(logs,runId+'-native.json');
  await run(rt.python,[fileURLToPath(new URL('./lib/native.py',import.meta.url)),staged,modelFile,nativeFile],{windowsHide:true,maxBuffer:1024*1024});
  const saved=await SpreadsheetFile.importXlsx(await FileBlob.load(staged));
  log.previews=[];
  for(let i=0;i<model.sheets.length;i++){
   const s=model.sheets[i];let start=1,height=theme.topHeight+theme.titleHeight+theme.headerHeight,page=1;const ranges=[];
   for(let r=0;r<s.rows.length;r++){
    if(height+s.rows[r].height>1800&&r+4>start){ranges.push([start,r+3]);start=r+4;height=0;}
    height+=s.rows[r].height;
   }
   ranges.push([start,s.last+1]);
   for(const [from,to] of ranges){
    const range=`A${from}:${s.gutter}${to}`;
    const image=await saved.render({sheetName:s.name,range,scale:theme.previewScale,format:'png'});
    const preview=path.join(runDir,`sheet-${i+1}${ranges.length>1?'-part-'+page++:''}.png`);await fs.writeFile(preview,new Uint8Array(await image.arrayBuffer()));log.previews.push({sheet:s.name,range,path:path.relative(out,preview)});
   }
  }
  // Publish only after successful native checks and rendering. Copy atomically on the same volume.
  const publish=path.join(out,`.${runId}.xlsx`);await fs.copyFile(staged,publish);
  try{await fs.rename(publish,target);}catch(e){await fs.unlink(publish).catch(()=>{});throw e;}
  log.status='automated_checks_passed';log.output=target;log.outputSha256=hash(await fs.readFile(target));log.nativeChecks=path.relative(out,nativeFile);
  console.log(JSON.stringify({status:log.status,output:target,sheets:model.sheets.length,visualReview:'pending',previews:log.previews}));return log;
 }catch(e){log.status='failed';log.error=e.message;throw e;}finally{
  try{await fs.writeFile(path.join(logs,runId+'-run.json'),JSON.stringify(log,null,2));}finally{await fd.close();await fs.unlink(lock);}
 }
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))Promise.resolve().then(()=>generate(args(process.argv.slice(2)))).catch(e=>{console.error(e.message);process.exitCode=1;});
