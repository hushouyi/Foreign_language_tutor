/**
 * NDJSON 流解析 — 聊天请求、段揭示、发送/取消
 * =============================================
 * 管理 fetch + ReadableStream 读取 /api/chat 的 NDJSON 事件流，
 * 缓冲 segment 事件，等 done 后逐段揭示+播放音频。
 */

import { state } from './state.js';
import { setStatus, showWarning, addMessage, addSystemMessage,
         clearMessages, updateHeader, inputText, sendBtn, micBtn } from './chat-ui.js';
import { audioCtx, unlockAudio, playSingleAudio, resetAudioQueue } from './audio-player.js';

// ── 内部状态 ──────────────────────────────────
export const pendingSegments = [];
export let revealGeneration = 0;
let revealTotal = 0;
let revealIndex = 0;
let abortController = null;

// ── 发送消息 ──────────────────────────────────
export async function sendMessage() {
  const text = inputText.value.trim();
  if (!text || state.isProcessing) return;
  await unlockAudio();
  inputText.value = '';
  chatStream(text);
}

// ── 取消当前 AI 回复（Ctrl+C） ────────────────
export function cancelChat() {
  if (abortController) {
    abortController.abort();
    abortController = null;
  }
  pendingSegments.length = 0;
  revealGeneration++;
  state.isProcessing = false;
  sendBtn.disabled = false;
  inputText.disabled = false;
  inputText.focus();
  micBtn.classList.remove('mic-disabled');
  setStatus('⛔ 已取消');
  setTimeout(() => setStatus(''), 2000);
}

// ── NDJSON 流处理 ─────────────────────────────
async function chatStream(userText) {
  if (state.isProcessing) return;
  state.isProcessing = true;
  sendBtn.disabled = true;
  inputText.disabled = true;
  micBtn.classList.add('mic-disabled');

  // 清空上一轮未 reveal 完的段
  pendingSegments.length = 0;
  revealGeneration++;
  revealTotal = 0;
  revealIndex = 0;

  // 显示用户消息
  addMessage('user', userText, null, null);

  // 发送请求
  let response;
  abortController = new AbortController();
  try {
    response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userText }),
      signal: abortController.signal,
    });
    if (!response.ok) {
      const errText = await response.text();
      addSystemMessage('❌ 请求失败: ' + errText);
      finishProcessing();
      return;
    }
  } catch (e) {
    if (e.name === 'AbortError') return;
    addSystemMessage('❌ 网络错误: ' + e.message);
    finishProcessing();
    return;
  }

  // 读取 NDJSON 流
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        if (buffer.trim()) processLine(buffer.trim());
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.trim()) continue;
        processLine(line.trim());
      }
    }
  } catch (e) {
    if (e.name !== 'AbortError') {
      addSystemMessage('❌ 读取流错误: ' + e.message);
    }
  } finally {
    abortController = null;
    reader.releaseLock();
    finishProcessing();
  }
}

function finishProcessing() {
  state.isProcessing = false;
  sendBtn.disabled = false;
  inputText.disabled = false;
  inputText.focus();
  micBtn.classList.remove('mic-disabled');
}

function processLine(line) {
  let evt;
  try { evt = JSON.parse(line); } catch (e) { return; }

  switch (evt.type) {
    case 'status':
      if (evt.status === 'thinking') {
        setStatus(`${state.characterName} 思考中···`, 'thinking-dots');
      } else if (evt.status === 'searching') {
        setStatus(`🔍 正在搜索: "${evt.query}"`);
      } else if (evt.status === 'search_results') {
        setStatus(`📋 找到 ${evt.count} 条搜索结果`);
        setTimeout(() => {
          if (state.isProcessing) {
            setStatus(`${state.characterName} 思考中···`, 'thinking-dots');
          }
        }, 1200);
      } else if (evt.status === 'goodbye') {
        setStatus('');
        addSystemMessage('👋 会话已结束，输入新消息继续对话');
      }
      break;

    case 'segment':
      pendingSegments.push({
        content: evt.content,
        translation: evt.translation || null,
        audioUrl: null,
      });
      break;

    case 'audio':
      if (evt.url && pendingSegments.length > 0) {
        pendingSegments[pendingSegments.length - 1].audioUrl = evt.url;
      }
      break;

    case 'lang_switch':
      state.langKey = evt.lang_key;
      state.langDisplay = evt.display;
      updateHeader();
      addSystemMessage(`🌐 已切换到 ${evt.display}`);
      break;

    case 'warning':
      showWarning(evt.message);
      break;

    case 'error':
      addSystemMessage('❌ ' + (evt.message || '未知错误'));
      break;

    case 'cleared':
      pendingSegments.length = 0;
      resetAudioQueue();
      clearMessages();
      addSystemMessage('🗑️ 对话已清空');
      break;

    case 'done':
      setStatus('');
      revealTotal = pendingSegments.length;
      revealIndex = 0;
      revealNextResponseSegment();
      break;
  }
}

/** 逐段揭示 AI 回复：显示一段 → 播音频 → 完成后显示下一段 */
async function revealNextResponseSegment() {
  const myGen = revealGeneration;
  if (pendingSegments.length === 0) { setStatus(''); return; }
  const seg = pendingSegments.shift();
  const msgEl = addMessage('ai', seg.content, seg.translation, null);

  revealIndex++;
  setStatus(`${state.characterName} 朗读中... [${revealIndex}/${revealTotal}]`);

  if (!seg.audioUrl || myGen !== revealGeneration) {
    revealNextResponseSegment();
    return;
  }

  const btn = msgEl.querySelector('.audio-btn');
  if (!btn || myGen !== revealGeneration) {
    revealNextResponseSegment();
    return;
  }

  btn.className = 'audio-btn';
  btn.dataset.url = seg.audioUrl;
  btn.onclick = () => playSingleAudio(seg.audioUrl, btn);

  try {
    const resp = await fetch(seg.audioUrl);
    const buf = await resp.arrayBuffer();
    const audioBuf = await audioCtx.decodeAudioData(buf);
    const src = audioCtx.createBufferSource();
    src.buffer = audioBuf;
    src.connect(audioCtx.destination);
    src.start(0);
    btn.classList.add('playing');
    await new Promise(r => { src.onended = r; });
    btn.classList.remove('playing');
  } catch (e) { /* audio skipped */ }

  if (myGen !== revealGeneration) return;
  revealNextResponseSegment();
}
