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
  // Cash-flow net: Transfer row totals summed then sign flipped (Amazon often stores payouts negative).
  const transferSum=data.filter(r=>r.type==='Transfer').reduce((s,r)=>s+(Number(r.total)||0),0);
  const netPayout=-transferSum;
  const totalUnits=orders.reduce((s,r)=>s+r.qty,0);
  const refundAmt=refunds.reduce((s,r)=>s+Math.abs(r.productSales),0);
  const netProductSales=grossSales-refundAmt;
  const refundRate=grossSales>0?(refundAmt/grossSales)*100:0;
  const avgOrder=orders.length>0?grossSales/orders.length:0;
  const advSpend=data.filter(r=>r.type==='Service Fee'&&(r.description||'').toLowerCase().includes('advertis')).reduce((s,r)=>s+Math.abs(r.total),0);
  const byMonth={};
  data.forEach(r=>{
    if(!byMonth[r.monthKey]) byMonth[r.monthKey]={sales:0,net:0};
    if(r.type==='Order') byMonth[r.monthKey].sales+=r.productSales;
    if(r.type==='Refund') byMonth[r.monthKey].refunds=(byMonth[r.monthKey].refunds||0)+Math.abs(r.productSales);
    if(r.type==='Transfer') byMonth[r.monthKey].net-=Number(r.total)||0;
  });
  const mLabels=Object.keys(byMonth).sort();
  const mDisplay=mLabels.map(m=>{const[y,mo]=m.split('-');return MONTH_NAMES[+mo-1]+(mLabels.filter(x=>x.split('-')[1]===mo).length>1?` '${y.slice(2)}`:'');});
  // Unit sales by SKU for Sales Velocity doughnut
  const skuUnits={};
  data.filter(r=>r.type==='Order'&&r.sku).forEach(r=>{skuUnits[r.sku]=(skuUnits[r.sku]||0)+(Number(r.qty)||0);});
  const skuSorted=Object.entries(skuUnits).sort((a,b)=>b[1]-a[1]);
  const top5sku=skuSorted.slice(0,5);
  const othersUnits=skuSorted.slice(5).reduce((s,[,v])=>s+v,0);
  const totalSkuUnits=skuSorted.reduce((s,[,v])=>s+v,0);
  const velLabels=[...top5sku.map(([k])=>k),...(othersUnits>0?['All others']:[])];
  const velData=[...top5sku.map(([,v])=>v),...(othersUnits>0?[othersUnits]:[])];
  const velCols=['#378ADD','#1D9E75','#EF9F27','#7F77DD','#E24B4A','#94a3b8'];
  // Top-5 by net for table
  const prod={};data.filter(r=>r.type==='Order').forEach(r=>{const k=r.sku||'(no SKU)';if(!prod[k])prod[k]={sku:k,desc:r.description,net:0,cnt:0};prod[k].net+=r.total;prod[k].cnt++;});
  const top5=Object.values(prod).sort((a,b)=>b.net-a.net).slice(0,5);
  const p=document.getElementById('p0');
  p.innerHTML=`<div class="kpi-grid" id="kpiGrid0"></div>
    <div class="sec">Monthly gross sales & net payout</div>
    <div class="leg" id="trendLeg"></div>
    <div class="chart-wrap" style="height:440px"><canvas id="trendC"></canvas></div>
    <div class="two-col" style="margin-top:16px">
      <div><div class="sec">Unit sales distribution</div><div class="leg" id="typeLeg"></div><div class="chart-wrap" style="height:400px"><canvas id="typeC"></canvas></div></div>
      <div><div class="sec">Top 5 products by net payout</div><div class="tbl-wrap"><table id="top5T"><thead><tr><th>SKU</th><th>Description</th><th>Net payout</th><th>Orders</th></tr></thead><tbody></tbody></table></div></div>
    </div>`;
  document.getElementById('kpiGrid0').innerHTML=`
    <div class="kpi"><div class="label">Gross sales</div><div class="value" style="color:${grossSales>=0?'#0F6E56':'#993C1D'}">${fmt(grossSales)}</div><div class="sub">${orders.length} orders · ${totalUnits} units</div></div>
    <div class="kpi neg"><div class="label">Refunds</div><div class="value">${fmtd(-refundAmt)}</div><div class="sub">${grossSales>0?fmtp(refundAmt/grossSales*100)+' of gross sales':'—'}</div></div>
    <div class="kpi"><div class="label">Net product sales</div><div class="value" style="color:${netProductSales>=0?'#0F6E56':'#993C1D'}">${fmt(netProductSales)}</div><div class="sub">${grossSales>0?fmtp(netProductSales/grossSales*100)+' of gross sales':'—'}</div></div>
    <div class="kpi"><div class="label">Net payout</div><div class="value" style="color:${netPayout>=0?'#0F6E56':'#993C1D'}">${fmt(netPayout)}</div><div class="sub">${grossSales>0?fmtp(netPayout/grossSales*100)+' of gross sales':'—'}</div></div>
    <div class="kpi"><div class="label">Net margin</div><div class="value" style="color:${netPayout>=0?'#0F6E56':'#993C1D'}">${netProductSales>0?fmtp(netPayout/netProductSales*100):'—'}</div><div class="sub">Net payout / net product sales</div></div>
    <div class="kpi"><div class="label">Avg order value</div><div class="value" style="color:${avgOrder>=0?'#0F6E56':'#993C1D'}">${fmt(avgOrder)}</div></div>`;
  document.getElementById('trendLeg').innerHTML=`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#B5D4F4"></span>Gross sales</span><span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#1D9E75"></span>Net payout</span>`;
  destroyChart('trend');
  charts.trend=new Chart(document.getElementById('trendC'),{type:'bar',data:{labels:mDisplay,datasets:[
    {label:'Gross sales',data:mLabels.map(m=>Math.round(byMonth[m].sales)),backgroundColor:'#B5D4F4',borderRadius:3,barPercentage:0.6,categoryPercentage:0.8},
    {label:'Net payout',data:mLabels.map(m=>Math.round(byMonth[m].net)),backgroundColor:'#1D9E75',borderRadius:3,barPercentage:0.6,categoryPercentage:0.8}
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},scales:{x:{stacked:false,ticks:{autoSkip:true,maxRotation:45,minRotation:45,maxTicksLimit:24,font:{size:DS.fsAxis}}},y:{stacked:false,ticks:{callback:v=>'$'+v.toLocaleString(),font:{size:DS.fsAxis}}}}}});
  document.getElementById('typeLeg').innerHTML=velLabels.map((l,i)=>`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:${velCols[i]}"></span>${l} (${totalSkuUnits>0?fmtp(velData[i]/totalSkuUnits*100):'—'})</span>`).join('');
  destroyChart('type');
  charts.type=new Chart(document.getElementById('typeC'),{type:'doughnut',data:{labels:velLabels,datasets:[{data:velData,backgroundColor:velCols.slice(0,velLabels.length),borderWidth:2,borderColor:'var(--color-background-primary,#fff)'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>` ${c.label}: ${c.raw.toLocaleString()} units (${totalSkuUnits>0?fmtp(c.raw/totalSkuUnits*100):'—'})`},bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},cutout:'48%'}});
  document.querySelector('#top5T tbody').innerHTML=top5.map(p=>`<tr><td>${p.sku}</td><td style="max-width:150px;overflow:hidden;text-overflow:ellipsis">${(p.desc||'').slice(0,40)}</td><td style="font-weight:500">${fmt(p.net)}</td><td>${p.cnt}</td></tr>`).join('');
}
