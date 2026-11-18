import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';

export const HEADERS=['排序序号','Type','字段原名','字段名','字段释义','主键'];
export const AUDIT=['first_inserted_dt','etl_dt','last_updated_dt'];

// C06、C18和模型构建程序共用；调用方传入官方运行时artifact-tool。
export async function buildPlatformFields({artifact,contract,template,output,receipt,previewDir}) {
  const {FileBlob,SpreadsheetFile}=artifact;
  const fields=contract.fields;
  if(!Array.isArray(fields)||fields.length<4)throw Error('缺少最终字段合同');
  for(const key of ['name','label'])if(new Set(fields.map(f=>f[key])).size!==fields.length)throw Error(key+'存在重复');
  for(const f of fields){
    if(!f.name||!f.label||!f.comment||!f.type||f.type!==f.type.toLowerCase())throw Error('字段定义不完整或Type非小写：'+f.name);
    if(typeof f.physical_primary_key!=='boolean')throw Error('须明确最终物理主键：'+f.name);
  }
  for(const n of AUDIT)if(fields.find(f=>f.name===n)?.type!=='datetime(3)')throw Error('缺少datetime(3)审计字段：'+n);
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(template));
  const sh=wb.worksheets.getItemAt(0);
  if(JSON.stringify(sh.getRange('A1:F1').values[0])!==JSON.stringify(HEADERS))throw Error('平台模板六列表头已变化，停止生成');
  const old=sh.getUsedRange().values;
  if(old.some(row=>row.slice(6).some(v=>v!==null&&v!=='')))throw Error('模板包含六列以外的内容');
  const ordered=[...AUDIT.map(n=>fields.find(f=>f.name===n)),...fields.filter(f=>!AUDIT.includes(f.name))];
  const rows=ordered.map((f,i)=>[i<3?0:i-2,f.type,f.name,f.label,f.comment,f.physical_primary_key?'是':null]);
  // 原件可能含其他模型旧行；必须清空，不得带入新模型。
  if(old.length>1)sh.getRange(`A2:F${old.length}`).clear({applyTo:'contents'});
  sh.name='字段信息';
  sh.getRange(`A2:F${rows.length+1}`).values=rows;
  [12,21,33,26,80,10].forEach((w,i)=>{sh.getRangeByIndexes(0,i,rows.length+1,1).format.columnWidth=w;});
  sh.getRange(`A2:F${rows.length+1}`).format.font={name:'Microsoft YaHei',size:11};
  sh.getRange(`A1:F${rows.length+1}`).format.verticalAlignment='center';
  sh.getRange(`E2:E${rows.length+1}`).format.wrapText=true;
  rows.forEach((r,i)=>{sh.getRange(`A${i+2}:F${i+2}`).format.rowHeight=Math.max(28,Math.ceil(r[4].length/36)*18+8);});
  wb.recalculate();
  if(JSON.stringify(sh.getRange(`A2:F${rows.length+1}`).values)!==JSON.stringify(rows))throw Error('生成字段回读与合同不一致');
  if(previewDir){
    await fs.mkdir(previewDir,{recursive:true});
    const png=await wb.render({sheetName:sh.name,range:'A1:F8',format:'png',scale:1});
    await fs.writeFile(path.join(previewDir,'平台字段信息.png'),new Uint8Array(await png.arrayBuffer()));
  }
  await fs.mkdir(path.dirname(output),{recursive:true});
  await (await SpreadsheetFile.exportXlsx(wb)).save(output);
  const digest=async p=>crypto.createHash('sha256').update(await fs.readFile(p)).digest('hex');
  const result={generator:'C18/build_platform_fields.mjs',template:path.resolve(template),template_sha256:await digest(template),output:path.resolve(output),output_sha256:await digest(output),field_count:rows.length,headers:HEADERS,primary_keys:rows.filter(r=>r[5]==='是').map(r=>r[2]),platform_import_verified:false};
  await fs.mkdir(path.dirname(receipt),{recursive:true});
  await fs.writeFile(receipt,JSON.stringify(result,null,2));
  try { await fs.rename(output+'.inspect.ndjson',receipt+'.inspect.ndjson'); }catch(e){if(e.code!=='ENOENT')throw e;}
  return result;
}
