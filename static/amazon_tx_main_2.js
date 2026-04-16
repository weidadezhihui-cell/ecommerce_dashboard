function filtered(){
  return ALL.filter(r=>{
    if(selYear!=='all'&&r.year!=selYear) return false;
    if(selMonth!=='all'&&r.month!=selMonth) return false;
    if(selType!=='all'&&r.type!==selType) return false;
    if(selState!=='all'&&r.state!==selState) return false;
    if(selSku!=='all'&&r.sku!==selSku) return false;
    return true;
  });
}

function fmt(n){return'$'+Math.round(n).toLocaleString();}
function fmtd(n){return(n<0?'-$':'$')+Math.abs(Math.round(n)).toLocaleString();}
function fmtp(n){return n.toFixed(1)+'%';}
function destroyChart(k){if(charts[k]){charts[k].destroy();delete charts[k];}}
function updateAll(){const d=filtered();renderOverview(d);renderProducts(d);renderFinancials(d);renderGeo(d);renderRaw(d);}

// ── OVERVIEW ─────────────────────────────────────────────────────────────────
function renderOverview(data){
  const orders=data.filter(r=>r.type==='Order'),refunds=data.filter(r=>r.type==='Refund');
  const grossSales=orders.reduce((s,r)=>s+r.productSales,0);
  const netPayout=data.reduce((s,r)=>s+r.total,0);
  const totalUnits=orders.reduce((s,r)=>s+r.qty,0);
  const refundAmt=refunds.reduce((s,r)=>s+Math.abs(r.productSales),0);
  const refundRate=grossSales>0?(refundAmt/grossSales)*100:0;
  const avgOrder=orders.length>0?grossSales/orders.length:0;
  const advSpend=data.filter(r=>r.type==='Service Fee'&&(r.description||'').toLowerCase().includes('advertis')).reduce((s,r)=>s+Math.abs(r.total),0);
  const byMonth={};
  data.forEach(r=>{
    if(!byMonth[r.monthKey]) byMonth[r.monthKey]={sales:0,net:0};
    if(r.type==='Order') byMonth[r.monthKey].sales+=r.productSales;
    if(r.type==='Refund') byMonth[r.monthKey].refunds=(byMonth[r.monthKey].refunds||0)+Math.abs(r.productSales);
    byMonth[r.monthKey].net+=r.total;
  });
  const mLabels=Object.keys(byMonth).sort();
  const mDisplay=mLabels.map(m=>{const[y,mo]=m.split('-');return MONTH_NAMES[+mo-1]+(mLabels.filter(x=>x.split('-')[1]===mo).length>1?` '${y.slice(2)}`:'');});
  const tCounts={};data.forEach(r=>{tCounts[r.type]=(tCounts[r.type]||0)+1;});
  const prod={};data.filter(r=>r.type==='Order').forEach(r=>{const k=r.sku||'(no SKU)';if(!prod[k])prod[k]={sku:k,desc:r.description,net:0,cnt:0};prod[k].net+=r.total;prod[k].cnt++;});
  const top5=Object.values(prod).sort((a,b)=>b.net-a.net).slice(0,5);
  const p=document.getElementById('p0');
  p.innerHTML=`<div class="kpi-grid" id="kpiGrid0"></div>
    <div class="sec">Monthly revenue & net payout</div>
    <div class="leg" id="trendLeg"></div>
    <div class="chart-wrap" style="height:440px"><canvas id="trendC"></canvas></div>
    <div class="two-col" style="margin-top:16px">
      <div><div class="sec">Transaction mix</div><div class="leg" id="typeLeg"></div><div class="chart-wrap" style="height:400px"><canvas id="typeC"></canvas></div></div>
      <div><div class="sec">Top 5 products by net</div><div class="tbl-wrap"><table id="top5T"><thead><tr><th>SKU</th><th>Description</th><th>Net $</th><th>Orders</th></tr></thead><tbody></tbody></table></div></div>
    </div>`;
  document.getElementById('kpiGrid0').innerHTML=`
    <div class="kpi"><div class="label">Product sales</div><div class="value">${fmt(grossSales)}</div><div class="sub">${orders.length} orders · ${totalUnits} units</div></div>
    <div class="kpi pos"><div class="label">Net payout</div><div class="value">${fmt(netPayout)}</div><div class="sub">After all deductions</div></div>
    <div class="kpi"><div class="label">Net margin</div><div class="value">${grossSales>0?fmtp(netPayout/grossSales*100):'—'}</div></div>
    <div class="kpi neg"><div class="label">Refunds</div><div class="value">${fmtd(-refundAmt)}</div><div class="sub">${fmtp(refundRate)} of sales · ${refunds.length} txns</div></div>
    <div class="kpi"><div class="label">Avg order value</div><div class="value">${fmt(avgOrder)}</div></div>
    <div class="kpi neg"><div class="label">Ad spend</div><div class="value">${fmt(advSpend)}</div></div>`;
  document.getElementById('trendLeg').innerHTML=`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#B5D4F4"></span>Product sales</span><span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#1D9E75"></span>Net payout</span><span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#F09595"></span>Refunds</span>`;
  destroyChart('trend');
  charts.trend=new Chart(document.getElementById('trendC'),{type:'bar',data:{labels:mDisplay,datasets:[
    {label:'Sales',data:mLabels.map(m=>Math.round(byMonth[m].sales)),backgroundColor:'#B5D4F4',borderRadius:3,stack:'a'},
    {label:'Net',data:mLabels.map(m=>Math.round(byMonth[m].net)),backgroundColor:'#1D9E75',borderRadius:3,stack:'b'},
    {label:'Refunds',data:mLabels.map(m=>Math.round(byMonth[m].refunds||0)),backgroundColor:'#F09595',borderRadius:3,stack:'c'}
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},scales:{x:{ticks:{autoSkip:false,maxRotation:0,font:{size:DS.fsAxis}}},y:{ticks:{callback:v=>'$'+v.toLocaleString(),font:{size:DS.fsAxis}}}}}});
  const typeKeys=Object.keys(tCounts),typeCols=['#378ADD','#E24B4A','#EF9F27','#1D9E75','#7F77DD','#73726c'];
  document.getElementById('typeLeg').innerHTML=typeKeys.map((k,i)=>`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:${typeCols[i%typeCols.length]}"></span>${k} (${tCounts[k]})</span>`).join('');
  destroyChart('type');
  charts.type=new Chart(document.getElementById('typeC'),{type:'doughnut',data:{labels:typeKeys,datasets:[{data:typeKeys.map(k=>tCounts[k]),backgroundColor:typeCols.slice(0,typeKeys.length),borderWidth:2,borderColor:'var(--color-background-primary,#fff)'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false,labels:{font:{size:DS.fsLegend},padding:DS.legPad,boxWidth:13}},tooltip:{bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},cutout:'48%'}});
  document.querySelector('#top5T tbody').innerHTML=top5.map(p=>`<tr><td>${p.sku}</td><td style="max-width:150px;overflow:hidden;text-overflow:ellipsis">${(p.desc||'').slice(0,40)}</td><td style="font-weight:500">${fmt(p.net)}</td><td>${p.cnt}</td></tr>`).join('');
}
