const form = document.getElementById('uploadForm');
const submitBtn = document.getElementById('submitBtn');
const statusSection = document.getElementById('statusSection');
const resultsSection = document.getElementById('resultsSection');
const stageText = document.getElementById('stageText');
const fileText = document.getElementById('fileText');
const previewBox = document.getElementById('previewBox');
const progressValue = document.getElementById('progressValue');
const ringFg = document.getElementById('ringFg');
const jobBadge = document.getElementById('jobBadge');
const overviewCards = document.getElementById('overviewCards');
const plannedStrip = document.getElementById('plannedStrip');
const currentBriefCard = document.getElementById('currentBriefCard');
const tierTabs = document.getElementById('tierTabs');
const supplierGrid = document.getElementById('supplierGrid');
const insightPanel = document.getElementById('insightPanel');
const summaryMarkdown = document.getElementById('summaryMarkdown');
const homeSection = document.getElementById('homeSection');
const backBtn = document.getElementById('backBtn');
const sidebarStats = document.getElementById('sidebarStats');
const supplierNav = document.getElementById('supplierNav');
const supplierNavInfo = document.getElementById('supplierNavInfo');
const supplierPrev = document.getElementById('supplierPrev');
const supplierNext = document.getElementById('supplierNext');

const RING_LENGTH = 301.59;
const SUPPLIERS_PER_PAGE = 6;
let pollTimer = null;
let currentResult = null;
let activePlanIndex = 0;
let activeTier = 'A';
let activeSupplierIndex = 0;
let supplierPage = 0;

function setProgress(value) {
  const v = Math.max(0, Math.min(100, Number(value || 0)));
  progressValue.textContent = `${v}%`;
  ringFg.style.strokeDashoffset = String(RING_LENGTH * (1 - v / 100));
}

function escapeHtml(str) {
  return (str || '').replace(/[&<>"']/g, (m) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}

function formatDemand(obj) {
  if (!obj || typeof obj !== 'object') return '—';
  return Object.keys(obj).map((k) => `${k}: ${obj[k]}`).join(' / ');
}

function qualityLabel(q) {
  if (q === 'strong') return '强匹配';
  if (q === 'weak') return '待复核';
  return '建议补渠道';
}

function renderPreview(preview) {
  if (!preview) {
    previewBox.textContent = '上传后会在这里显示识别到的企划款预览。';
    return;
  }
  const lines = [`识别到 ${preview.item_count} 个企划款`, ''];
  (preview.preview_items || []).forEach((item, idx) => {
    lines.push(`${idx + 1}. ${item.theme || '未识别主题'}`);
    lines.push(`   ${item.brief_summary || ''}`);
  });
  previewBox.textContent = lines.join('\n');
}

function renderOverview(result) {
  const overview = result.overview || {};
  const supplierCounts = overview.supplier_counts || {};
  const cards = [
    ['企划款总数', overview.total_items || 0, '本次任务识别出的企划款数量'],
    ['已命中企划款', overview.matched_count || 0, '已找到可用结果的企划款数量'],
    ['A类供应商数', supplierCounts.A || 0, '建议优先推进的供应商数量'],
    ['建议补渠道企划款', overview.fallback_count || 0, '当前渠道匹配不足，建议补其他渠道'],
  ];
  overviewCards.innerHTML = cards.map(([label, value, sub]) => `
    <article class="overview-card">
      <div class="overview-label">${escapeHtml(label)}</div>
      <div class="overview-value">${escapeHtml(String(value))}</div>
      <div class="overview-sub">${escapeHtml(sub)}</div>
    </article>
  `).join('');
}

function renderPlanList(cards) {
  plannedStrip.innerHTML = cards.map((card, index) => `
    <article class="planned-item ${index === activePlanIndex ? 'active' : ''}" data-plan-index="${index}">
      <div class="planned-top">
        <div class="theme">${escapeHtml(card.theme || '未命名企划款')}</div>
      </div>
      <div class="muted small-gap">${escapeHtml(card.price_band_raw || '价格带待定')}</div>
      <div class="reasons">风格：${escapeHtml((card.styles || []).join(' / ') || '—')}</div>
      <div class="reasons">颜色：${escapeHtml((card.colors || []).join(' / ') || '—')}</div>
      <div class="reasons">面料：${escapeHtml((card.fabrics || []).join(' / ') || '—')}</div>
      <div class="reasons">元素：${escapeHtml((card.elements || []).join(' / ') || '—')}</div>
    </article>
  `).join('');

  plannedStrip.querySelectorAll('[data-plan-index]').forEach((el) => {
    el.addEventListener('click', () => {
      activePlanIndex = Number(el.getAttribute('data-plan-index'));
      activeTier = 'A';
      activeSupplierIndex = 0;
      supplierPage = 0;
      renderDeck();
    });
  });
}

function renderBriefCard(card) {
  currentBriefCard.innerHTML = `
    <div class="panel-header"><span class="dot"></span><span>当前企划款概览</span></div>
    <div class="brief-title-row">
      <div>
        <div class="result-title">${escapeHtml(card.theme || '未命名企划款')}</div>
        <div class="result-meta">${escapeHtml(card.brief_summary || '')}</div>
      </div>
      <div class="quality-badge quality-${escapeHtml(card.quality || 'empty')}">${escapeHtml(qualityLabel(card.quality))}</div>
    </div>
    <div class="brief-grid">
      <div class="brief-cell"><div class="label">价格带</div><div class="value">${escapeHtml(card.price_band_raw || '—')}</div></div>
      <div class="brief-cell"><div class="label">面料关键词</div><div class="value">${escapeHtml((card.fabrics || []).join(' / ') || '—')}</div></div>
      <div class="brief-cell"><div class="label">元素关键词</div><div class="value">${escapeHtml((card.elements || []).join(' / ') || '—')}</div></div>
      <div class="brief-cell"><div class="label">需求节奏</div><div class="value">${escapeHtml(formatDemand(card.demand_by_month))}</div></div>
      <div class="brief-cell full"><div class="label">AI判断</div><div class="value emphasis">${escapeHtml(card.ai_summary || '—')}</div></div>
      <div class="brief-cell full"><div class="label">建议动作</div><div class="value">${escapeHtml(card.recommended_action || '—')}</div></div>
    </div>
  `;
}

function getTierLabel(tier) {
  if (tier === 'A') return 'A类｜优先推进';
  if (tier === 'B') return 'B类｜重点复核';
  return 'C类｜补充储备';
}

function renderTierSection(card) {
  const groups = card.supplier_groups || {};
  const counts = { A: card.a_count || 0, B: card.b_count || 0, C: card.c_count || 0 };
  const tiers = ['A', 'B', 'C'];
  if (!groups[activeTier] || !groups[activeTier].length) {
    const fallbackTier = tiers.find((tier) => groups[tier] && groups[tier].length);
    activeTier = fallbackTier || 'A';
    activeSupplierIndex = 0;
  }

  tierTabs.innerHTML = tiers.map((tier) => `
    <button class="tier-tab ${activeTier === tier ? 'active' : ''}" data-tier="${tier}">
      <span>${getTierLabel(tier)}</span>
      <strong>${counts[tier] || 0}</strong>
    </button>
  `).join('');

  tierTabs.querySelectorAll('[data-tier]').forEach((el) => {
    el.addEventListener('click', () => {
      activeTier = el.getAttribute('data-tier');
      activeSupplierIndex = 0;
      supplierPage = 0;
      renderDeck();
    });
  });

  const allSuppliers = groups[activeTier] || [];
  const totalPages = Math.max(1, Math.ceil(allSuppliers.length / SUPPLIERS_PER_PAGE));
  if (supplierPage >= totalPages) supplierPage = totalPages - 1;
  const pageStart = supplierPage * SUPPLIERS_PER_PAGE;
  const pageSuppliers = allSuppliers.slice(pageStart, pageStart + SUPPLIERS_PER_PAGE);

  supplierGrid.innerHTML = pageSuppliers.length ? pageSuppliers.map((supplier, index) => `
    <article class="supplier-card" data-supplier-index="${pageStart + index}">
      <div class="supplier-radar-wrap">${renderRadar(supplier.radar)}</div>
      <div class="supplier-body">
        <div class="supplier-head-row">
          <div class="supplier-name">${escapeHtml(supplier.supplier_name || '未命名商家')}</div>
          <div class="supplier-price-score">
            <span class="chip">${escapeHtml(supplier.price_fit_guess || '—')}</span>
            <div class="score-badge">${escapeHtml(String(supplier.score_total || '—'))}分</div>
          </div>
        </div>
        <div class="supplier-judgement">${escapeHtml(supplier.ai_judgement || '—')}</div>
        <div class="reason-block">
          <div class="reason-title">推荐理由</div>
          <ul class="reasons-list">${(supplier.recommend_reasons || []).slice(0,3).map((x) => `<li>${escapeHtml(x)}</li>`).join('') || '<li>暂无</li>'}</ul>
        </div>
        <div class="risk-block">
          <div class="reason-title">风险提示</div>
          <div class="risk-text">${escapeHtml((supplier.risk_warnings || []).join('；') || '暂无明显风险')}</div>
        </div>
        <div class="supplier-links">
          ${supplier.shop_url ? `<a href="${supplier.shop_url}" target="_blank" rel="noreferrer">查看店铺</a>` : ''}
        </div>
      </div>
    </article>
  `).join('') : '<div class="empty-state">当前分层下暂无供应商推荐。</div>';

  if (allSuppliers.length > SUPPLIERS_PER_PAGE) {
    supplierNav.style.display = 'flex';
    supplierNavInfo.textContent = `${supplierPage + 1} / ${totalPages}（共${allSuppliers.length}个）`;
    supplierPrev.disabled = supplierPage <= 0;
    supplierNext.disabled = supplierPage >= totalPages - 1;
  } else {
    supplierNav.style.display = 'none';
  }
}

function renderDeckSelection() {
  supplierGrid.querySelectorAll('[data-supplier-index]').forEach((el) => {
    el.classList.toggle('active', Number(el.getAttribute('data-supplier-index')) === activeSupplierIndex);
  });
}

function renderRadar(radar) {
  const entries = Object.entries(radar || {});
  if (!entries.length) return '';
  const size = 300;
  const center = size / 2;
  const radius = 85;
  const levels = 4;
  const angleStep = (Math.PI * 2) / entries.length;

  const polygons = [];
  for (let level = 1; level <= levels; level++) {
    const r = radius * (level / levels);
    const pts = entries.map((_, i) => {
      const angle = -Math.PI / 2 + i * angleStep;
      return `${(center + Math.cos(angle) * r).toFixed(1)},${(center + Math.sin(angle) * r).toFixed(1)}`;
    }).join(' ');
    polygons.push(`<polygon points="${pts}" class="radar-grid-level"></polygon>`);
  }

  const axes = entries.map((_, i) => {
    const angle = -Math.PI / 2 + i * angleStep;
    const x = center + Math.cos(angle) * radius;
    const y = center + Math.sin(angle) * radius;
    return `<line x1="${center}" y1="${center}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" class="radar-axis"></line>`;
  }).join('');

  const valuePts = entries.map(([_, value], i) => {
    const angle = -Math.PI / 2 + i * angleStep;
    const r = radius * ((value || 0) / 100);
    return `${(center + Math.cos(angle) * r).toFixed(1)},${(center + Math.sin(angle) * r).toFixed(1)}`;
  }).join(' ');

  const labels = entries.map(([label], i) => {
    const angle = -Math.PI / 2 + i * angleStep;
    const r = radius + 52;
    const x = center + Math.cos(angle) * r;
    const y = center + Math.sin(angle) * r;
    return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" class="radar-label">${escapeHtml(label)}</text>`;
  }).join('');

  return `
    <svg viewBox="0 0 ${size} ${size}" class="radar-svg">
      ${polygons.join('')}
      ${axes}
      <polygon points="${valuePts}" class="radar-value"></polygon>
      ${labels}
    </svg>
  `;
}

function renderInsight(card) {
  const groups = card.supplier_groups || {};
  const suppliers = groups[activeTier] || [];
  const supplier = suppliers[activeSupplierIndex];
  if (!supplier) {
    insightPanel.innerHTML = '<div class="muted">当前分层下暂无供应商，切换其他层级查看。</div>';
    return;
  }

  insightPanel.innerHTML = `
    <div class="insight-head">
      <div class="supplier-name">${escapeHtml(supplier.supplier_name || '未命名商家')}</div>
      <div class="score-badge large">${escapeHtml(String(supplier.score_total || '—'))}分</div>
    </div>
    <div class="muted">${escapeHtml(supplier.profile_summary || supplier.supplier_profile_summary || '')}</div>
    <div class="radar-wrap">${renderRadar(supplier.radar)}</div>
    <div class="insight-summary">
      <div class="reason-title">AI判断</div>
      <div class="insight-judgement">${escapeHtml(supplier.ai_judgement || '—')}</div>
    </div>
    <div class="insight-summary">
      <div class="reason-title">风险提示</div>
      <div class="risk-text">${escapeHtml((supplier.risk_warnings || []).join('；') || '暂无明显风险')}</div>
    </div>
    <div class="supplier-links insight-links">
      ${supplier.source_url ? `<a href="${supplier.source_url}" target="_blank" rel="noreferrer">查看商品</a>` : ''}
      ${supplier.shop_url ? `<a href="${supplier.shop_url}" target="_blank" rel="noreferrer">查看店铺</a>` : ''}
    </div>
  `;
}

function renderDeck() {
  if (!currentResult) return;
  const cards = currentResult.result_cards || [];
  if (!cards.length) return;
  if (activePlanIndex >= cards.length) activePlanIndex = 0;
  const card = cards[activePlanIndex];
  renderPlanList(cards);
  renderBriefCard(card);
  renderTierSection(card);
}

function renderResults(result) {
  currentResult = result;
  activePlanIndex = 0;
  activeTier = 'A';
  activeSupplierIndex = 0;
  supplierPage = 0;
  renderOverview(result);
  const ov = result.overview || {};
  sidebarStats.innerHTML = `<span>企划款总数 <strong>${ov.total_items || 0}</strong></span><span>已寻源款数 <strong>${ov.matched_count || 0}</strong></span>`;
  renderDeck();
  summaryMarkdown.textContent = result.summary_markdown || '暂无 markdown 汇总';
}

async function pollJob(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`);
  const data = await res.json();
  statusSection.classList.remove('hidden');
  stageText.textContent = data.stage || '处理中';
  fileText.textContent = data.original_filename || '';
  jobBadge.textContent = `${data.status || 'unknown'} · ${jobId}`;
  setProgress(data.progress || 0);
  renderPreview(data.preview);

  if (data.status === 'done' && data.result) {
    homeSection.classList.add('hidden');
    resultsSection.classList.remove('hidden');
    renderResults(data.result);
    submitBtn.disabled = false;
    submitBtn.textContent = '再次启动新任务';
    clearTimeout(pollTimer);
    return;
  }

  if (data.status === 'error') {
    previewBox.textContent = data.error || '执行失败';
    submitBtn.disabled = false;
    submitBtn.textContent = '重新上传并启动';
    clearTimeout(pollTimer);
    return;
  }

  pollTimer = setTimeout(() => pollJob(jobId), 2500);
}

backBtn.addEventListener('click', () => {
  resultsSection.classList.add('hidden');
  homeSection.classList.remove('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

supplierPrev.addEventListener('click', () => {
  if (supplierPage > 0) { supplierPage--; renderDeck(); }
});
supplierNext.addEventListener('click', () => {
  supplierPage++;
  renderDeck();
});

document.querySelectorAll('.scroll-container').forEach((el) => {
  el.addEventListener('scroll', () => {
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 8;
    el.classList.toggle('at-bottom', atBottom);
  });
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = '任务提交中...';
  resultsSection.classList.add('hidden');
  setProgress(0);
  renderPreview(null);

  const formData = new FormData(form);
  const res = await fetch('/api/jobs', { method: 'POST', body: formData });
  const data = await res.json();
  if (!res.ok) {
    previewBox.textContent = data.error || '提交失败';
    statusSection.classList.remove('hidden');
    submitBtn.disabled = false;
    submitBtn.textContent = '重新上传并启动';
    return;
  }
  submitBtn.textContent = '任务执行中...';
  pollJob(data.job_id);
});
