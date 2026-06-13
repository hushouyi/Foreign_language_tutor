/**
 * 音频播放 — AudioContext + 顺序播放队列
 * ==========================================
 * 管理 Web Audio API 的 AudioContext 实例，
 * 维护一个 FIFO 音频队列顺序播放。
 */

import { state } from './state.js';
import { setStatus } from './chat-ui.js';

/** @type {AudioContext|null} */
export let audioCtx = null;

/** @type {{url:string, btn:HTMLElement|null}[]} */
const audioQueue = [];
let audioPlaying = false;
let audioQueueTotal = 0;
let audioQueuePlayed = 0;

/** 创建 AudioContext（页面加载时调用，初始为 suspended） */
export function initAudio() {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
}

/**
 * 在用户手势中创建/解锁 AudioContext。
 * 播一段 50ms 静音让浏览器确认"该页面已获得音频权限"。
 */
export async function unlockAudio() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    try { await audioCtx.resume(); } catch (e) { /* ignore */ }
  }
  const sr = audioCtx.sampleRate;
  const dummy = audioCtx.createBuffer(1, Math.ceil(sr * 0.05), sr);
  const src = audioCtx.createBufferSource();
  src.buffer = dummy;
  src.connect(audioCtx.destination);
  src.start(0);
}

/** 将音频加入队列顺序播放 */
export function queueAudio(url, btn) {
  if (!url) return;
  audioQueue.push({ url, btn });
  audioQueueTotal++;
  if (!audioPlaying) {
    setStatus(`${state.characterName} 朗读中... [1/${audioQueueTotal}]`);
    playNextAudio();
  } else {
    setStatus(`${state.characterName} 朗读中... [${audioQueuePlayed + 1}/${audioQueueTotal}]`);
  }
}

/** 内部：播放下一个队列项 */
function playNextAudio() {
  if (audioQueue.length === 0) {
    audioPlaying = false;
    setStatus('');
    return;
  }
  audioPlaying = true;
  const { url, btn } = audioQueue.shift();
  audioQueuePlayed++;

  const remaining = audioQueue.length;
  if (remaining > 0) {
    setStatus(`${state.characterName} 朗读中... [${audioQueuePlayed + 1}/${audioQueueTotal}]`);
  }

  document.querySelectorAll('.audio-btn.playing').forEach(b => b.classList.remove('playing'));
  if (btn) btn.classList.add('playing');

  fetch(url)
    .then(r => r.arrayBuffer())
    .then(buf => audioCtx.decodeAudioData(buf))
    .then(audioBuf => {
      const src = audioCtx.createBufferSource();
      src.buffer = audioBuf;
      src.connect(audioCtx.destination);
      src.start(0);
      src.onended = () => {
        if (btn) btn.classList.remove('playing');
        playNextAudio();
      };
    })
    .catch(() => {
      if (btn) btn.classList.remove('playing');
      playNextAudio();
    });
}

/** 重置音频队列 */
export function resetAudioQueue() {
  audioQueue.length = 0;
  audioPlaying = false;
  audioQueueTotal = 0;
  audioQueuePlayed = 0;
}

/** 用户手势中点击按钮重播单条音频 */
export async function playSingleAudio(url, btn) {
  if (!url) return;
  await unlockAudio();
  audioQueue.length = 0;
  audioPlaying = false;

  document.querySelectorAll('.audio-btn.playing').forEach(b => b.classList.remove('playing'));
  if (btn) btn.classList.add('playing');

  try {
    const resp = await fetch(url);
    const buf = await resp.arrayBuffer();
    const audioBuf = await audioCtx.decodeAudioData(buf);
    const src = audioCtx.createBufferSource();
    src.buffer = audioBuf;
    src.connect(audioCtx.destination);
    src.start(0);
    src.onended = () => { if (btn) btn.classList.remove('playing'); };
  } catch (e) {
    if (btn) btn.classList.remove('playing');
  }
}

/**
 * 播放欢迎词音频队列（由首次交互触发）。
 * 欢迎词音频 URL 须先写入 state.welcomeAudioUrls。
 */
export function playWelcomeQueue() {
  if (state.welcomePlayed || state.welcomeAudioUrls.length === 0) return;
  state.welcomePlayed = true;
  resetAudioQueue();
  state.welcomeAudioUrls.forEach(url => {
    audioQueue.push({ url, btn: null });
  });
  audioQueueTotal = state.welcomeAudioUrls.length;
  setStatus(`${state.characterName} 朗读中... [1/${audioQueueTotal}]`);
  playNextAudio();
}
