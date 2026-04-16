// ── FINANCIALS ───────────────────────────────────────────────────────────────
function renderFinancials(data){
  const orders=data.filter(r=>r.type==='Order');
  const totSales=orders.reduce((s,r)=>s+r.productSales,0);
  const totSellFees=orders.reduce((s,r)=>s+Math.abs(r.sellingFees),0);
  const totFBA=orders.reduce((s,r)=>s+Math.abs(r.fbaFees),0);
  const totRebates=orders.reduce((s,r)=>s+Math.abs(r.promotionalRebates),0);
  const totWithheld=orders.reduce((s,r)=>s+Math.abs(r.marketplaceWithheldTax),0);
  const totOther=orders.reduce((s,r)=>s+Math.abs(r.otherTransactionFees),0);
  const totAdv=data.filter(r=>r.type==='Service Fee'&&(r.description||'').toLowerCase().includes('advertis')).reduce((s,r)=>s+Math.abs(r.total),0);
  const totFBAStorage=data.filter(r=>r.type==='FBA Inventory Fee').reduce((s,r)=>s+Math.abs(r.total),0);
  const refundLoss=data.filter(r=>r.type==='Refund').reduce((s,r)=>s+Math.abs(r.total),0);
  const totNet=data.reduce((s,r)=>s+r.total,0);
  const byM={};
  data.forEach(r=>{
    if(!byM[r.monthKey]) byM[r.monthKey]={sales:0,sellFees:0,fba:0,adv:0,net:0};
    if(r.type==='Order'){byM[r.monthKey].sales+=r.productSales;byM[r.monthKey].sellFees+=Math.abs(r.sellingFees);byM[r.monthKey].fba+=Math.abs(r.fbaFees);}
    if(r.type==='Service Fee'&&(r.description||'').toLowerCase().includes('advertis')) byM[r.monthKey].adv+=Math.abs(r.total);
    byM[r.monthKey].net+=r.total;
  });
  const mL=Object.keys(byM).sort();
  const mD=mL.map(m=>{const[y,mo]=m.split('-');return MONTH_NAMES[+mo-1]+(mL.filter(x=>x.split('-')[1]===mo).length>1?` '${y.slice(2)}`:'');});
  const p=document.getElementById('p2');
  p.innerHTML=`<div class="kpi-grid" id="finKPI"></div>
    <div class="two-col" style="margin-top:4px">
      <div><div class="sec">Fee breakdown (orders only)</div><div class="leg" id="feeLeg"></div><div class="chart-wrap" style="height:460px"><canvas id="feeC"></canvas></div></div>
      <div><div class="sec">Monthly cost structure</div><div class="leg" id="stackLeg"></div><div class="chart-wrap" style="height:460px"><canvas id="stackC"></canvas></div></div>
    </div>
    <div class="sec" style="margin-top:14px">Waterfall summary</div>
    <div class="chart-wrap" style="height:400px"><canvas id="waterC"></canvas></div>`;
  document.getElementById('finKPI').innerHTML=`
    <div class="kpi pos"><div class="label">Product sales</div><div class="value">${fmt(totSales)}</div></div>
    <div class="kpi neg"><div class="label">Selling fees</div><div class="value">${fmtd(-totSellFees)}</div><div class="sub">${totSales>0?fmtp(totSellFees/totSales*100):''} of sales</div></div>
    <div class="kpi neg"><div class="label">FBA fees</div><div class="value">${fmtd(-totFBA)}</div></div>
    <div class="kpi neg"><div class="label">Advertising</div><div class="value">${fmtd(-totAdv)}</div></div>
    <div class="kpi neg"><div class="label">FBA storage</div><div class="value">${fmtd(-totFBAStorage)}</div></div>
    <div class="kpi neg"><div class="label">Promo rebates</div><div class="value">${fmtd(-totRebates)}</div></div>
    <div class="kpi neg"><div class="label">Refund losses</div><div class="value">${fmtd(-refundLoss)}</div></div>
    <div class="kpi pos"><div class="label">Net payout</div><div class="value">${fmt(totNet)}</div><div class="sub">${totSales>0?fmtp(totNet/totSales*100):''} margin</div></div>`;
  const feeLabels=['Selling fees','FBA fees','Promo rebates','Mkt withheld tax','Other txn fees'],feeVals=[totSellFees,totFBA,totRebates,totWithheld,totOther],feeCols=['#378ADD','#EF9F27','#E24B4A','#7F77DD','#73726c'];
  document.getElementById('feeLeg').innerHTML=feeLabels.map((l,i)=>`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:${feeCols[i]}"></span>${l}</span>`).join('');
  destroyChart('fee');
  charts.fee=new Chart(document.getElementById('feeC'),{type:'doughnut',data:{labels:feeLabels,datasets:[{data:feeVals.map(Math.round),backgroundColor:feeCols,borderWidth:2,borderColor:'var(--color-background-primary,#fff)'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>' '+fmt(c.raw)},bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},cutout:'42%'}});
  document.getElementById('stackLeg').innerHTML=`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#B5D4F4"></span>Selling fees</span><span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#EF9F27"></span>FBA fees</span><span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#E24B4A"></span>Advertising</span>`;
  destroyChart('stack');
  charts.stack=new Chart(document.getElementById('stackC'),{type:'bar',data:{labels:mD,datasets:[
    {label:'Selling fees',data:mL.map(m=>Math.round(byM[m].sellFees)),backgroundColor:'#B5D4F4',borderRadius:2,stack:'s'},
    {label:'FBA fees',data:mL.map(m=>Math.round(byM[m].fba)),backgroundColor:'#EF9F27',borderRadius:2,stack:'s'},
    {label:'Advertising',data:mL.map(m=>Math.round(byM[m].adv)),backgroundColor:'#F09595',borderRadius:2,stack:'s'}
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},scales:{x:{ticks:{font:{size:DS.fsAxis}}},y:{stacked:true,ticks:{callback:v=>'$'+v.toLocaleString(),font:{size:DS.fsAxis}}}}}});
  const wLabels=['Product sales','Selling fees','FBA fees','Advertising','FBA storage','Promo rebates','Refunds','Net payout'],wVals=[totSales,-totSellFees,-totFBA,-totAdv,-totFBAStorage,-totRebates,-refundLoss,totNet];
  const wColors=wVals.map((v,i)=>i===0||i===wVals.length-1?'#1D9E75':(v>=0?'#1D9E75':'#E24B4A'));
  destroyChart('water');
  charts.water=new Chart(document.getElementById('waterC'),{type:'bar',data:{labels:wLabels,datasets:[{data:wVals.map(Math.round),backgroundColor:wColors,borderRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},scales:{x:{ticks:{font:{size:DS.fsAxis}}},y:{ticks:{callback:v=>(v<0?'-$':'$')+Math.abs(v).toLocaleString(),font:{size:DS.fsAxis}}}}}});
}
