const form = document.querySelector('#job-form');
const urlInput = document.querySelector('#article-url');
const authorized = document.querySelector('#authorized');
const formError = document.querySelector('#form-error');
const stepsEl = document.querySelector('#steps');
const stateEl = document.querySelector('#job-state');
const progressEl = document.querySelector('#progress-bar');
const jobIdEl = document.querySelector('#job-id');
const elapsedEl = document.querySelector('#elapsed');
const currentActionEl = document.querySelector('#current-action');
const currentDetailEl = document.querySelector('#current-detail');
const stepElapsedEl = document.querySelector('#step-elapsed');
const activityEventsEl = document.querySelector('#activity-events');
const statContentEl = document.querySelector('#stat-content');
const statImagesEl = document.querySelector('#stat-images');
const statProcessedEl = document.querySelector('#stat-processed');
const statElapsedEl = document.querySelector('#stat-elapsed');
const resultPanel = document.querySelector('#result-panel');
const resultTitle = document.querySelector('#result-title');
const downloadLink = document.querySelector('#download-link');
const warnings = document.querySelector('#result-warnings');
const originalPreview = document.querySelector('#original-preview');
const rewrittenPreview = document.querySelector('#rewritten-preview');
const comparisonEl = document.querySelector('#comparison');
const previewCount = document.querySelector('#preview-count');
const originalCount = document.querySelector('#original-count');
const rewrittenCount = document.querySelector('#rewritten-count');
const submitButton = form.querySelector('button[type="submit"]');

let pollTimer = null;
let startedAt = 0;

function selectedStrategy() {
  return document.querySelector('input[name="image_strategy"]:checked')?.value || 'skip';
}

function normalizeArticleUrl(rawValue) {
  const raw = rawValue.trim();
  if (!raw) throw new Error('请输入公众号文章链接。');
  const value = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error('链接格式不正确，请粘贴完整的公众号文章链接。');
  }
  if (!parsed.hostname.endsWith('weixin.qq.com')) {
    throw new Error('目前只支持 mp.weixin.qq.com 公众号文章链接。');
  }
  if (parsed.hostname !== 'mp.weixin.qq.com' || !/^\/s\//i.test(parsed.pathname)) {
    throw new Error('请输入具体的公众号文章链接，不要输入 mp.weixin.qq.com 首页地址。');
  }
  return parsed.toString();
}

function setStrategyState() {
  document.querySelectorAll('.segment').forEach((segment) => {
    segment.classList.toggle('active', segment.querySelector('input')?.checked);
  });
}
document.querySelectorAll('input[name="image_strategy"]').forEach((input) => input.addEventListener('change', setStrategyState));

function escapeHtml(value = '') {
  return value.replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
}

function renderInlineMarkdown(value, jobId, imageRoot = 'output/images') {
  let html = escapeHtml(value);
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_match, alt, path) => {
    const normalized = String(path).replace(/^\.\//, '');
    const filePath = normalized.startsWith('images/') ? `${imageRoot}/${normalized.slice('images/'.length)}` : normalized;
    return `<img loading="lazy" alt="${alt}" src="/api/jobs/${encodeURIComponent(jobId)}/files/${filePath.split('/').map(encodeURIComponent).join('/')}">`;
  });
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/\*([^*]+)\*/g, '<em>$1</em>').replace(/`([^`]+)`/g, '<code>$1</code>');
  return html;
}

function renderMarkdown(markdown, jobId, imageRoot = 'output/images') {
  const lines = String(markdown || '').replace(/\r/g, '').split('\n');
  const blocks = [];
  let paragraph = [];
  let listType = '';
  let listItems = [];
  const flushParagraph = () => {
    if (paragraph.length) blocks.push(`<p>${renderInlineMarkdown(paragraph.join(' '), jobId, imageRoot)}</p>`);
    paragraph = [];
  };
  const flushList = () => {
    if (listItems.length) blocks.push(`<${listType}>${listItems.map((item) => `<li>${renderInlineMarkdown(item, jobId, imageRoot)}</li>`).join('')}</${listType}>`);
    listItems = [];
    listType = '';
  };
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) { flushParagraph(); flushList(); continue; }
    if (/^<!--/.test(trimmed)) continue;
    const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (heading) { flushParagraph(); flushList(); const level = heading[1].length; blocks.push(`<h${level}>${renderInlineMarkdown(heading[2], jobId, imageRoot)}</h${level}>`); continue; }
    const image = trimmed.match(/^!\[([^\]]*)\]\(([^)]+)\)$/);
    if (image) { flushParagraph(); flushList(); blocks.push(`<figure>${renderInlineMarkdown(trimmed, jobId, imageRoot)}${image[1] ? `<figcaption>${escapeHtml(image[1])}</figcaption>` : ''}</figure>`); continue; }
    const quote = trimmed.match(/^>\s?(.*)$/);
    if (quote) { flushParagraph(); flushList(); blocks.push(`<blockquote>${renderInlineMarkdown(quote[1], jobId, imageRoot)}</blockquote>`); continue; }
    const item = trimmed.match(/^([-*+]\s+|\d+\.\s+)(.*)$/);
    if (item) { flushParagraph(); const type = /^\d/.test(item[1]) ? 'ol' : 'ul'; if (listType && listType !== type) flushList(); listType = type; listItems.push(item[2]); continue; }
    flushList();
    paragraph.push(trimmed);
  }
  flushParagraph(); flushList();
  return blocks.join('') || '<p class="preview-placeholder">没有可显示的正文</p>';
}

async function loadComparison(jobId) {
  previewCount.textContent = '正在加载两份文章…';
  try {
    const response = await fetch(`/api/jobs/${jobId}/preview`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '预览加载失败');
    originalPreview.innerHTML = renderMarkdown(data.original_markdown, jobId, 'output/original_images');
    rewrittenPreview.innerHTML = renderMarkdown(data.rewritten_markdown, jobId, 'output/images');
    const originalLength = data.original_markdown.length;
    const rewrittenLength = data.rewritten_markdown.length;
    originalCount.textContent = `${originalLength.toLocaleString()} 字`;
    rewrittenCount.textContent = `${rewrittenLength.toLocaleString()} 字`;
    previewCount.textContent = `原文 ${originalLength.toLocaleString()} 字 · 改写 ${rewrittenLength.toLocaleString()} 字`;
  } catch (error) {
    previewCount.textContent = error.message;
  }
}

document.querySelectorAll('.preview-tab').forEach((tab) => tab.addEventListener('click', () => {
  document.querySelectorAll('.preview-tab').forEach((item) => {
    const active = item === tab;
    item.classList.toggle('active', active);
    item.setAttribute('aria-selected', String(active));
  });
  comparisonEl.dataset.view = tab.dataset.preview;
}));

function toFriendlyError(value = '') {
  const text = String(value);
  const lower = text.toLowerCase();
  if (lower.includes('connection error') || lower.includes('connecterror')) return '文字改写服务暂时无法连接，已保留原文。请检查模型接口地址和网络后重试。';
  if (lower.includes('timed out') || lower.includes('timeout')) return '文字改写服务响应超时，已保留原文。请稍后重试或缩短文章内容。';
  if (lower.includes('api key') || lower.includes('unauthorized') || lower.includes('401')) return '文字改写服务鉴权失败，已保留原文。请检查 API Key 配置。';
  return text;
}

function renderSteps(job) {
  const completed = job.status === 'completed';
  const activeIndex = job.steps.findIndex((step) => step.status === 'active');
  const doneCount = completed ? job.steps.length : job.steps.filter((step) => step.status === 'done').length;
  progressEl.style.width = `${Math.max(0, Math.min(100, (doneCount / job.steps.length) * 100))}%`;
  stepsEl.innerHTML = job.steps.map((step) => {
    const statusClass = step.status === 'done' ? 'done' : step.status === 'active' ? 'active' : step.status === 'failed' ? 'failed' : '';
    const icon = step.status === 'done' ? '✓' : step.status === 'active' ? '•' : step.status === 'failed' ? '!' : '—';
    return `<div class="step ${statusClass}"><span class="step-node">${icon}</span><div><strong>${escapeHtml(step.label)}</strong><p>${escapeHtml(step.detail)}</p></div></div>`;
  }).join('');
  if (!job.steps.length && activeIndex < 0) {
    stepsEl.innerHTML = '<div class="step empty"><span class="step-node">—</span><div><strong>等待输入</strong><p>提交链接后，处理轨迹会显示在这里</p></div></div>';
  }
}

function formatDuration(seconds = 0) {
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  return hours ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}` : `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function renderActivity(job) {
  const events = job.events || [];
  activityEventsEl.innerHTML = events.length ? events.slice(-8).reverse().map((event) => {
    const time = new Date(event.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    return `<div class="activity-event ${escapeHtml(event.kind || 'info')}"><time>${time}</time><span>${escapeHtml(event.message)}</span></div>`;
  }).join('') : '<p class="log-empty">等待任务事件…</p>';
}

function renderJob(job) {
  const labels = { queued: 'QUEUED', running: 'PROCESSING', completed: 'COMPLETE', failed: 'FAILED' };
  stateEl.textContent = labels[job.status] || String(job.status).toUpperCase();
  jobIdEl.textContent = job.id ? `JOB / ${job.id.toUpperCase()}` : 'NO ACTIVE JOB';
  elapsedEl.textContent = job.status === 'completed' ? 'DELIVERY READY' : job.status === 'failed' ? 'CHECK WARNINGS' : 'LIVE PIPELINE';
  currentActionEl.textContent = job.current_action || '等待输入';
  currentDetailEl.textContent = job.current_detail || '提交链接后，这里会显示系统正在执行的具体工作。';
  stepElapsedEl.textContent = formatDuration(job.step_elapsed_seconds);
  statContentEl.textContent = job.stats?.content_chars ? Number(job.stats.content_chars).toLocaleString() : '—';
  statImagesEl.textContent = job.stats?.image_count ?? '—';
  statProcessedEl.textContent = job.stats?.processed_images ?? '—';
  statElapsedEl.textContent = formatDuration(job.elapsed_seconds);
  renderSteps(job);
  renderActivity(job);

  if (job.status === 'completed') {
    resultPanel.classList.remove('hidden');
    resultTitle.textContent = job.title || '未命名文章';
    downloadLink.href = `/api/jobs/${job.id}/package`;
    if (job.has_preview && resultPanel.dataset.previewJob !== job.id) {
      resultPanel.dataset.previewJob = job.id;
      loadComparison(job.id);
    }
    if (job.errors?.length) {
      warnings.classList.remove('hidden');
      warnings.innerHTML = job.errors.map((error) => `<div>! ${escapeHtml(toFriendlyError(error))}</div>`).join('');
    }
    submitButton.disabled = false;
    submitButton.innerHTML = '<span class="button-icon">↗</span><span>再次处理</span><span class="button-arrow">→</span>';
  } else if (job.status === 'failed') {
    formError.textContent = toFriendlyError(job.errors?.[job.errors.length - 1] || '任务执行失败，请检查链接或服务配置。');
    submitButton.disabled = false;
    submitButton.innerHTML = '<span class="button-icon">↗</span><span>重新尝试</span><span class="button-arrow">→</span>';
  }
}

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    if (!response.ok) throw new Error('无法读取任务状态');
    const job = await response.json();
    renderJob(job);
    if (job.status === 'completed' || job.status === 'failed') {
      clearInterval(pollTimer);
      submitButton.disabled = false;
      return;
    }
    const seconds = Math.floor((Date.now() - startedAt) / 1000);
    elapsedEl.textContent = `${formatDuration(seconds)} / LIVE PIPELINE`;
    statElapsedEl.textContent = formatDuration(seconds);
  } catch (error) {
    formError.textContent = error.message;
    clearInterval(pollTimer);
    submitButton.disabled = false;
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  formError.textContent = '';
  resultPanel.classList.add('hidden');
  warnings.classList.add('hidden');
  warnings.innerHTML = '';
  if (!authorized.checked) {
    formError.textContent = '请先确认内容版权或处理授权。';
    authorized.focus();
    return;
  }
  let normalizedUrl;
  try {
    normalizedUrl = normalizeArticleUrl(urlInput.value);
  } catch (error) {
    formError.textContent = error.message;
    urlInput.focus();
    return;
  }
  submitButton.disabled = true;
  submitButton.innerHTML = '<span class="button-icon">◌</span><span>正在建立任务</span><span class="button-arrow">…</span>';
  try {
    const response = await fetch('/api/jobs', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: normalizedUrl, authorized: true, image_strategy: selectedStrategy() }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || '创建任务失败');
    startedAt = Date.now();
    renderJob(data);
    clearInterval(pollTimer);
    pollTimer = setInterval(() => pollJob(data.id), 850);
    pollJob(data.id);
  } catch (error) {
    formError.textContent = error.message;
    submitButton.disabled = false;
    submitButton.innerHTML = '<span class="button-icon">↗</span><span>开始处理</span><span class="button-arrow">→</span>';
  }
});
