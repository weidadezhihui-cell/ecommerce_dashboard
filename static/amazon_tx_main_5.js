// ── GEOGRAPHY (Leaflet Choropleth) ───────────────────────────────────────────

// Full state-name → 2-letter abbreviation lookup (matches PublicaMundi GeoJSON names)
const STATE_NAME_TO_ABBR={
  'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA',
  'Colorado':'CO','Connecticut':'CT','Delaware':'DE','Florida':'FL','Georgia':'GA',
  'Hawaii':'HI','Idaho':'ID','Illinois':'IL','Indiana':'IN','Iowa':'IA',
  'Kansas':'KS','Kentucky':'KY','Louisiana':'LA','Maine':'ME','Maryland':'MD',
  'Massachusetts':'MA','Michigan':'MI','Minnesota':'MN','Mississippi':'MS',
  'Missouri':'MO','Montana':'MT','Nebraska':'NE','Nevada':'NV','New Hampshire':'NH',
  'New Jersey':'NJ','New Mexico':'NM','New York':'NY','North Carolina':'NC',
  'North Dakota':'ND','Ohio':'OH','Oklahoma':'OK','Oregon':'OR','Pennsylvania':'PA',
  'Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD','Tennessee':'TN',
  'Texas':'TX','Utah':'UT','Vermont':'VT','Virginia':'VA','Washington':'WA',
  'West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY','District of Columbia':'DC'
};

let _geoMap=null;  // store active Leaflet instance so we can destroy it on re-render

function renderGeo(data){
  const bySt={};
  data.filter(r=>r.type==='Order'&&r.state&&/^[A-Z]{2}$/.test(r.state)).forEach(r=>{
    if(!bySt[r.state]) bySt[r.state]={state:r.state,orders:0,sales:0,net:0,units:0};
    bySt[r.state].orders++;bySt[r.state].sales+=r.productSales;bySt[r.state].net+=r.total;bySt[r.state].units+=r.qty;
  });
  const sorted=Object.values(bySt).sort((a,b)=>b.sales-a.sales).slice(0,25);
  const totStates=Object.keys(bySt).length,topSt=sorted[0]||{state:'—',sales:0};

  const p=document.getElementById('p3');
  p.innerHTML=`
    <div class="kpi-grid" id="geoKPI"></div>
    <div class="sec">Product sales by state — hover for details</div>
    <div id="usaMap"></div>
    <div class="sec" style="margin-top:18px">Top states by product sales</div>
    <div class="leg" id="geoLeg"></div>
    <div class="chart-wrap" style="height:${Math.max(560,sorted.length*52+180)}px"><canvas id="geoC"></canvas></div>
    <div class="sec" style="margin-top:14px">State detail</div>
    <div class="tbl-wrap"><table id="geoT"><thead><tr><th>State</th><th>Orders</th><th>Units</th><th>Product sales</th><th>Net payout</th><th>Margin %</th></tr></thead><tbody></tbody></table></div>`;

  document.getElementById('geoKPI').innerHTML=`
    <div class="kpi"><div class="label">States reached</div><div class="value">${totStates}</div></div>
    <div class="kpi"><div class="label">Top state</div><div class="value">${topSt.state}</div><div class="sub">${fmt(topSt.sales)} in sales</div></div>`;

  // ── Leaflet choropleth ──────────────────────────────────────────────────
  setTimeout(()=>{
    if(typeof L==='undefined'){
      const m=document.getElementById('usaMap');
      if(m) m.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#888;font-size:13px">Leaflet not loaded</div>';
      return;
    }

    // Destroy any previous map instance (prevents "already initialised" error)
    if(_geoMap){try{_geoMap.remove();}catch(e){} _geoMap=null;}

    const map=L.map('usaMap',{
      zoomControl:true,
      scrollWheelZoom:false,
      attributionControl:true
    }).fitBounds([[24,-125],[50,-66]]);
    _geoMap=map;

    // CartoDB Positron — clean light tile, no visual noise
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{
      attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com">CARTO</a>',
      subdomains:'abcd',maxZoom:12
    }).addTo(map);

    // Teal color scale (light → dark) based on product sales
    const netVals=Object.values(bySt).map(s=>Math.max(0,s.sales));
    const maxNet=Math.max(...netVals,1);
    function choroplethColor(net){
      if(net<=0) return '#dff0ed';
      const t=Math.sqrt(net/maxNet);          // sqrt stretches lower values visually
      // #D9F0EC (light teal) → #0A5C4A (deep teal)
      const r=Math.round(217*(1-t)+10*t);
      const g=Math.round(240*(1-t)+92*t);
      const b=Math.round(236*(1-t)+74*t);
      return `rgb(${r},${g},${b})`;
    }

    // Fetch US states GeoJSON (PublicaMundi — well-maintained, no auth needed)
    fetch('https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json')
      .then(r=>{if(!r.ok) throw new Error('fetch failed');return r.json();})
      .then(geojson=>{
        let geoLayer;
        geoLayer=L.geoJson(geojson,{
          style(feature){
            const abbr=STATE_NAME_TO_ABBR[feature.properties.name]||'';
            const st=bySt[abbr];
            return{
              fillColor: st?choroplethColor(Math.max(0,st.sales)):'#f0f0ee',
              weight:0.8, opacity:1, color:'#fff',
              fillOpacity: st?0.85:0.25
            };
          },
          onEachFeature(feature,layer){
            const abbr=STATE_NAME_TO_ABBR[feature.properties.name]||'';
            const st=bySt[abbr];
            const tip=st
              ?`<b>${feature.properties.name} (${abbr})</b><br>`+
                `Product sales: <b style="color:#0A5C4A">${fmt(st.sales)}</b><br>`+
                `Net payout:&nbsp;&nbsp;${fmt(st.net)}<br>`+
                `Orders: ${st.orders} &nbsp;·&nbsp; Units: ${st.units}<br>`+
                `Margin: ${st.sales>0?fmtp(st.net/st.sales*100):'—'}`
              :`<b>${feature.properties.name}</b><br><span style="color:#999">No orders in selected period</span>`;
            layer.bindTooltip(tip,{sticky:true,opacity:0.97,className:'geo-tip'});
            layer.on({
              mouseover(e){
                e.target.setStyle({weight:2,color:'#555',fillOpacity:0.96});
                e.target.bringToFront();
              },
              mouseout(e){geoLayer.resetStyle(e.target);}
            });
          }
        }).addTo(map);
      })
      .catch(()=>{
        const m=document.getElementById('usaMap');
        if(m) m.innerHTML='<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#999;font-size:13px">Map tiles unavailable — check internet connection</div>';
      });

    // Colour-scale legend (bottom-right)
    const legend=L.control({position:'bottomright'});
    legend.onAdd=()=>{
      const d=L.DomUtil.create('div','geo-legend');
      d.innerHTML=
        `<div style="font-size:12px;font-weight:600;margin-bottom:5px;color:#333">Product Sales</div>`+
        `<div style="width:120px;height:10px;border-radius:3px;background:linear-gradient(to right,#D9F0EC,#0A5C4A)"></div>`+
        `<div style="display:flex;justify-content:space-between;font-size:10px;color:#666;margin-top:2px"><span>Low</span><span>High</span></div>`;
      return d;
    };
    legend.addTo(map);

    // Force tile re-render after DOM paint
    setTimeout(()=>map.invalidateSize(),120);
  },80);

  // Bar chart (unchanged)
  document.getElementById('geoLeg').innerHTML=`<span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#B5D4F4"></span>Product sales</span><span style="display:flex;align-items:center;gap:3px"><span class="ld" style="background:#1D9E75"></span>Net payout</span>`;
  destroyChart('geo');
  setTimeout(()=>{
    const geoEl=document.getElementById('geoC');
    if(!geoEl) return;
    charts.geo=new Chart(geoEl,{type:'bar',data:{labels:sorted.map(s=>s.state),datasets:[
      {label:'Sales',data:sorted.map(s=>Math.round(s.sales)),backgroundColor:'#B5D4F4',borderRadius:2},
      {label:'Net',data:sorted.map(s=>Math.round(s.net)),backgroundColor:'#1D9E75',borderRadius:2}
    ]},options:{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{legend:{display:false},tooltip:{bodyFont:{size:DS.fsTooltip},titleFont:{size:DS.fsTooltip,weight:'600'}}},
      scales:{x:{ticks:{callback:v=>'$'+v.toLocaleString(),font:{size:DS.fsAxis}}},y:{ticks:{font:{size:DS.fsAxis},autoSkip:false}}}}});
  },80);
  document.querySelector('#geoT tbody').innerHTML=sorted.map(s=>`<tr><td style="font-weight:500">${s.state}</td><td>${s.orders}</td><td>${s.units}</td><td>${fmt(s.sales)}</td><td style="color:${s.net>=0?'#0F6E56':'#993C1D'}">${fmt(s.net)}</td><td>${s.sales>0?fmtp(s.net/s.sales*100):'—'}</td></tr>`).join('');
}

// ── RAW DATA ─────────────────────────────────────────────────────────────────
function renderRaw(data){
  const tagClass=t=>t==='Order'?'t-order':t==='Refund'?'t-refund':t==='Service Fee'?'t-fee':t==='FBA Inventory Fee'?'t-fba':t==='Adjustment'?'t-adj':'t-other';
  const show=data.slice(0,500);
  document.getElementById('p4').innerHTML=`
    <div style="font-size:11px;color:var(--color-text-secondary);margin-bottom:6px">Showing ${show.length} of ${data.length} rows</div>
    <div class="tbl-wrap"><table id="rawT"><thead><tr><th>Date</th><th>Type</th><th>Order ID</th><th>SKU</th><th>Description</th><th>Qty</th><th>State</th><th>City</th><th>Product sales</th><th>Sales tax</th><th>Ship credits</th><th>Promo rebates</th><th>Mkt withheld tax</th><th>Selling fees</th><th>FBA fees</th><th>Other txn fees</th><th>Other</th><th style="font-weight:600">Total</th></tr></thead>
    <tbody>${show.map(r=>`<tr>
      <td>${r.dt.toISOString().slice(0,10)}</td>
      <td><span class="tag ${tagClass(r.type)}">${r.type}</span></td>
      <td style="font-size:10px">${(r.orderId||'').slice(0,18)}</td>
      <td>${r.sku||'—'}</td>
      <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis">${(r.description||'').slice(0,40)}</td>
      <td>${r.qty||''}</td><td>${r.state||''}</td><td>${r.city||''}</td>
      <td>${r.productSales?fmtd(r.productSales):''}</td>
      <td>${r.productSalesTax?fmtd(r.productSalesTax):''}</td>
      <td>${r.shippingCredits?fmtd(r.shippingCredits):''}</td>
      <td>${r.promotionalRebates?fmtd(r.promotionalRebates):''}</td>
      <td>${r.marketplaceWithheldTax?fmtd(r.marketplaceWithheldTax):''}</td>
      <td style="color:#993C1D">${r.sellingFees?fmtd(r.sellingFees):''}</td>
      <td style="color:#993C1D">${r.fbaFees?fmtd(r.fbaFees):''}</td>
      <td style="color:#993C1D">${r.otherTransactionFees?fmtd(r.otherTransactionFees):''}</td>
      <td>${r.other?fmtd(r.other):''}</td>
      <td style="font-weight:500;color:${r.total>=0?'#0F6E56':'#993C1D'}">${fmtd(r.total)}</td>
    </tr>`).join('')}</tbody></table></div>`;
}

function switchTab(i){
  document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('active',j===i));
  document.querySelectorAll('.panel').forEach((p,j)=>p.classList.toggle('active',j===i));
  // Re-render geo map when tab becomes visible so canvas sizes correctly
  if(i===3){const d=filtered();renderGeo(d);}
}

document.getElementById('fYear').addEventListener('change',e=>{selYear=e.target.value;updateAll();});
document.getElementById('fMonth').addEventListener('change',e=>{selMonth=e.target.value;updateAll();});
document.getElementById('fType').addEventListener('change',e=>{selType=e.target.value;updateAll();});
document.getElementById('fState').addEventListener('change',e=>{selState=e.target.value;updateAll();});
document.getElementById('fSku').addEventListener('change',e=>{selSku=e.target.value;updateAll();});

// ── Multi-tier sticky: measure brand header and write offset CSS variable ──
(function(){
  const bh=document.querySelector('.brand-header');
  if(bh){
    const setH=()=>document.documentElement.style.setProperty('--brand-h',bh.offsetHeight+'px');
    setH();
    window.addEventListener('resize',setH);
  }
})();

// ── Smart Sticky: shadow appears once the sentinel scrolls above the viewport ──
(function(){
  const nav=document.getElementById('stickyNav');
  const sentinel=document.getElementById('stickyNavSentinel');
  if(!nav||!sentinel||typeof IntersectionObserver==='undefined') return;
  new IntersectionObserver(
    ([entry])=>{ nav.classList.toggle('is-stuck',!entry.isIntersecting); },
    {threshold:0,rootMargin:'0px'}
  ).observe(sentinel);
})();

const SAMPLE = document.getElementById('amazon-sample-tsv').textContent.trim();
