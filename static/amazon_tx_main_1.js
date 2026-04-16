let ALL=[], charts={};
let selYear='all', selMonth='all', selType='all', selState='all', selSku='all';

// ── Design System: chart font tokens (mirrors CSS --fs-* variables) ───────
const DS = {
  fsAxis:    16,   // axis tick labels  — mirrors --fs-filter: 16px
  fsTooltip: 14,   // tooltip body      — mirrors --fs-subtext: 14px
  fsLegend:  14,   // chart legend labels (when displayed)
  legPad:    15,   // padding between legend items
};

if (typeof Chart !== 'undefined') {
  Chart.defaults.font.size   = DS.fsAxis;
  Chart.defaults.font.family = "system-ui,'Segoe UI',sans-serif";
  Chart.defaults.plugins.tooltip.bodyFont  = {size: DS.fsTooltip};
  Chart.defaults.plugins.tooltip.titleFont = {size: DS.fsTooltip, weight:'600'};
  Chart.defaults.plugins.legend.labels     = {font:{size: DS.fsLegend}, boxWidth:13, padding: DS.legPad};
}

const MONTH_NAMES=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function parseDate(s){
  if(!s) return null;
  if(s instanceof Date) return isNaN(s)?null:s;
  try{const d=new Date(String(s).replace(/ PST| PDT| UTC/i,'').trim());if(!isNaN(d))return d;}catch(e){}
  return null;
}
function n(v){const x=parseFloat((v||'').toString().replace(/[$,]/g,''));return isNaN(x)?0:x;}

// Build a column-index lookup from a header row array.
// Returns a function ci(name, fallback) that finds the best matching column index.
function buildColMap(headerCols){
  const norm=s=>String(s||'').toLowerCase().replace(/[^a-z0-9]/g,'');
  const map={};
  headerCols.forEach((h,i)=>{map[norm(h)]=i;});
  return function ci(name,fallback){
    const k=norm(name);
    if(map[k]!==undefined) return map[k];
    // partial match — find key that starts with k or contains k
    const hit=Object.keys(map).find(mk=>mk.startsWith(k)||mk===k);
    return hit!==undefined?map[hit]:fallback;
  };
}

function parseRows(text){
  const lines=text.split('\n');
  // Scan up to 30 rows for the header (Amazon reports have ~7 metadata rows before headers)
  let headerIdx=-1;
  for(let i=0;i<Math.min(30,lines.length);i++){
    const l=lines[i].toLowerCase();
    if((l.includes('date/time')||l.includes('date time'))&&(l.includes('settlement')||l.includes('type'))){
      headerIdx=i;break;
    }
  }
  if(headerIdx<0){
    // fallback: first row that has many tab-separated columns
    for(let i=0;i<Math.min(30,lines.length);i++){
      if(lines[i].split('\t').length>=20){headerIdx=i;break;}
    }
  }
  const dataStart=headerIdx>=0?headerIdx+1:0;
  const headerCols=headerIdx>=0?lines[headerIdx].split('\t').map(h=>h.replace(/"/g,'').trim()):[];
  const ci=buildColMap(headerCols);

  const rows=[];
  for(let i=dataStart;i<lines.length;i++){
    const cols=lines[i].split('\t');
    if(cols.length<10) continue;
    const raw0=cols[ci('date/time',ci('datetime',0))];
    const dt=parseDate(raw0);
    if(!dt) continue;
    rows.push({
      dt,
      month:dt.getMonth()+1, year:dt.getFullYear(),
      monthKey:dt.getFullYear()+'-'+String(dt.getMonth()+1).padStart(2,'0'),
      settlementId: cols[ci('settlement id',1)]||'',
      type:         (cols[ci('type',2)]||'').trim(),
      orderId:       cols[ci('order id',3)]||'',
      sku:          (cols[ci('sku',4)]||'').trim(),
      description:  (cols[ci('description',5)]||'').trim(),
      qty:           n(cols[ci('quantity',6)]),
      marketplace:   cols[ci('marketplace',7)]||'',
      accountType:   cols[ci('account type',8)]||'',
      fulfillment:   cols[ci('fulfillment',9)]||'',
      city:         (cols[ci('order city',10)]||'').trim(),
      state:        (cols[ci('order state',11)]||'').trim().toUpperCase().slice(0,2),
      postal:       (cols[ci('order postal',12)]||'').trim(),
      taxModel:      cols[ci('tax collection model',ci('taxcollectionmodel',13))]||'',
      productSales:         n(cols[ci('product sales',14)]),
      productSalesTax:      n(cols[ci('product sales tax',15)]),
      shippingCredits:      n(cols[ci('shipping credits',16)]),
      shippingCreditsTax:   n(cols[ci('shipping credits tax',17)]),
      giftWrapCredits:      n(cols[ci('gift wrap credits',18)]),
      giftWrapCreditsTax:   n(cols[ci('giftwrap credits tax',19)]),
      regulatoryFee:        n(cols[ci('regulatory fee',20)]),
      taxOnRegulatoryFee:   n(cols[ci('tax on regulatory fee',21)]),
      promotionalRebates:   n(cols[ci('promotional rebates',22)]),
      promotionalRebatesTax:n(cols[ci('promotional rebates tax',23)]),
      marketplaceWithheldTax:n(cols[ci('marketplace withheld tax',24)]),
      sellingFees:          n(cols[ci('selling fees',25)]),
      fbaFees:              n(cols[ci('fba fees',26)]),
      otherTransactionFees: n(cols[ci('other transaction fees',27)]),
      other:                n(cols[ci('other',cols.length-2)]),
      total:                n(cols[ci('total',cols.length-1)])
    });
  }
  return rows;
}

function processText(txt, label){
  ALL=parseRows(txt);
  if(ALL.length===0){
    document.getElementById('status').textContent='Could not parse — check the file has the correct Amazon transaction headers.';
    return;
  }
  if(label){
    const dz=document.getElementById('dropZone');
    dz.classList.add('file-loaded');
    document.getElementById('fileName').textContent='✓ '+label;
  }
  init();
}

function fmtExcelDate(v){
  // v may be a JS Date (when cellDates:true) or a number serial
  if(v instanceof Date && !isNaN(v)){
    const mo=MONTH_NAMES[v.getMonth()];
    const d=v.getDate(), y=v.getFullYear();
    const hh=String(v.getHours()).padStart(2,'0');
    const mm=String(v.getMinutes()).padStart(2,'0');
    const ss=String(v.getSeconds()).padStart(2,'0');
    return `${mo} ${d}, ${y} ${hh}:${mm}:${ss}`;
  }
  return String(v||'');
}

function handleFileSelect(file){
  if(!file) return;
  document.getElementById('status').textContent='Reading '+file.name+' …';
  const ext=file.name.split('.').pop().toLowerCase();

  if(ext==='xlsx'||ext==='xls'){
    if(typeof XLSX==='undefined'){
      document.getElementById('status').textContent='Excel library not loaded yet — please try again in a moment.';
      return;
    }
    const reader=new FileReader();
    reader.onload=e=>{
      try{
        // cellDates:true → SheetJS returns real JS Date objects for date cells
        const wb=XLSX.read(new Uint8Array(e.target.result),{type:'array',cellDates:true});
        const ws=wb.Sheets[wb.SheetNames[0]];
        // sheet_to_json with header:1 gives a 2-D array; raw:true keeps Date objects intact
        const rows2d=XLSX.utils.sheet_to_json(ws,{header:1,defval:'',raw:true});
        // Build TSV: format Date objects, stringify everything else
        const tsv=rows2d.map(row=>
          row.map(c=>c instanceof Date?fmtExcelDate(c):String(c===null||c===undefined?'':c)).join('\t')
        ).join('\n');
        processText(tsv, file.name);
      }catch(err){
        document.getElementById('status').textContent='Error reading Excel file: '+err.message;
      }
    };
    reader.readAsArrayBuffer(file);
  } else {
    // CSV / TSV text file
    const reader=new FileReader();
    reader.onload=e=>{
      let txt=e.target.result;
      // If no tabs found, try to parse as CSV (handling quoted fields)
      if(txt.indexOf('\t')===-1&&txt.indexOf(',')>-1){
        txt=txt.split('\n').map(line=>{
          const fields=[];let cur='',inQ=false;
          for(let i=0;i<line.length;i++){
            if(line[i]==='"'){inQ=!inQ;}
            else if(line[i]===','&&!inQ){fields.push(cur.trim());cur='';}
            else cur+=line[i];
          }
          fields.push(cur.trim());
          return fields.join('\t');
        }).join('\n');
      }
      processText(txt, file.name);
    };
    reader.readAsText(file);
  }
}

function handleDrop(event){
  event.preventDefault();
  document.getElementById('dropZone').classList.remove('drag-over');
  const file=event.dataTransfer.files[0];
  if(file) handleFileSelect(file);
}

function loadSample(){
  const dz=document.getElementById('dropZone');
  dz.classList.add('file-loaded');
  document.getElementById('fileName').textContent='✓ sample_data.tsv';
  processText(SAMPLE, null);
}

function init(){
  document.getElementById('status').textContent=ALL.length+' rows loaded';
  document.getElementById('filtersRow').style.display='flex';
  document.getElementById('tabBar').style.display='flex';
  buildFilters();updateAll();
}

function buildFilters(){
  const years=[...new Set(ALL.map(r=>r.year))].sort();
  const ySel=document.getElementById('fYear');
  ySel.innerHTML='<option value="all">All years</option>';
  years.forEach(y=>{const o=document.createElement('option');o.value=y;o.text=y;ySel.appendChild(o);});

  // Month dropdown: show only months present in data
  const monthNums=[...new Set(ALL.map(r=>r.month))].sort((a,b)=>a-b);
  const mSel=document.getElementById('fMonth');
  mSel.innerHTML='<option value="all">All months</option>';
  monthNums.forEach(m=>{const o=document.createElement('option');o.value=m;o.text=MONTH_NAMES[m-1];mSel.appendChild(o);});

  const states=[...new Set(ALL.filter(r=>r.state&&/^[A-Z]{2}$/.test(r.state)).map(r=>r.state))].sort();
  const sSel=document.getElementById('fState');
  sSel.innerHTML='<option value="all">All states</option>';
  states.forEach(s=>{const o=document.createElement('option');o.value=s;o.text=s;sSel.appendChild(o);});

  const skus=[...new Set(ALL.filter(r=>r.sku).map(r=>r.sku))].sort();
  const kSel=document.getElementById('fSku');
  kSel.innerHTML='<option value="all">All SKUs</option>';
  skus.forEach(s=>{const o=document.createElement('option');o.value=s;o.text=s;kSel.appendChild(o);});
}
