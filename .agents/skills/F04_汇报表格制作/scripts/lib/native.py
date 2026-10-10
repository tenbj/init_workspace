"""Scoped OOXML finishing + re-open verification. Does not author worksheet data."""
import sys, json, zipfile, pathlib, copy, re, datetime, xml.etree.ElementTree as E
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
E.register_namespace('',S);E.register_namespace('r',R)
def q(t):return '{'+S+'}'+t
def parse(z,name):return E.fromstring(z[name])
def xml(t):return E.tostring(t,encoding='utf-8',xml_declaration=True)
def col(n):
 s=''
 while n:n,a=divmod(n-1,26);s=chr(65+a)+s
 return s
def cell_value(c,strings):
 if c is None:return None
 if c.find(q('f')) is not None:raise ValueError('Unexpected formula in content-only report')
 v=c.find(q('v'));t=c.get('t')
 if t=='inlineStr':return ''.join(c.find(q('is')).itertext())
 if v is None:return None
 if t=='s':return strings[int(v.text)]
 if t=='b':return v.text=='1'
 if t in ('str','e'):return v.text or ''
 if v.text is None:return None
 try:return float(v.text)
 except ValueError:return v.text
def package(file):
 with zipfile.ZipFile(file) as z:
  if z.testzip():raise ValueError('Damaged xlsx ZIP')
  return {n:z.read(n) for n in z.namelist()}
def eq(actual,want):
 if isinstance(want,dict):return actual==(datetime.date.fromisoformat(want['value'])-datetime.date(1899,12,30)).days
 if want is None or want=='':return actual in (None,'')
 if isinstance(want,bool):return actual is want
 return actual==want
def check_values(data,model):
 strings=[''.join(s.itertext()) for s in parse(data,'xl/sharedStrings.xml')] if 'xl/sharedStrings.xml' in data else []
 count=0
 for i,s in enumerate(model['sheets'],1):
  t=parse(data,f'xl/worksheets/sheet{i}.xml');cells={c.get('r'):c for c in t.findall('.//'+q('c'))}
  for j,row in enumerate(s['rows'],4):
   for k,want in enumerate(row['values'],2):
    addr=f'{col(k)}{j}';got=cell_value(cells.get(addr),strings)
    if not eq(got,want):raise ValueError(f'{s["name"]}!{addr}: exported value differs: {got!r} != {want!r}')
    count+=1
  if cell_value(cells.get(s['titleCell']),strings)!=s['title']:raise ValueError('Title changed')
  for j,c in enumerate(s['columns'],2):
   if cell_value(cells.get(f'{col(j)}3'),strings)!=c['label']:raise ValueError('Header changed')
 return count
def main(file,model_file,log_file):
 file=pathlib.Path(file);model=json.loads(pathlib.Path(model_file).read_text(encoding='utf-8'));theme=model['theme'];data=package(file)
 check_values(data,model)
 styles=parse(data,'xl/styles.xml');xfs=styles.find(q('cellXfs'));cache={}
 def style(old,indent,border=None):
  key=(old,indent,border)
  if key in cache:return cache[key]
  x=copy.deepcopy(xfs[old]);a=x.find(q('alignment'))
  if a is None:a=E.SubElement(x,q('alignment'))
  a.set('indent',str(indent));x.set('applyAlignment','1')
  if border is not None:x.set('borderId',str(border));x.set('applyBorder','1')
  cache[key]=len(xfs);xfs.append(x);return cache[key]
 for i,s in enumerate(model['sheets'],1):
  f=f'xl/worksheets/sheet{i}.xml';t=parse(data,f)
  for c in t.findall('.//'+q('c')):
   letters,row=re.fullmatch(r'([A-Z]+)(\d+)',c.get('r')).groups();row=int(row);old=int(c.get('s','0'))
   if row==2:c.set('s',str(style(old,0,0)))
   elif row==3:c.set('s',str(style(old,0)))
   elif 4<=row<=s['last'] and 'B'<=letters<=s['end']:
    idx=ord(letters)-ord('B');c.set('s',str(style(old,0 if s['columns'][idx]['align']=='center' else 1)))
  view=t.find(q('sheetViews')+'/'+q('sheetView'));view.set('showGridLines','0');view.set('zoomScale','80')
  if s.get('autoFilter'):
   af=E.Element(q('autoFilter'),{'ref':f'B3:{s["end"]}{s["last"]}'})
   later={'sortState','dataConsolidate','customSheetViews','mergeCells','phoneticPr','conditionalFormatting','dataValidations','hyperlinks','printOptions','pageMargins','pageSetup','headerFooter','drawing','extLst'}
   pos=next((j for j,c in enumerate(t) if c.tag.split('}')[-1] in later),len(t));t.insert(pos,af)
  for selection in view.findall(q('selection')):selection.set('activeCell','A1');selection.set('sqref','A1')
  if s['links']:
   links=E.Element(q('hyperlinks'));rf=f'xl/worksheets/_rels/sheet{i}.xml.rels'
   rels=parse(data,rf) if rf in data else E.Element('{'+P+'}Relationships')
   for j,l in enumerate(s['links']):
    rid=f'rIdR01Source{j}';E.SubElement(links,q('hyperlink'),{'ref':l['cell'],'{'+R+'}id':rid})
    E.SubElement(rels,'{'+P+'}Relationship',{'Id':rid,'Type':R+'/hyperlink','Target':l['url'],'TargetMode':'External'})
   # Insert before page settings; preserve any existing unrelated parts.
   later={'printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks','customProperties','cellWatches','ignoredErrors','smartTags','drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst'}
   pos=next((j for j,c in enumerate(t) if c.tag.split('}')[-1] in later),len(t));t.insert(pos,links);data[rf]=xml(rels)
  prop=t.find(q('sheetPr'))
  if prop is None:prop=E.Element(q('sheetPr'));t.insert(0,prop)
  setup=prop.find(q('pageSetUpPr'))
  if setup is None:setup=E.SubElement(prop,q('pageSetUpPr'))
  setup.set('fitToPage','1')
  ps=t.find(q('pageSetup'))
  if ps is None:
   ps=E.Element(q('pageSetup'));later={'headerFooter','rowBreaks','colBreaks','drawing','legacyDrawing','tableParts','extLst'};pos=next((j for j,c in enumerate(t) if c.tag.split('}')[-1] in later),len(t));t.insert(pos,ps)
  ps.set('orientation','landscape');ps.set('paperSize','8' if sum(c['width'] for c in s['columns'])>175 else '9');ps.set('fitToWidth','1');ps.set('fitToHeight','0')
  data[f]=xml(t)
 xfs.set('count',str(len(xfs)));data['xl/styles.xml']=xml(styles)
 book=parse(data,'xl/workbook.xml');defined=book.find(q('definedNames'))
 if defined is None:
  defined=E.Element(q('definedNames'));later={'calcPr','oleSize','customWorkbookViews','pivotCaches','smartTagPr','smartTagTypes','webPublishing','fileRecoveryPr','webPublishObjects','extLst'};pos=next((j for j,c in enumerate(book) if c.tag.split('}')[-1] in later),len(book));book.insert(pos,defined)
 for i,s in enumerate(model['sheets']):
  escaped=s['name'].replace("'","''")
  E.SubElement(defined,q('definedName'),{'name':'_xlnm.Print_Area','localSheetId':str(i)}).text=f"'{escaped}'!$A$1:${s['gutter']}${s['last']+1}"
  E.SubElement(defined,q('definedName'),{'name':'_xlnm.Print_Titles','localSheetId':str(i)}).text=f"'{escaped}'!$1:$3"
 data['xl/workbook.xml']=xml(book)
 temp=file.with_suffix('.native.xlsx')
 with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in data.items():z.writestr(n,b)
 temp.replace(file)
 # Verify the saved package, not just the in-memory model.
 saved=package(file);checked=check_values(saved,model);styles=parse(saved,'xl/styles.xml');xfs=styles.find(q('cellXfs'));fonts=styles.find(q('fonts'))
 formats={'0':'General','1':'0','2':'0.00','3':'#,##0','4':'#,##0.00','9':'0%','10':'0.00%','11':'0.00E+00','12':'# ?/?','13':'# ??/??','14':'mm-dd-yy','49':'@'}
 formats.update({n.get('numFmtId'):n.get('formatCode') for n in styles.findall(q('numFmts')+'/'+q('numFmt'))})
 def require(ok,msg):
  if not ok:raise ValueError(msg)
 actual_names=[s.get('name') for s in parse(saved,'xl/workbook.xml').find(q('sheets'))];require(actual_names==[s['name'] for s in model['sheets']],'Sheet order/name mismatch')
 for i,s in enumerate(model['sheets'],1):
  t=parse(saved,f'xl/worksheets/sheet{i}.xml');merges=[m.get('ref') for m in t.findall(q('mergeCells')+'/'+q('mergeCell'))];require(set(merges)==set(s['merges']),'Merged range mismatch')
  for m in merges:
   if m==s.get('titleRange'):require(m==f'B2:{s["end"]}2','Title merge must cover only the table width on row 2')
   else:require(m.split(':')[0].rstrip('0123456789')==m.split(':')[1].rstrip('0123456789'),'Horizontal body merge forbidden')
  pane=t.find(q('sheetViews')+'/'+q('sheetView')+'/'+q('pane'));require(pane is not None and pane.get('ySplit')=='3' and pane.get('xSplit','0')=='0','Freeze pane mismatch')
  require(t.find(q('pageSetup')).get('fitToHeight')=='0','Print height must be automatic')
  if s.get('autoFilter'):require(t.find(q('autoFilter')).get('ref')==f'B3:{s["end"]}{s["last"]}','Filter range mismatch')
  for c in t.findall('.//'+q('c')):
   letters,row=re.fullmatch(r'([A-Z]+)(\d+)',c.get('r')).groups();row=int(row)
   if not ('B'<=letters<=s['end'] and 2<=row<=s['last']):continue
   x=xfs[int(c.get('s','0'))];a=x.find(q('alignment'));font=fonts[int(x.get('fontId'))];idx=ord(letters)-ord('B')
   require(font.find(q('name')).get('val')==theme['font'],'Font mismatch')
   require(float(font.find(q('sz')).get('val'))==theme['titleSize' if row==2 else 'headerSize' if row==3 else 'bodySize'],'Font size mismatch')
   if row==2:
    require(x.get('borderId','0')=='0','Title border present')
    require(a is not None and a.get('horizontal')=='center' and a.get('vertical')=='center' and a.get('indent')=='0','Title alignment mismatch')
    continue
   if row==3:require(a.get('horizontal')=='center' and a.get('indent')=='0','Header alignment mismatch');continue
   require(a.get('horizontal')==s['columns'][idx]['align'],'Body alignment mismatch')
   require(a.get('indent')==('0' if s['columns'][idx]['align']=='center' else '1'),'Indent mismatch')
   b=font.find(q('b'));bold=b is not None and b.get('val','1')!='0';require(bold==(idx<2),'Unexpected bold')
   key=s['columns'][idx]['key'];expected=theme['red'] if key in s['rows'][row-4]['emphasis'] else theme['blue'] if any(l['cell']==c.get('r') for l in s['links']) else theme['black']
   require(font.find(q('color')).get('rgb','').upper().endswith(expected[1:]),'Body color mismatch')
   value=s['rows'][row-4]['values'][idx]
   expected_format=s['rows'][row-4]['formats'].get(key,'yyyy-mm-dd' if isinstance(value,dict) else s['columns'][idx].get('numberFormat'))
   if expected_format is not None:require(formats.get(x.get('numFmtId','0'))==expected_format,'Number/date format mismatch')
  links=t.findall(q('hyperlinks')+'/'+q('hyperlink'));require(len(links)==len(s['links']),'Hyperlink count mismatch')
  if links:
   rels={r.get('Id'):r.get('Target') for r in parse(saved,f'xl/worksheets/_rels/sheet{i}.xml.rels')}
   require({l.get('ref'):rels[l.get('{'+R+'}id')] for l in links}=={l['cell']:l['url'] for l in s['links']},'Hyperlink target mismatch')
 pathlib.Path(log_file).write_text(json.dumps({'status':'passed','cellsCompared':checked,'sheets':len(model['sheets']),'checks':['values','sheet_order','fonts_and_sizes','number_date_formats','emphasis','alignment','indent','title_merge','vertical_body_merges','freeze','hyperlinks','print_height'],'visualReview':'pending'},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
 try:main(*sys.argv[1:])
 except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
