// Data contract and deterministic layout, independent of the spreadsheet runtime.
export const SCHEMA_VERSION = '1.0.0';
export const ENGINE_VERSION = '1.2.0';
const plain = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const empty = v => v === null || v === undefined || v === '';
export function columnName(n) { let s='';for(n++;n>0;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s;return s; }
export function numeral(n) { const a='零一二三四五六七八九';if(n<10)return a[n];if(n<20)return '十'+(n%10?a[n%10]:'');if(n<100)return a[Math.floor(n/10)]+'十'+(n%10?a[n%10]:'');return String(n); }
function isDate(v) { return /^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0,10)===v; }
function unknown(obj,allowed,at,errors) { if(!plain(obj)) { errors.push(`${at}: expected object`);return; }for(const k of Object.keys(obj))if(!allowed.includes(k))errors.push(`${at}: unknown field ${k}`); }
export function sourceRows(sources) {return sources.map((s,i)=>({id:s.id,values:{no:numeral(i+1),topic:s.topic,code:s.id,publisher:s.publisher,date:{type:'date',value:s.publishedAt},support:s.support,url:'打开原文',remarks:s.limitations??''}}));}
export function validateReport(r) {
 const errors=[],warnings=[];unknown(r,['schemaVersion','id','title','filename','asOf','sources','sheets'],'report',errors);
 if(errors.length)return {errors,warnings};
 if(r.schemaVersion!==SCHEMA_VERSION)errors.push(`schemaVersion: expected ${SCHEMA_VERSION}`);
 for(const k of ['id','title','filename'])if(typeof r[k]!=='string'||!r[k].trim())errors.push(`${k}: required string`);
 if(typeof r.filename==='string'&&(!/\.xlsx$/i.test(r.filename)||/[\\/:*?"<>|]/.test(r.filename)||r.filename==='..'))errors.push('filename: must be an xlsx basename');
 if(r.asOf!==undefined&&!isDate(r.asOf))errors.push('asOf: invalid ISO date');
 if(r.sources!==undefined&&!Array.isArray(r.sources))errors.push('sources: expected array');
 const sources=Array.isArray(r.sources)?r.sources:[],sourceIds=new Set(),sourceUrls=new Set();
 sources.forEach((s,i)=>{const at=`sources[${i}]`;unknown(s,['id','topic','publisher','publishedAt','support','url','limitations'],at,errors);if(!plain(s))return;
  for(const k of ['id','topic','publisher','publishedAt','support','url'])if(typeof s[k]!=='string'||!s[k].trim())errors.push(`${at}.${k}: required string`);
  if(!/^[A-Za-z][A-Za-z0-9_-]*$/.test(s.id??''))errors.push(`${at}.id: invalid identifier`);
  if(sourceIds.has(s.id))errors.push(`${at}: duplicate source id`);sourceIds.add(s.id);
  if(!isDate(s.publishedAt??''))errors.push(`${at}: invalid publishedAt`);
  try {const u=new URL(s.url);if(!['http:','https:'].includes(u.protocol)||u.username||u.password)throw Error();}catch {errors.push(`${at}: source URL must be http(s), without credentials`);}
  if(sourceUrls.has(s.url))errors.push(`${at}: duplicate URL; reuse one source id`);sourceUrls.add(s.url);
  if(s.limitations!==undefined&&typeof s.limitations!=='string')errors.push(`${at}.limitations: expected string`);
 });
 if(!Array.isArray(r.sheets)||!r.sheets.length)return {errors:[...errors,'sheets: nonempty array required'],warnings};
 for(const s of r.sheets){
  if(!plain(s)||!Array.isArray(s.columns)||s.columns.some(c=>!plain(c))||
   (s.rows!==undefined&&(!Array.isArray(s.rows)||s.rows.some(row=>!plain(row)||!plain(row.values)))))
   errors.push('sheets: each sheet/column/row must be an object; rows need values objects');
 }
 if(errors.length)return {errors,warnings};
 const ids=new Set(),names=new Set(),usedSources=new Set();let sourceSheetCount=0;
 r.sheets.forEach((s,si)=>{
  const at=`sheets[${si}]`;unknown(s,['id','name','role','title','titleMerge','columns','rows','groups','columnPolicy','emphasisReasonKey','autoFilter'],at,errors);if(!plain(s))return;
  const custom=s.columnPolicy==='custom';
  if(s.columnPolicy!==undefined&&!['standard','custom'].includes(s.columnPolicy))errors.push(`${at}: invalid columnPolicy`);
  if(s.autoFilter!==undefined&&typeof s.autoFilter!=='boolean')errors.push(`${at}: autoFilter must be boolean`);
  if(custom&&s.role==='sources')errors.push(`${at}: sources use the standard column policy`);
  if(s.titleMerge!==undefined&&typeof s.titleMerge!=='boolean')errors.push(`${at}: titleMerge must be boolean`);
  if(!/^[A-Za-z][A-Za-z0-9_-]*$/.test(s.id??'')||ids.has(s.id))errors.push(`${at}: invalid/duplicate sheet id`);ids.add(s.id);
  if(typeof s.name!=='string'||!s.name||s.name.length>31||/[\\/?*\[\]:]/.test(s.name)||names.has(s.name.toLowerCase()))errors.push(`${at}: invalid/duplicate sheet name`);else names.add(s.name.toLowerCase());
  if(!['overview','detail','comparison','sources'].includes(s.role))errors.push(`${at}: unsupported role`);
  if(s.title!==undefined&&(typeof s.title!=='string'||(s.role==='overview'?!s.title.includes('概览'):!s.title.startsWith(s.name))))errors.push(`${at}: title must reflect sheet identity`);
  if(!Array.isArray(s.columns)||s.columns.length<3||s.columns.length>12){errors.push(`${at}: 3–12 columns required`);return;}
  const keys=new Set();s.columns.forEach((c,ci)=>{unknown(c,['key','label','width','align','numberFormat'],`${at}.columns[${ci}]`,errors);if(!plain(c))return;
   if(!/^[A-Za-z][A-Za-z0-9_-]*$/.test(c.key??'')||keys.has(c.key))errors.push(`${at}: invalid/duplicate column key`);keys.add(c.key);
   if(typeof c.label!=='string'||!c.label.trim())errors.push(`${at}: missing column label`);
   if(c.width!==undefined&&(!Number.isFinite(c.width)||c.width<8||c.width>85))errors.push(`${at}.${c.key}: width must be 8–85`);
   if(c.align!==undefined&&!['left','center'].includes(c.align))errors.push(`${at}.${c.key}: align must be left/center`);
   if(ci<2&&c.align&&c.align!=='center')errors.push(`${at}: first two columns must be centered`);
   if(c.numberFormat!==undefined&&typeof c.numberFormat!=='string')errors.push(`${at}: invalid numberFormat`);
  });
  if(!custom&&(s.columns[0]?.key!=='no'||s.columns[0]?.label!=='编号'||s.columns.at(-1)?.key!=='remarks'||s.columns.at(-1)?.label!=='备注'))errors.push(`${at}: first/last columns must be no 编号 / remarks 备注`);
  const reasonKey=s.emphasisReasonKey??'remarks';
  if(s.emphasisReasonKey!==undefined&&(!custom||!keys.has(reasonKey)||s.columns.slice(0,2).some(c=>c.key===reasonKey)))errors.push(`${at}: emphasisReasonKey requires a custom business column`);
  if(s.autoFilter&&s.groups?.length)errors.push(`${at}: autoFilter cannot be combined with body merges`);
  if(s.role==='sources'){
   sourceSheetCount++;if(s.rows!==undefined||s.groups!==undefined)errors.push(`${at}: sources rows are derived, do not provide rows/groups`);
   if([...keys].join(',')!=='no,topic,code,publisher,date,support,url,remarks')errors.push(`${at}: source columns must be no,topic,code,publisher,date,support,url,remarks`);
   return;
  }
  if(!Array.isArray(s.rows)||!s.rows.length){errors.push(`${at}: nonempty rows required`);return;}
  const rowIds=new Set();s.rows.forEach((row,ri)=>{unknown(row,['id','values','refs','emphasis','formats','targetSheetId','height'],`${at}.rows[${ri}]`,errors);if(!plain(row))return;
   if(typeof row.id!=='string'||!row.id||rowIds.has(row.id))errors.push(`${at}: invalid/duplicate row id`);rowIds.add(row.id);
   if(!plain(row.values)){errors.push(`${at}.${row.id}: values object required`);return;}
   for(const [k,v]of Object.entries(row.values)){
    if(!keys.has(k))errors.push(`${at}.${row.id}: unknown value field ${k}`);
    if(plain(v)){if(Object.keys(v).sort().join(',')!=='type,value'||v.type!=='date'||!isDate(v.value??''))errors.push(`${at}.${row.id}.${k}: only typed ISO dates supported`);}
    else if(v!==null&&!['string','number','boolean'].includes(typeof v)||typeof v==='number'&&!Number.isFinite(v))errors.push(`${at}.${row.id}.${k}: invalid scalar`);
   }
   if(!custom&&!empty(row.values.no)&&!/^[一二三四五六七八九十百]+$/.test(row.values.no))errors.push(`${at}.${row.id}: use Chinese display numbering`);
   for(const k of ['refs','formats'])if(row[k]!==undefined&&!plain(row[k]))errors.push(`${at}.${row.id}.${k}: expected object`);
   if(plain(row.refs))for(const [k,v]of Object.entries(row.refs)){
    if(!keys.has(k)||typeof row.values[k]!=='string'||!Array.isArray(v)||!v.length)errors.push(`${at}.${row.id}: refs require a populated text field and array`);
    if(Array.isArray(v))for(const id of v){usedSources.add(id);if(!sourceIds.has(id))errors.push(`${at}.${row.id}: unknown source ${id}`);}
   }
   if(plain(row.formats))for(const[k,v]of Object.entries(row.formats))if(!keys.has(k)||typeof v!=='string'||typeof row.values[k]!=='number')errors.push(`${at}.${row.id}: formats require a numeric value and valid key`);
   if(row.emphasis!==undefined&&!Array.isArray(row.emphasis))errors.push(`${at}.${row.id}: emphasis array required`);
   for(const k of Array.isArray(row.emphasis)?row.emphasis:[]){
    if(!keys.has(k)||s.columns.slice(0,2).some(c=>c.key===k)||k===reasonKey||empty(row.values[k]))errors.push(`${at}.${row.id}: emphasis must target populated business fields`);
    if(typeof row.values[reasonKey]!=='string'||!row.values[reasonKey].trim())errors.push(`${at}.${row.id}: emphasis needs a visible remark explaining why`);
   }
   if(row.height!==undefined&&(!Number.isFinite(row.height)||row.height<40||row.height>409))errors.push(`${at}.${row.id}: invalid height`);
   if(row.targetSheetId!==undefined&&s.role!=='overview')errors.push(`${at}.${row.id}: targetSheetId belongs only in overview`);
  });
  if(s.groups!==undefined&&!Array.isArray(s.groups))errors.push(`${at}: groups array required`);
  const covered=new Set();for(const g of Array.isArray(s.groups)?s.groups:[]){unknown(g,['from','to','fields'],`${at}.group`,errors);if(!plain(g))continue;
   const start=s.rows.findIndex(x=>x.id===g.from),end=s.rows.findIndex(x=>x.id===g.to);
   if(start<0||end<=start||!Array.isArray(g.fields)||!g.fields.length){errors.push(`${at}: invalid group endpoints/fields`);continue;}
   const first2=s.columns.slice(0,2).map(c=>c.key);
   if(first2.some(k=>g.fields.includes(k))&&!first2.every(k=>g.fields.includes(k)))errors.push(`${at}: grouping no/topic must have the same span`);
   for(const k of g.fields){
    if(!keys.has(k)||empty(s.rows[start].values?.[k]))errors.push(`${at}: invalid/empty group anchor ${k}`);
    for(let j=start;j<=end;j++){const key=`${j}:${k}`;if(covered.has(key))errors.push(`${at}: overlapping groups`);covered.add(key);
     if(j>start&&!empty(s.rows[j].values?.[k]))errors.push(`${at}: merge would overwrite ${s.rows[j].id}.${k}`);
     if(s.rows[j].refs?.[k]||s.rows[j].emphasis?.includes(k))errors.push(`${at}: group field cannot contain refs/emphasis`);
    }
   }
  }
  s.rows.forEach((row,j)=>s.columns.slice(0,2).forEach(c=>{if(empty(row.values?.[c.key])&&!covered.has(`${j}:${c.key}`))errors.push(`${at}.${row.id}: ungrouped blank ${c.key}`);}));
 });
 if(r.sheets.length>1){
  const o=r.sheets[0];if(o.role!=='overview'||o.name!=='0 概览')errors.push('multi-sheet reports must start with 0 概览');
  r.sheets.slice(1).forEach((s,i)=>{if(!s.name?.startsWith(`${i+1} `)||s.role==='overview')errors.push('detail sheets need sequential names 1, 2, ...');});
  if(o.rows?.map(x=>x.targetSheetId).join('|')!==r.sheets.slice(1).map(x=>x.id).join('|'))errors.push('overview order/targets must match detail sheets exactly');
  o.rows?.forEach((row,i)=>{const detail=r.sheets[i+1],key=o.columns?.[1]?.key;if(detail&&row.values?.[key]!==detail.name.replace(/^\d+ /,''))errors.push('overview topic must equal target sheet topic');});
 }
 if(sources.length&&sourceSheetCount!==1)errors.push('sources require exactly one sources sheet');
 if(!sources.length&&sourceSheetCount)errors.push('empty sources sheet is not allowed');
 for(const id of sourceIds)if(!usedSources.has(id))errors.push(`unused source: ${id}`);
 if(r.sheets.some(s=>s.role==='comparison'))warnings.push('Comparison scope, units and conditions still require content review.');
 return {errors,warnings};
}
export function textWidth(text,size=16){return [...text].reduce((n,c)=>n+(c.charCodeAt(0)>255?1: /[MW@]/.test(c)?0.9:/[il .,:;'!]/.test(c)?0.32:0.56),0)*size*4/3;}
export function wrapText(value,width,size=16,center=false){
 if(typeof value!=='string'||!value)return value;
 const max=width*8-(center?20:44);const result=[];
 for(const paragraph of value.split('\n')){
  // Keep closing punctuation with its preceding character and opening punctuation with the next token.
  let line='';const tokens=paragraph.match(/[（【“《(]*(?:[A-Za-z0-9][A-Za-z0-9_.,:/%+()-]*|.)[，。；：！？、）】”》,;:!?)]*/gu)??[];
  for(const token of tokens){if(textWidth(token,size)>max)throw Error(`Unbreakable token exceeds width: ${token.slice(0,50)}`);if(line&&textWidth(line+token,size)>max){result.push(line.trimEnd());line=token.trimStart();}else line+=token;}
  result.push(line);
 }
 return result.join('\n');
}
export function compileReport(r,theme){
 const result=validateReport(r);if(result.errors.length)throw Error(result.errors.join('\n'));
 const sheets=r.sheets.map((s,si)=>{
  const cols=s.columns.map((c,i)=>({...c,width:c.width??(i===0?9:i===1?22:34),align:i<2?'center':c.align??'left'}));
  const title=s.title??s.name,titleMerge=s.titleMerge!==false;let titleIndex=0;
  if(titleMerge){
   if(textWidth(title,theme.titleSize)+30>cols.reduce((n,c)=>n+c.width*8,0))throw Error(`${s.name}: shorten title; title exceeds table width`);
  }else{
   titleIndex=2;cols.forEach((c,i)=>{if(i>=2&&c.width>cols[titleIndex].width)titleIndex=i;});
   cols[titleIndex].width=Math.max(cols[titleIndex].width,Math.ceil((textWidth(title,theme.titleSize)+30)/8));
   if(cols[titleIndex].width>85)throw Error(`${s.name}: shorten title; a single-cell title would exceed width 85`);
  }
  const rawRows=s.role==='sources'?sourceRows(r.sources):s.rows;
  const rows=rawRows.map((row,i)=>{
   const values=cols.map(c=>{let v=row.values[c.key]??null;if(row.refs?.[c.key])v+=` [${row.refs[c.key].join('、')}]`;return wrapText(v,c.width,theme.bodySize,c.align==='center');});
   const lines=Math.max(...values.map(v=>typeof v==='string'?v.split('\n').length:1));
   const height=Math.max(theme.minRowHeight,row.height??0,lines*theme.lineHeight+theme.verticalPadding);
   if(height>409)throw Error(`${s.name}/${row.id}: split this row, height exceeds Excel limit`);
   return {id:row.id,values,height,emphasis:row.emphasis??[],formats:row.formats??{}};
  });
  const merges=(s.groups??[]).flatMap(g=>g.fields.map(k=>{const col=columnName(cols.findIndex(c=>c.key===k)+1);return `${col}${4+rawRows.findIndex(x=>x.id===g.from)}:${col}${4+rawRows.findIndex(x=>x.id===g.to)}`;}));
  const links=s.role==='sources'?r.sources.map((src,i)=>({cell:`${columnName(cols.findIndex(c=>c.key==='url')+1)}${i+4}`,url:src.url})):[];
  const titleRange=titleMerge?`B2:${columnName(cols.length)}2`:null;
  if(titleRange)merges.unshift(titleRange);
  return {id:s.id,name:s.name,role:s.role,title,titleCell:`${columnName(titleIndex+1)}2`,titleRange,columns:cols,rows,merges,links,autoFilter:s.autoFilter===true,last:rows.length+3,end:columnName(cols.length),gutter:columnName(cols.length+1),index:si};
 });return {schemaVersion:SCHEMA_VERSION,engineVersion:ENGINE_VERSION,themeVersion:theme.themeVersion,title:r.title,asOf:r.asOf??null,filename:r.filename,sheets,warnings:result.warnings};
}
