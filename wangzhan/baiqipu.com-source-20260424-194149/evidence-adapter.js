/* Scoped progressive enhancement: compiled original application remains untouched. */
(() => {
  const nativeFetch = window.fetch.bind(window);
  let host, root, last = null, generation = 0;
  const eligible = () => /^\/(chat|atlas|horse|horses|horse-rag)(\/|$)/.test(location.pathname);
  function el(tag, text) { const x = document.createElement(tag); if (text) x.textContent = text; return x; }
  function mount() {
    if (!eligible()) { if (host) host.remove(); host = null; return; }
    if (host?.isConnected) return;
    const container = document.querySelector('main');
    if (!container) return;
    host = el('section'); host.id = 'steedatlas-evidence';
    root = host.attachShadow({mode: 'open'});
    const style = el('style'); style.textContent = ':host{display:block;margin:24px auto;max-width:1000px;padding:0 16px;color:#e7d7b6;font:inherit;box-sizing:border-box}details{background:#15120e;border:1px solid #6d5428;border-radius:12px;padding:16px}summary{color:#e7bb63;cursor:pointer;font-size:16px}p{line-height:1.8;white-space:pre-wrap;overflow-wrap:anywhere}input,button{font:inherit;color:#e7d7b6;background:#211b13;border:1px solid #8b6b32;border-radius:6px;padding:9px;margin:4px 0}input{width:100%;box-sizing:border-box}button{cursor:pointer;margin-right:8px}a{color:#e7bb63;display:block;padding:8px 0;overflow-wrap:anywhere}small{color:#b9ab93}.row{border-top:1px solid #42351e;padding:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}';
    root.append(style);
    const details = el('details');
    details.append(el('summary', '知识与原文证据'));
    details.append(el('p', '图鉴故事属于编辑整理。机器核对的原文可直接查阅，标明版本、出处与许可；机器核对不等于专家审核或史实证明。'));
    const input = el('input'); input.placeholder = '查询名马或比较来源，如：赤兔和的卢的出处'; input.setAttribute('aria-label','证据查询');
    const search = el('button','查阅证据'); search.type='button';
    const research = el('button','研究与来源比较'); research.type='button';
    const acquire = el('button','自动查找缺失来源'); acquire.type='button';
    const content = el('div'); content.id='evidence-content'; content.setAttribute('aria-live','polite');
    async function submit(agent, discover=false) {
      const q = input.value.trim(); if (!q) return;
      search.disabled = research.disabled = acquire.disabled = true; content.replaceChildren(el('p','正在检索…'));
      try {
        let token = '';
        if (agent) { const auth=JSON.parse(localStorage.getItem('auth-storage')||'{}'); token=auth.state?.accessToken||auth.accessToken||auth.state?.access_token||''; }
        const response = await nativeFetch(agent?'/api/v2/research/runs':'/api/v2/answers', {
          method:'POST',headers:{'Content-Type':'application/json',...(token?{'Authorization':'Bearer '+token}:{})},
          body:JSON.stringify(agent?{query:q,acquire_sources:discover,max_calls:10}:{messages:[{role:'user',content:q}]})});
        if (!response.ok) throw new Error(response.status===401?'请先在原站登录后发起研究。':'暂时无法读取资料，请稍后重试。');
        const data=await response.json();
        if (agent) { render({mode:'RULE_BASED · 来源研究',message:'研究记录已保存；引文核验与历史结论审核分别标注。',evidence:{results:data.data.evidence},citations:data.data.evidence.map(h=>h.citation)});
          const trace=el('pre',data.data.trace.map(t=>`${t.tool} → ${t.status} (${t.elapsed_ms}ms)`).join('\n')); content.append(trace);
          content.append(el('small',`停止原因：${data.data.stop_reason}；模型调用 0；费用 0`));
        } else render(data);
      } catch(e) { content.replaceChildren(el('p',e.message)); }
      finally { search.disabled=research.disabled=acquire.disabled=false; }
    }
    search.onclick=()=>submit(false); research.onclick=()=>submit(true);
    acquire.onclick=()=>submit(true,true);
    input.onkeydown=e=>{if(e.key==='Enter')submit(false);};
    details.append(input,search,research,acquire,content); root.append(details);
    container.append(host);
    if(last)render(last);
  }
  function render(data) {
    last=data; if(!host?.isConnected)return;
    const content=root.getElementById('evidence-content');
    root.querySelector('details').open=true;
    content.replaceChildren(el('p',`${data.mode||'BROWSE'} · ${data.summary||data.message||'来源资料（审核状态见下）'}`));
    const citations=data.citations||[];
    for(const c of citations) {
      const row=el('div'); row.className='row';
      row.append(el('small',`${c.genre} · ${c.verification||c.review_state} · ${c.human_review_state||c.review_state} · ${c.relation}`));
      const a=el('a',`${c.source_title} / ${c.locator} · 段落版本 ${c.passage_revision}`);
      if(/^\/api\/v2\/(?:passage-)?evidence\/[a-zA-Z0-9_-]+@\d+$/.test(c.href)){a.href=c.href;a.target='_blank';a.rel='noopener';}
      row.append(a);
      const full=el('details'); full.append(el('summary','展开完整原文（保留原始段落与定位）'),el('p',c.quote));
      row.append(full,el('small',`${c.attribution||''} · ${c.license||''}`));
      if(c.source_observation?.checked_at)row.append(el('small',` · 来源观察：${c.source_observation.checked_at}`));
      content.append(row);
    }
    for(const c of data.evidence?.candidates||[]) {
      if(c.usable_as_fact||c.usable_as_attributed_quote)continue;
      const a=el('a',`待核候选：${c.source_title} · ${c.genre} · ${c.review_state}（不可作已证实引文）`);
      if(/^\/api\/v2\/(?:passage-)?evidence\/[a-zA-Z0-9_-]+@\d+$/.test(c.href)){a.href=c.href;a.target='_blank';a.rel='noopener';}
      content.append(a);
    }
    for(const snapshot of data.evidence?.snapshots||[]) {
      const a=el('a',`保存快照 · 非实时：${snapshot.title} · 最后观察 ${snapshot.observation?.checked_at||'未知'}`);
      if(/^\/api\/v2\/snapshot-evidence\/[a-zA-Z0-9_-]+$/.test(snapshot.href)){a.href=snapshot.href;a.target='_blank';a.rel='noopener';}
      content.append(a);
    }
    if(citations.length) {
      const check=el('button','重新核验引用'); check.onclick=async()=>{
        try { const r=await nativeFetch('/api/v2/evidence/validate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({citations})});
          const v=await r.json(); check.textContent=v.stale?'引用已过期，请重新查询':'原文、版本与使用许可核验通过';
        }catch{check.textContent='核验失败，请重试';}
      };content.append(check);
    }
  }
  window.fetch=async(...args)=>{
    const response=await nativeFetch(...args);
    const path=new URL(typeof args[0]==='string'?args[0]:args[0].url,location.href).pathname;
    if(response.ok&&path==='/api/v1/chat') {
      const ticket=++generation;
      response.clone().text().then(text=>{
        if(ticket!==generation)return;
        if(response.headers.get('content-type')?.includes('text/event-stream')){
          for(const line of text.split('\n'))if(line.startsWith('data: {')){const data=JSON.parse(line.slice(6));if(data.type==='meta')render(data);}
        }else render(JSON.parse(text));
      }).catch(()=>{});
    }
    if(response.ok&&/^\/api\/v1\/horses\/(?:rag-library\/)?[^/]+$/.test(path)&&!path.endsWith('/stats')) {
      response.clone().json().then(async row=>{
        if(!row.name)return;
        const r=await nativeFetch('/api/v2/answers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:row.name+'的出处'}]})});
        if(r.ok)render(await r.json());
      }).catch(()=>{});
    }
    return response;
  };
  new MutationObserver(mount).observe(document.documentElement,{childList:true,subtree:true});
  window.addEventListener('popstate',mount); window.addEventListener('DOMContentLoaded',mount);
})();
