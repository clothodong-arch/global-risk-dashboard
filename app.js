const fmt=(v,d=2)=>v==null||Number.isNaN(v)?'—':Number(v).toLocaleString('zh-CN',{maximumFractionDigits:d,minimumFractionDigits:d});
const signed=(v,d=2)=>v==null||Number.isNaN(v)?'—':`${v>0?'+':''}${fmt(v,d)}`;
const changeClass=(v,riskUp=true)=>v==null||v===0||Number.isNaN(v)?'neutral':((v>0)===riskUp?'up':'down');
async function boot(){
  const res=await fetch(`data/dashboard.json?t=${Date.now()}`); const d=await res.json();
  document.querySelector('#updated-at').textContent=`更新：${new Date(d.generated_at).toLocaleString('zh-CN',{timeZone:'Asia/Hong_Kong'})}`;
  document.querySelector('#risk-score').textContent=d.risk.score; document.querySelector('#score-label').textContent=d.risk.label;
  document.querySelector('#risk-regime').textContent=d.risk.regime; document.querySelector('#meter-fill').style.width=`${d.risk.score}%`;
  const dot=document.querySelector('#status-dot'); dot.style.background=d.risk.score>=70?'var(--bad)':d.risk.score>=45?'var(--warn)':'var(--good)';
  document.querySelector('#headline').textContent=d.analysis.headline; document.querySelector('#summary').textContent=d.analysis.summary;
  document.querySelector('#signals').innerHTML=d.analysis.signals.map(x=>`<li>${x}</li>`).join('');
  document.querySelector('#cards').innerHTML=d.cards.map(c=>`<article class="card"><div class="card-head"><span>${c.name}</span><span>${c.category}</span></div><div class="card-value">${fmt(c.value,c.decimals)}${c.unit||''}</div><div class="card-foot"><span class="${changeClass(c.change_1d,c.risk_up)}">1D ${signed(c.change_1d)}${c.change_unit||'%'}</span><span class="${changeClass(c.change_20d,c.risk_up)}">20D ${signed(c.change_20d)}${c.change_unit||'%'}</span></div><div class="card-source">${c.source||''}</div></article>`).join('');
  document.querySelector('#transmission').innerHTML=d.analysis.transmission.map((x,i)=>`${i?'<span class="arrow">→</span>':''}<span class="node">${x}</span>`).join('');
  const q=d.data_quality||{successful:d.cards.length,expected:d.cards.length,missing:[]};
  document.querySelector('#coverage').textContent=`${q.successful}/${q.expected}`;
  document.querySelector('#missing').innerHTML=(q.missing&&q.missing.length?q.missing:[{name:'无',source:'',reason:'全部指标成功'}]).map(x=>`<li><strong>${x.name}</strong><span>${x.source}${x.reason?` · ${x.reason}`:''}</span></li>`).join('');
  renderCharts(d);
}
function renderCharts(d){
 const common={responsive:true,interaction:{mode:'index',intersect:false},plugins:{legend:{labels:{color:'#a9bac7',usePointStyle:true}}},scales:{x:{ticks:{color:'#7f93a5',maxTicksLimit:8},grid:{color:'#172838'}},y:{ticks:{color:'#7f93a5'},grid:{color:'#172838'}}}};
 new Chart(document.querySelector('#stress-chart'),{type:'line',data:{labels:d.history.dates,datasets:d.history.stress.map(s=>({label:s.name,data:s.values,borderWidth:2,pointRadius:0,tension:.25}))},options:common});
 new Chart(document.querySelector('#equity-chart'),{type:'line',data:{labels:d.history.dates,datasets:d.history.equities.map(s=>({label:s.name,data:s.values,borderWidth:2,pointRadius:0,tension:.25}))},options:common});
}
boot().catch(e=>{document.querySelector('#headline').textContent='数据载入失败，请检查 data/dashboard.json 或自动更新任务。';console.error(e)});
