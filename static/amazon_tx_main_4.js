// ── FINANCIALS ───────────────────────────────────────────────────────────────
function renderFinancials(data){
  const orders=data.filter(r=>r.type==='Order');
  const refunds=data.filter(r=>r.type==='Refund');
  const grossSales=orders.reduce((s,r)=>s+(Number(r.productSales)||0),0);
  const refundLosses=refunds.reduce((s,r)=>s+(Number(r.productSales)||0),0);
  const wfRefund=refundLosses<=0?refundLosses:-Math.abs(refundLosses);
  const sellFeesSum=data.reduce((s,r)=>s+(Number(r.sellingFees)||0),0);
  const fbaFeesSum=data.reduce((s,r)=>s+(Number(r.fbaFees)||0),0);
  const totSellFees=Math.abs(sellFeesSum);
  const totFBA=Math.abs(fbaFeesSum);
  const totAdv=data.filter(r=>r.type==='Service Fee'&&(r.description||'').toLowerCase().includes('advertis')).reduce((s,r)=>s+Math.abs(r.total),0);
  const totFBAStorage=data.filter(r=>r.type==='FBA Inventory Fee').reduce((s,r)=>s+Math.abs(r.total),0);
  const totDeals=data.filter(r=>{
    const d=(r.description||'').toLowerCase();
    const t=(r.type||'').trim();
    return (t==='Service Fee'&&d.includes('coupon'))||(t===''&&d.includes('deal'));
  }).reduce((s,r)=>s+(Number(r.total)||0),0);
  const totFBAInbound=data.filter(r=>(r.description||'').toLowerCase().includes('fba inbound placement')).reduce((s,r)=>s+(Number(r.total)||0),0);
  // Cash-flow net: Transfer totals only, sign flipped for display (narrow SKU/State filters may yield $0).
  const transferSum=data.filter(r=>r.type==='Transfer').reduce((s,r)=>s+(Number(r.total)||0),0);
  const totNet=-transferSum;
  // Others: residual that makes (bridge + others) == net payout exactly.
  const bridgeSum=grossSales+wfRefund-totSellFees-totFBA-totAdv-totFBAStorage+totDeals+totFBAInbound;
  const totOthers=totNet-bridgeSum;
  const byM={};
  data.forEach(r=>{
    const m=r.monthKey;
    if(!byM[m]) byM[m]={sales:0,sellFees:0,fba:0,adv:0,storage:0,deals:0,inbound:0};
    byM[m].sellFees+=Number(r.sellingFees)||0;
    byM[m].fba+=Number(r.fbaFees)||0;
    if(r.type==='Order') byM[m].sales+=Number(r.productSales)||0;
    if(r.type==='Service Fee'&&(r.description||'').toLowerCase().includes('advertis')) byM[m].adv+=Math.abs(r.total);
    if(r.type==='FBA Inventory Fee') byM[m].storage+=Math.abs(Number(r.total)||0);
    const d=(r.description||'').toLowerCase(),t=(r.type||'').trim();
    if((t==='Service Fee'&&d.includes('coupon'))||(t===''&&d.includes('deal'))) byM[m].deals+=Number(r.total)||0;
    if(d.includes('fba inbound placement')) byM[m].inbound+=Number(r.total)||0;
  });
  const mL=Object.keys(byM).sort();
  const mD=mL.map(m=>{const[y,mo]=m.split('-');return MONTH_NAMES[+mo-1]+(mL.filter(x=>x.split('-')[1]===mo).length>1?` '${y.slice(2)}`:'');});
  const p=document.getElementById('p2');
  p.innerHTML=`<div class="kpi-grid" id="finKPI"></div>
    <div class="two-col" style="margin-top:4px">
      <div><div class="sec">Fee breakdown</div><div class="leg" id="feeLeg"></div><div class="chart-wrap" style="height:460px"><canvas id="feeC"></canvas></div></div>
      <div><div class="sec">Monthly cost structure</div><div class="leg" id="stackLeg"></div><div class="chart-wrap" style="height:460px"><canvas id="stackC"></canvas></div></div>
    </div>
    <div class="sec" style="margin-top:14px">Waterfall summary</div>
    <div class="chart-wrap" style="height:400px"><canvas id="waterC"></canvas></div>`;
  const pctGross=v=>grossSales>0?fmtp(Math.abs(v)/grossSales*100)+' of gross sales':'—';
  document.getElementById('finKPI').innerHTML=`
    <div class="kpi pos"><div class="label">Gross sales</div><div class="value">${fmt(grossSales)}</div><div class="sub">100% of gross sales</div></div>
    <div class="kpi neg"><div class="label">Refund losses</div><div class="value">${fmtd(wfRefund)}</div><div class="sub">${pctGross(wfRefund)}</div></div>
    <div class="kpi neg"><div class="label">Selling fees</div><div class="value">${fmtd(-totSellFees)}</div><div class="sub">${pctGross(totSellFees)}</div></div>
    <div class="kpi neg"><div class="label">FBA fees</div><div class="value">${fmtd(-totFBA)}</div><div class="sub">${pctGross(totFBA)}</div></div>
    <div class="kpi neg"><div class="label">Advertising</div><div class="value">${fmtd(-totAdv)}</div><div class="sub">${pctGross(totAdv)}</div></div>
    <div class="kpi neg"><div class="label">FBA storage</div><div class="value">${fmtd(-totFBAStorage)}</div><div class="sub">${pctGross(totFBAStorage)}</div></div>
    <div class="kpi ${totDeals<0?'neg':totDeals>0?'pos':''}"><div class="label">Deals / coupon fee</div><div class="value">${fmtd(totDeals)}</div><div class="sub">${pctGross(totDeals)}</div></div>
    <div class="kpi ${totFBAInbound<0?'neg':totFBAInbound>0?'pos':''}"><div class="label">FBA inbound placement</div><div class="value">${fmtd(totFBAInbound)}</div><div class="sub">${pctGross(totFBAInbound)}</div></div>
    <div class="kpi"><div class="label">Others</div><div class="value" style="color:${totOthers>=0?'#1D9E75':'#E24B4A'}">${fmtd(totOthers)}</div><div class="sub">${pctGross(totOthers)}</div></div>
    <div class="kpi ${totNet>0?'pos':totNet<0?'neg':''}"><div class="label">Net payout</div><div class="value">${fmt(totNet)}</div><div class="sub">${pctGross(totNet)}</div></div>`;
  const feeLabels=['Selling fees','FBA fees','Advertising','FBA storage','Deals/coupon','FBA inbound'];
  const feeVals=[totSellFees,totFBA,totAdv,totFBAStorage,Math.abs(totDeals),Math.abs(totFBAInbound)];
  const feeCols=['#378ADD','#EF9F27','#F09595','#7F77DD','#E24B4A','#1D9E75'];
  document.getElementById('feeLeg').innerHTML=feeLabels.map((l,i)=>`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:${feeCols[i]}"></span>${l}</span>`).join('');
  destroyChart('fee');
  charts.fee=new Chart(document.getElementById('feeC'),{type:'doughnut',data:{labels:feeLabels,datasets:[{data:feeVals.map(Math.round),backgroundColor:feeCols,borderWidth:2,borderColor:'var(--color-background-primary,#fff)'}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>' '+fmt(c.raw)},bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},cutout:'42%'}});
  document.getElementById('stackLeg').innerHTML=feeLabels.map((l,i)=>`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:${feeCols[i]}"></span>${l}</span>`).join('');
  destroyChart('stack');
  charts.stack=new Chart(document.getElementById('stackC'),{type:'bar',data:{labels:mD,datasets:[
    {label:'Selling fees',data:mL.map(m=>Math.round(Math.abs(byM[m].sellFees))),backgroundColor:'#378ADD',borderRadius:2,stack:'s'},
    {label:'FBA fees',data:mL.map(m=>Math.round(Math.abs(byM[m].fba))),backgroundColor:'#EF9F27',borderRadius:2,stack:'s'},
    {label:'Advertising',data:mL.map(m=>Math.round(byM[m].adv)),backgroundColor:'#F09595',borderRadius:2,stack:'s'},
    {label:'FBA storage',data:mL.map(m=>Math.round(byM[m].storage)),backgroundColor:'#7F77DD',borderRadius:2,stack:'s'},
    {label:'Deals/coupon',data:mL.map(m=>Math.round(Math.abs(byM[m].deals))),backgroundColor:'#E24B4A',borderRadius:2,stack:'s'},
    {label:'FBA inbound',data:mL.map(m=>Math.round(Math.abs(byM[m].inbound))),backgroundColor:'#1D9E75',borderRadius:2,stack:'s'}
  ]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},scales:{x:{ticks:{font:{size:DS.fsAxis}}},y:{stacked:true,ticks:{callback:v=>'$'+v.toLocaleString(),font:{size:DS.fsAxis}}}}}});
  const wLabels=['Gross sales','Refund losses','Selling fees','FBA fees','Advertising','FBA storage','Deals/coupon','FBA inbound','Others','Net payout'];
  const wVals=[grossSales,wfRefund,-totSellFees,-totFBA,-totAdv,-totFBAStorage,totDeals,totFBAInbound,totOthers,totNet];
  const wColors=wVals.map((v,i)=>(i===0||i===wVals.length-1?v>=0?'#1D9E75':'#E24B4A':(v>=0?'#1D9E75':'#E24B4A')));
  destroyChart('water');
  charts.water=new Chart(document.getElementById('waterC'),{type:'bar',data:{labels:wLabels,datasets:[{data:wVals.map(Math.round),backgroundColor:wColors,borderRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},scales:{x:{ticks:{font:{size:DS.fsAxis}}},y:{ticks:{callback:v=>(v<0?'-$':'$')+Math.abs(v).toLocaleString(),font:{size:DS.fsAxis}}}}}});
}
