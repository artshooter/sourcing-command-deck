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
const resultCards = document.getElementById('resultCards');
const summaryMarkdown = document.getElementById('summaryMarkdown');

const RING_LENGTH = 301.59;
let pollTimer = null;

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
  if (q === 'weak') return '可用但需复核';
  return '空结果 / 转其他渠道';
}

function renderPreview(preview) {
  if (!preview) {
    previewBox.textContent = '上传后会在这里显示解析到的 item 预览。';
    return;
  }
  const lines = [`识别到 ${preview.item_count} 个企划 item`, ''];
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
    ['总 item 数', overview.total_items || 0, '企划中解析出的总主题数'],
    ['本轮已跑', overview.selected_count || 0, '本次优先执行的 item'],
    ['强匹配', overview.strong_count || 0, '推荐优先联系'],
    ['待复核', overview.weak_count || 0, '有命中但需要人工判断'],
    ['空结果', overview.empty_count || 0, '两轮仍空时建议换渠道'],
    ['供应商池', (supplierCounts.A || 0) + (supplierCounts.B || 0) + (supplierCounts.C || 0), `A:${supplierCounts.A || 0} / B:${supplierCounts.B || 0} / C:${supplierCounts.C || 0}`],
  ];
  overviewCards.innerHTML = cards.map(([label, value, sub]) => `
    <article class="overview-card">
      <div class="overview-label">${escapeHtml(label)}</div>
      <div class="overview-value">${escapeHtml(String(value))}</div>
      <div class="overview-sub">${escapeHtml(sub)}</div>
    </article>
  `).join('');
}

function renderPlannedItems(items) {
  plannedStrip.innerHTML = (items || []).map((item) => `
    <article class="planned-item">
      <div class="score">Priority ${escapeHtml(String(item.priority_score || 0))}</div>
      <div class="theme">${escapeHtml(item.theme || '未命名主题')}</div>
      <div class="muted">#${escapeHtml(String(item.item_index || ''))} · ${escapeHtml(item.market || '')}</div>
      <div class="reasons">${escapeHtml((item.priority_reasons || []).join(' / '))}</div>
    </article>
  `).join('');
}

function renderSupplierCard(card) {
  const img = card.product_image ? `<img class="supplier-image" src="${card.product_image}" alt="">` : '<div class="supplier-image"></div>';
  const reasons = (card.recommend_reasons || []).length
    ? `<ul class="reasons-list">${card.recommend_reasons.map((x) => `<li>${escapeHtml(x)}</li>`).join('')}</ul>`
    : '';
  return `
    <article class="supplier-card">
      ${img}
      <div class="supplier-body">
        <div class="overview-label level-${escapeHtml(card.recommendation_level || '')}">Level ${escapeHtml(card.recommendation_level || '-')}</div>
        <div class="supplier-name">${escapeHtml(card.supplier_name || '未命名商家')}</div>
        <div class="supplier-title">${escapeHtml(card.product_title || '')}</div>
        <div class="muted">${escapeHtml(card.supplier_profile_summary || '')}</div>
        <div class="chips">
          <span class="chip">分数 ${escapeHtml(String(card.score_total || '—'))}</span>
          <span class="chip">价格 ${escapeHtml(card.price_fit_guess || '—')}</span>
        </div>
        ${reasons}
        <div class="supplier-links">
          ${card.source_url ? `<a href="${card.source_url}" target="_blank" rel="noreferrer">商品链接</a>` : ''}
          ${card.shop_url ? `<a href="${card.shop_url}" target="_blank" rel="noreferrer">店铺链接</a>` : ''}
        </div>
      </div>
    </article>
  `;
}

function renderResults(result) {
  renderOverview(result);
  renderPlannedItems(result.planned_items || []);
  resultCards.innerHTML = (result.result_cards || []).map((card) => `
    <article class="result-card">
      <div class="result-head">
        <div>
          <div class="result-title">#${escapeHtml(String(card.item_index || ''))} · ${escapeHtml(card.theme || '未命名主题')}</div>
          <div class="result-meta">${escapeHtml(card.brief_summary || '')}</div>
          <div class="chips">
            <span class="chip">价格带 ${escapeHtml(card.price_band_raw || '—')}</span>
            <span class="chip">面料 ${escapeHtml((card.fabrics || []).join(' / ') || '—')}</span>
            <span class="chip">元素 ${escapeHtml((card.elements || []).join(' / ') || '—')}</span>
            <span class="chip">需求 ${escapeHtml(formatDemand(card.demand_by_month))}</span>
          </div>
        </div>
        <div class="quality-badge quality-${escapeHtml(card.quality || 'empty')}">${escapeHtml(qualityLabel(card.quality))}</div>
      </div>
      <div class="stat-strip">
        <div class="small-stat"><div class="label">Top Suppliers</div><div class="value">${escapeHtml(String(card.top_count || 0))}</div></div>
        <div class="small-stat"><div class="label">A 类</div><div class="value">${escapeHtml(String(card.a_count || 0))}</div></div>
        <div class="small-stat"><div class="label">B 类</div><div class="value">${escapeHtml(String(card.b_count || 0))}</div></div>
        <div class="small-stat"><div class="label">C 类</div><div class="value">${escapeHtml(String(card.c_count || 0))}</div></div>
        <div class="small-stat"><div class="label">建议动作</div><div class="value" style="font-size:18px">${escapeHtml(card.recommended_action || '—')}</div></div>
      </div>
      ${(card.supplier_cards || []).length ? `<div class="supplier-grid">${card.supplier_cards.map(renderSupplierCard).join('')}</div>` : '<div class="muted">当前没有可展示的商家卡片；如果这是二轮后仍为空的 item，建议直接补其他渠道。</div>'}
    </article>
  `).join('');
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
