// Records a review performed by a person or model; this command does not inspect images itself.
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
export async function recordReview(runFile,note){
 if(typeof note!=='string'||!note.trim())throw Error('A concrete review note is required');
 const log=JSON.parse(await fs.readFile(runFile));
 if(log.status!=='automated_checks_passed')throw Error('Automated checks must pass first');
 const sha=crypto.createHash('sha256').update(await fs.readFile(log.output)).digest('hex');
 if(sha!==log.outputSha256)throw Error('Output changed after generation; regenerate and review again');
 const out=path.dirname(log.output);
 for(const p of log.previews)await fs.access(path.join(out,p.path));
 const review={runId:log.runId,status:'reviewed',output:log.output,outputSha256:sha,reviewedAt:new Date().toISOString(),sheets:log.previews.map(p=>p.sheet),note};
 const target=path.join(path.dirname(runFile),log.runId+'-review.json');await fs.writeFile(target,JSON.stringify(review,null,2));return target;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const [runFile,note,...extra]=process.argv.slice(2);
 Promise.resolve().then(()=>{if(!runFile||!note||extra.length)throw Error('Usage: node review.mjs <run-log.json> <review note after examining every preview>');return recordReview(path.resolve(runFile),note);}).then(console.log).catch(e=>{console.error(e.message);process.exitCode=1;});
}
