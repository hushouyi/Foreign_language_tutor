/**
 * 入口 — 将所有模块连接起来
 * ============================
 * 初始化各模块，绑定全局事件（键盘快捷键、按钮、窗口事件）。
 *
 * 使用方式：<script type="module" src="/static/js/app.js"></script>
 */

import { state } from './state.js';
import { initScroll } from './scroll.js';
import { initAudio, unlockAudio, playWelcomeQueue } from './audio-player.js';
import {
  addMessage, addSystemMessage, updateHeader, updateModeUI,
  inputText, sendBtn, micBtn,
} from './chat-ui.js';
import { sendMessage, cancelChat } from './stream-reader.js';
import { initASR, toggleMic, toggleInputMode, micCleanup, isListening as asrIsListening } from './asr.js';
import { initSidebar } from './sidebar.js';

// ══════════════════════════════════════════════════
// 初始化
// ══════════════════════════════════════════════════

initScroll();
initAudio();
initASR();
initSidebar();

// ══════════════════════════════════════════════════
// 首次交互 — 解锁 AudioContext + 播欢迎词
// ══════════════════════════════════════════════════

async function onFirstInteraction() {
  document.removeEventListener('click', onFirstInteraction, true);
  document.removeEventListener('touchstart', onFirstInteraction, true);
  document.removeEventListener('keydown', onFirstInteraction, true);

  await unlockAudio();

  if (state.welcomeAudioUrls.length > 0) {
    playWelcomeQueue();
  }
}
document.addEventListener('click', onFirstInteraction, true);
document.addEventListener('touchstart', onFirstInteraction, true);
document.addEventListener('keydown', onFirstInteraction, true);

// ══════════════════════════════════════════════════
// 事件绑定
// ══════════════════════════════════════════════════

// 输入文本变化 → 发送按钮状态
inputText.addEventListener('input', () => {
  sendBtn.disabled = !inputText.value.trim() || state.isProcessing || asrIsListening;
});

// 全局 ESC：清空输入框 + 停止语音识别
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    e.preventDefault();
    if (asrIsListening) {
      micCleanup();
    }
    inputText.value = '';
    sendBtn.disabled = true;
    inputText.dispatchEvent(new Event('input'));
  }
});

// Ctrl+C：取消当前 AI 回复（类似终端的 Ctrl+C）
document.addEventListener('keydown', (e) => {
  if (e.ctrlKey && (e.key === 'c' || e.key === 'C')) {
    if (state.isProcessing) {
      e.preventDefault();
      cancelChat();
    }
  }
});

// 语音模式：空格键 = 开关（按一次开始，再按一次完成发送）
document.addEventListener('keydown', (e) => {
  if (state.inputMode !== 'voice') return;
  if (e.key !== ' ' && e.key !== 'Space') return;
  if (e.repeat || state.isProcessing) return;
  e.preventDefault();
  toggleMic();
});

// Enter 发送
inputText.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// 发送按钮
sendBtn.addEventListener('click', sendMessage);

// 麦克风按钮：切换输入模式（键盘/语音）
micBtn.addEventListener('click', () => {
  if (state.isProcessing) return;
  if (asrIsListening) {
    micCleanup();
  }
  toggleInputMode();
});

// 关闭页面时通知服务器
// 使用多种事件 + fetch keepalive 提升可靠性
function shutdownServer() {
  // 标记已发送，避免重复
  if (window._shutdownSent) return;
  window._shutdownSent = true;
  try {
    fetch('/api/shutdown', { method: 'POST', keepalive: true, body: '{}' });
  } catch (e) { /* 浏览器关闭中，忽略 */ }
}
window.addEventListener('beforeunload', shutdownServer);
window.addEventListener('pagehide', shutdownServer);

// ══════════════════════════════════════════════════
// 启动
// ══════════════════════════════════════════════════

async function initApp() {
  try {
    const resp = await fetch('/api/init');
    const data = await resp.json();

    state.langKey = data.current_lang;
    state.langDisplay = data.lang_display;
    state.characterName = data.character_name;
    state.silenceTimeout = data.silence_timeout;
    updateHeader();

    const welcome = data.welcome;
    if (welcome && welcome.segments) {
      if (welcome.audio_urls) {
        state.welcomeAudioUrls = welcome.audio_urls.map(a => a.url).filter(Boolean);
      }
      welcome.segments.forEach((seg, i) => {
        const audioUrl = (welcome.audio_urls && welcome.audio_urls[i]?.url) || null;
        addMessage('ai', seg.content, seg.translation || null, audioUrl);
      });
    }
  } catch (e) {
    addSystemMessage('⚠️ 初始化失败: ' + e.message);
  }

  updateModeUI();
  inputText.focus();
}

initApp();
