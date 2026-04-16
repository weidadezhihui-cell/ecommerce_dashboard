// ── PRODUCTS ─────────────────────────────────────────────────────────────────
function renderProducts(data){
  const prod={};
  data.filter(r=>r.type==='Order').forEach(r=>{
    const k=r.sku||'(no SKU)';
    if(!prod[k])prod[k]={sku:k,desc:r.description,sales:0,net:0,qty:0,sellingFees:0,fbaFees:0,rebates:0,cnt:0};
    prod[k].sales+=r.productSales;prod[k].net+=r.total;prod[k].qty+=r.qty;
    prod[k].sellingFees+=Math.abs(r.sellingFees);prod[k].fbaFees+=Math.abs(r.fbaFees);prod[k].rebates+=Math.abs(r.promotionalRebates);prod[k].cnt++;
  });
  const sorted=Object.values(prod).sort((a,b)=>b.sales-a.sales).slice(0,12);
  const p=document.getElementById('p1');
  p.innerHTML=`<div class="sec">Top products — product sales vs net payout</div>
    <div class="leg" id="prodLeg"></div>
    <div class="chart-wrap" style="height:${Math.max(560,sorted.length*52+180)}px"><canvas id="prodC"></canvas></div>
    <div class="sec" style="margin-top:14px">Product detail table</div>
    <div class="tbl-wrap"><table id="prodT"><thead><tr><th>SKU</th><th>Description</th><th>Units</th><th>Orders</th><th>Product sales</th><th>Selling fees</th><th>FBA fees</th><th>Promo rebates</th><th>Net payout</th><th>Margin %</th></tr></thead><tbody></tbody></table></div>`;
  document.getElementById('prodLeg').innerHTML=`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#B5D4F4"></span>Product sales</span><span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#1D9E75"></span>Net payout</span>`;
  destroyChart('prod');
  charts.prod=new Chart(document.getElementById('prodC'),{type:'bar',data:{labels:sorted.map(p=>p.sku),datasets:[
    {label:'Sales',data:sorted.map(p=>Math.round(p.sales)),backgroundColor:'#B5D4F4',borderRadius:2},
    {label:'Net',data:sorted.map(p=>Math.round(p.net)),backgroundColor:'#1D9E75',borderRadius:2}
  ]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false},tooltip:{bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},layout:{padding:{right:12}},scales:{x:{ticks:{callback:v=>'$'+v.toLocaleString(),font:{size:DS.fsAxis}}},y:{ticks:{font:{size:DS.fsAxis},autoSkip:false}}}}});
  document.querySelector('#prodT tbody').innerHTML=sorted.map(p=>`<tr><td>${p.sku}</td><td style="max-width:180px;overflow:hidden;text-overflow:ellipsis">${(p.desc||'').slice(0,45)}</td><td>${p.qty}</td><td>${p.cnt}</td><td>${fmt(p.sales)}</td><td style="color:#993C1D">${fmtd(-p.sellingFees)}</td><td style="color:#993C1D">${fmtd(-p.fbaFees)}</td><td style="color:#993C1D">${fmtd(-p.rebates)}</td><td style="font-weight:500;color:${p.net>=0?'#0F6E56':'#993C1D'}">${fmt(p.net)}</td><td>${p.sales>0?fmtp(p.net/p.sales*100):'—'}</td></tr>`).join('');
}
