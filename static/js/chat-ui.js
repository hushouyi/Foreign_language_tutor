/**
 * DOM 操作 — 消息渲染、状态栏、提示、DOM 引用
 * ===========================================
 * 所有直接 DOM 读写集中在此模块。
 * 其他模块调用这里导出的函数来更新界面。
 */

import { state } from './state.js';
import { autoScrollIfNeeded } from './scroll.js';
import { playSingleAudio } from './audio-player.js';

// ── DOM 元素引用 ──────────────────────────────
export const messagesEl = document.getElementById('messages');
export const statusBar = document.getElementById('status-bar');
export const inputText = document.getElementById('input-text');
export const sendBtn = document.getElementById('send-btn');
export const header = document.getElementById('header');
export const warningToast = document.getElementById('warning-toast');
export const micBtn = document.getElementById('mic-btn');

// ── 工具 ──────────────────────────────────────
export function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── 状态栏 ────────────────────────────────────
export function setStatus(text, cls = '') {
  statusBar.textContent = text;
  statusBar.className = cls;
  if (text) statusBar.classList.remove('hidden');
  else statusBar.classList.add('hidden');
}

// ── 警告横幅 ──────────────────────────────────
export function showWarning(msg) {
  warningToast.textContent = msg;
  warningToast.classList.add('show');
  setTimeout(() => warningToast.classList.remove('show'), 4000);
}

// ── 消息渲染 ──────────────────────────────────
/**
 * 添加一条消息气泡。
 * @param {'ai'|'user'|'system'} type
 * @param {string|null} content
 * @param {string|null} translation
 * @param {string|null} audioUrl  仅 AI 消息有此字段
 * @returns {HTMLElement} 消息容器 div.message
 */
export function addMessage(type, content, translation, audioUrl) {
  const div = document.createElement('div');
  div.className = `message ${type}`;

  if (type === 'system') {
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = content;
    div.appendChild(bubble);
    messagesEl.appendChild(div);
    autoScrollIfNeeded();
    return div;
  }

  const avatar = document.createElement('div');
  avatar.className = `avatar ${type}`;
  avatar.textContent = type === 'ai' ? state.characterName.charAt(0) : '我';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';

  const textSpan = document.createElement('div');
  textSpan.className = 'text';
  textSpan.textContent = content;
  bubble.appendChild(textSpan);

  if (translation) {
    const transSpan = document.createElement('div');
    transSpan.className = 'translation';
    transSpan.textContent = translation;
    bubble.appendChild(transSpan);
  }

  const audioBtn = document.createElement('button');
  audioBtn.className = 'audio-btn hidden';
  audioBtn.innerHTML = '&#x1F50A;';

  if (type === 'ai') {
    div.appendChild(avatar);
    div.appendChild(bubble);
    div.appendChild(audioBtn);
  } else {
    div.appendChild(audioBtn);
    div.appendChild(bubble);
    div.appendChild(avatar);
  }

  messagesEl.appendChild(div);
  autoScrollIfNeeded();

  if (type === 'ai' && audioUrl) {
    audioBtn.className = 'audio-btn';
    audioBtn.dataset.url = audioUrl;
    audioBtn.onclick = () => playSingleAudio(audioUrl, audioBtn);
  }

  return div;
}

/** 添加系统消息（居中灰色小字） */
export function addSystemMessage(text) {
  return addMessage('system', text, null, null);
}

/** 清空消息区 */
export function clearMessages() {
  messagesEl.innerHTML = '';
}

/** 更新 header 标题 */
export function updateHeader() {
  header.textContent = `${state.characterName} - AI 语言助教 [${state.langDisplay}]`;
}

/** 更新输入模式对应的 UI */
export function updateModeUI() {
  if (state.inputMode === 'voice') {
    micBtn.textContent = '🎤';
    micBtn.className = 'mic mic-idle';
    micBtn.title = '切换到键盘模式';
    inputText.placeholder = '按空格键开始/结束';
  } else {
    micBtn.textContent = '⌨️';
    micBtn.className = 'mic mic-idle';
    micBtn.title = '切换到语音模式';
    inputText.placeholder = '输入消息...';
  }
}
