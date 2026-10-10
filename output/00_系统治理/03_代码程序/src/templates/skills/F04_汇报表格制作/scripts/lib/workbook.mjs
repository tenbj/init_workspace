import {columnName} from './model.mjs';
export function authorWorkbook(Workbook,model,theme){
 const wb=Workbook.create();
 for(const m of model.sheets){
  const s=wb.worksheets.add(m.name);s.showGridLines=false;s.freezePanes.freezeRows(theme.freezeRows);s.tabColor=theme.blue;
  s.getRange(`A1:${m.gutter}${m.last+1}`).format={fill:theme.white,font:{name:theme.font,size:theme.bodySize,bold:false,color:theme.black}};
  s.getRange(`A1:A${m.last+1}`).format.columnWidth=theme.leftGutter;s.getRange(`${m.gutter}1:${m.gutter}${m.last+1}`).format.columnWidth=theme.rightGutter;
  m.columns.forEach((c,i)=>s.getRange(`${columnName(i+1)}1:${columnName(i+1)}${m.last+1}`).format.columnWidth=c.width);
  s.getRange(`A1:${m.gutter}1`).format.rowHeight=theme.topHeight;
  s.getRange(`B2:${m.end}2`).format={rowHeight:theme.titleHeight,font:{name:theme.font,size:theme.titleSize,bold:true,color:theme.blue},horizontalAlignment:'center',verticalAlignment:'center'};
  s.getRange(m.titleCell).values=[[m.title]];
  s.getRange(`B3:${m.end}3`).values=[m.columns.map(c=>c.label)];
  s.getRange(`B3:${m.end}3`).format={rowHeight:theme.headerHeight,wrapText:true,fill:theme.blue,font:{name:theme.font,size:theme.headerSize,bold:true,color:theme.white},horizontalAlignment:'center',verticalAlignment:'center',borders:{preset:'all',style:'thin',color:theme.white}};
  const values=m.rows.map(r=>r.values.map(v=>v&&typeof v==='object'?(Date.parse(v.value+'T00:00:00Z')-Date.UTC(1899,11,30))/86400000:typeof v==='string'&&v.startsWith('=')?"'"+v:v));
  s.getRange(`B4:${m.end}${m.last}`).values=values;
  s.getRange(`B4:${m.end}${m.last}`).format={wrapText:true,verticalAlignment:'center',borders:{preset:'all',style:'thin',color:theme.black}};
  m.columns.forEach((c,i)=>{const range=s.getRange(`${columnName(i+1)}4:${columnName(i+1)}${m.last}`);range.format.horizontalAlignment=c.align;range.format.font.bold=i<2;if(c.numberFormat)range.setNumberFormat(c.numberFormat);});
  m.rows.forEach((r,i)=>{s.getRange(`B${i+4}:${m.end}${i+4}`).format.rowHeight=r.height;r.values.forEach((v,j)=>{const cell=s.getRange(`${columnName(j+1)}${i+4}`);if(v&&typeof v==='object')cell.setNumberFormat('yyyy-mm-dd');if(r.formats[m.columns[j].key])cell.setNumberFormat(r.formats[m.columns[j].key]);});for(const k of r.emphasis)s.getRange(`${columnName(m.columns.findIndex(c=>c.key===k)+1)}${i+4}`).format.font={color:theme.red,bold:false};});
  for(const addr of m.merges){const range=s.getRange(addr);range.merge();range.format.borders={preset:'none'};if(addr!==m.titleRange)range.format.borders={preset:'outside',style:'thin',color:theme.black};}
  for(const l of m.links)s.getRange(l.cell).format.font={color:theme.blue,bold:false};
 }
 wb.recalculate();return wb;
}
