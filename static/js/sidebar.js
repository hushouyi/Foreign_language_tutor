/**
 * 侧边栏 — 配置面板
 * ===================
 * 侧边栏展开/收起、引擎切换、服务状态显示。
 */

import { state } from './state.js';
import { escapeHtml, showWarning } from './chat-ui.js';

// ── 状态 ──────────────────────────────────────
let sidebarOpen = false;

// ── 初始化 ────────────────────────────────────
export function initSidebar() {
  document.getElementById('sidebar-toggle').addEventListener('click', toggleSidebar);
  document.querySelector('.header-close').addEventListener('click', toggleSidebar);
  // 系统设置折叠
  document.getElementById('settings-toggle').addEventListener('click', toggleSettings);
  // 加载配置
  loadSidebarConfig();
}

// ── 系统设置折叠 ──────────────────────────────
function toggleSettings() {
  const body = document.getElementById('settings-body');
  const arrow = document.querySelector('.settings-arrow');
  const isOpen = body.classList.toggle('open');
  arrow.classList.toggle('open', isOpen);
}

// ── 展开/收起 ─────────────────────────────────
export function toggleSidebar() {
  sidebarOpen = !sidebarOpen;
  document.getElementById('sidebar-panel').classList.toggle('open', sidebarOpen);
}

// ── 加载配置 ──────────────────────────────────
async function loadSidebarConfig() {
  try {
    const resp = await fetch('/api/config');
    if (!resp.ok) return;
    const data = await resp.json();

    populateSelect('cfg-llm', data.options.llm, data.current.llm, async (value) => {
      await postConfig('llm', value);
    });

    populateSelect('cfg-search', data.options.search, data.current.search, async (value) => {
      await postConfig('search', value);
    });

    populateSilenceSelect(data);

    renderServices(data.services);
  } catch (e) {
    console.log('[sidebar] load error:', e);
  }
}

// ── 填充下拉框 ────────────────────────────────
function populateSelect(selId, options, current, onChange) {
  const sel = document.getElementById(selId);
  if (!sel) return;
  sel.innerHTML = '';
  let hasAvailable = false;
  options.forEach(opt => {
    const el = document.createElement('option');
    el.value = opt.id;
    el.textContent = opt.name;
    if (!opt.available) { el.disabled = true; } else { hasAvailable = true; }
    if (opt.id === current) el.selected = true;
    sel.appendChild(el);
  });
  sel.disabled = !hasAvailable;
  sel.onchange = () => onChange(sel.value);
}

// ── 填充语音超时选择框 ──────────────────────
function populateSilenceSelect(data) {
  const sel = document.getElementById('cfg-silence');
  if (!sel) return;
  const current = data.current.silence_timeout;
  const opts = data.options.silence_timeout;
  sel.innerHTML = '';
  for (let v = opts.min; v <= opts.max; v += opts.step) {
    const el = document.createElement('option');
    el.value = String(v);
    el.textContent = v === 0 ? '手动（空格控制）' : v + ' 秒';
    if (v === current) el.selected = true;
    sel.appendChild(el);
  }
  sel.onchange = () => {
    const val = parseInt(sel.value, 10);
    postConfig('silence_timeout', val);
    // 同步到全局状态，ASR 模块会读取这个值
    state.silenceTimeout = val;
  };
}

// ── 发送配置更新 ──────────────────────────────
async function postConfig(engine, value) {
  try {
    const resp = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ engine, value }),
    });
    const data = await resp.json();
    if (data.status === 'error') {
      showWarning(data.message || '配置失败');
    }
    await loadSidebarConfig();
  } catch (e) {
    showWarning('配置更新失败: ' + e.message);
    await loadSidebarConfig();
  }
}

// ── 渲染服务状态 ──────────────────────────────
function renderServices(services) {
  const container = document.getElementById('service-list');
  if (!container) return;
  container.innerHTML = '';
  for (const [name, info] of Object.entries(services)) {
    const item = document.createElement('div');
    item.className = 'service-item';
    const isRunning = info.status === 'running';
    const displayName = name.charAt(0).toUpperCase() + name.slice(1);
    let extra = '';
    if (info.models && info.models.length > 0) {
      extra = '<div class="service-models">' + escapeHtml(info.models.join(', ')) + '</div>';
    }
    item.innerHTML =
      '<div><span class="service-name">' + displayName + '</span>' + extra + '</div>' +
      '<span class="status-dot ' + (isRunning ? 'running' : 'stopped') + '"></span>';
    container.appendChild(item);
  }
}
