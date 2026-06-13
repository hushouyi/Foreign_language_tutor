/**
 * 语音识别 — Web Speech API + 切换输入模式
 * ==========================================
 * 管理麦克风权限、SpeechRecognition 生命周期、
 * 电平表可视化、键盘/语音输入模式切换。
 *
 * 语音模式行为：按空格键开始识别 → 再按空格停止并发送。
 * ESC 可以随时退出语音模式。
 */

import { state } from './state.js';
import { setStatus, showWarning, inputText, micBtn, updateModeUI } from './chat-ui.js';
import { sendMessage } from './stream-reader.js';

// ── 语种 → STT lang 映射 ─────────────────────
const STT_LANG_MAP = {
  english: 'en-US',
  japanese: 'ja-JP',
  french: 'fr-FR',
  spanish: 'es-ES',
  korean: 'ko-KR',
  german: 'de-DE',
  russian: 'ru-RU',
  chinese: 'zh-CN',
  italian: 'it-IT',
  portuguese: 'pt-BR',
  arabic: 'ar-SA',
};

function getSTTLang(langKey) {
  return STT_LANG_MAP[langKey] || 'en-US';
}

// ── 语音识别运行时状态 ────────────────────────
let recognition = null;
export let isListening = false;
let speechDetected = false;
let resultReceived = false;
// 麦克风设备选择
let selectedMicId = null;
// 电平表
let micStream = null;
let audioCtxMeter = null;
let meterInterval = null;
// 计时器
let stuckTimer = null;
let silenceTimer = null;

// ── 初始化 ────────────────────────────────────
/** 枚举麦克风设备（用于调试/将来设备选择） */
export function initASR() {
  navigator.mediaDevices.enumerateDevices()
    .then(devices => {
      const mics = devices.filter(d => d.kind === 'audioinput');
      console.log('[mic] available mics:', mics.map(m => m.label || m.deviceId.slice(0, 20) + '...'));
      if (mics.length > 0) {
        setStatus('🎤 ' + mics.length + ' 个麦克风可用');
        setTimeout(() => setStatus(''), 2000);
      }
    })
    .catch(e => console.log('[mic] enumerate error:', e));
}

// ── 电平表 ────────────────────────────────────
function startMeter(stream) {
  micStream = stream;
  try {
    audioCtxMeter = new (window.AudioContext || window.webkitAudioContext)();
    const src = audioCtxMeter.createMediaStreamSource(stream);
    const analyser = audioCtxMeter.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    meterInterval = setInterval(() => {
      analyser.getByteTimeDomainData(data);
      let max = 0;
      for (let i = 0; i < data.length; i++) {
        const v = Math.abs(data[i] - 128);
        if (v > max) max = v;
      }
      const pct = Math.min(100, (max / 128) * 100);
      if (pct > 3) {
        micBtn.style.boxShadow = '0 0 ' + (6 + pct / 3) + 'px rgba(7,193,96,' + (0.3 + pct / 150) + ')';
        micBtn.style.background = 'rgba(7,193,96,' + Math.min(0.3, pct / 300) + ')';
      } else {
        micBtn.style.boxShadow = 'none';
        micBtn.style.background = 'transparent';
      }
    }, 50);
  } catch (e) {
    console.log('[mic] meter error:', e);
  }
}

function stopMeter() {
  if (meterInterval) { clearInterval(meterInterval); meterInterval = null; }
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  if (audioCtxMeter) { try { audioCtxMeter.close(); } catch (e) { /* ignore */ } audioCtxMeter = null; }
  micBtn.style.boxShadow = 'none';
  micBtn.style.background = 'transparent';
}

// ── 内部清理 ──────────────────────────────────
export function micCleanup() {
  if (stuckTimer) { clearTimeout(stuckTimer); stuckTimer = null; }
  if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
  stopMeter();
  isListening = false;
  if (recognition) {
    try { recognition.abort(); } catch (e) { /* ignore */ }
    recognition = null;
  }
  micBtn.className = 'mic mic-idle';
  micBtn.style.boxShadow = 'none';
  micBtn.style.background = 'transparent';
  setStatus('');
  updateModeUI();
}

// ── 开始/停止聆听 ────────────────────────────
function startListening() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    showWarning('浏览器不支持语音识别，请使用 Chrome 或 Edge');
    return;
  }
  if (state.isProcessing) {
    console.log('[mic] start rejected: processing');
    return;
  }

  console.log('[mic] ======== startListening ========');
  console.log('[mic] selectedMicId:', selectedMicId);
  speechDetected = false;
  resultReceived = false;
  const recogLang = getSTTLang(state.langKey);
  console.log('[mic] recognition.lang=' + recogLang);

  navigator.mediaDevices.getUserMedia({
    audio: selectedMicId ? { deviceId: { exact: selectedMicId } } : true,
  })
    .then((stream) => {
      console.log('[mic] getUserMedia OK');
      const track = stream.getAudioTracks()[0];
      console.log('[mic] using device:', track.label);
      console.log('[mic] device settings:', JSON.stringify(track.getSettings ? track.getSettings() : {}));
      setStatus('🎤 ' + track.label);
      setTimeout(() => setStatus(''), 2000);
      startMeter(stream);

      recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = recogLang;

      // 事件处理
      recognition.onaudiostart = () => console.log('[mic] EVENT: audiostart');
      recognition.onaudioend = () => console.log('[mic] EVENT: audioend');
      recognition.onsoundstart = () => {
        speechDetected = true;
        console.log('[mic] EVENT: soundstart');
      };
      recognition.onsoundend = () => console.log('[mic] EVENT: soundend');
      recognition.onspeechstart = () => console.log('[mic] EVENT: speechstart');
      recognition.onspeechend = () => console.log('[mic] EVENT: speechend');
      recognition.onnomatch = (event) => {
        console.log('[mic] EVENT: nomatch', event);
      };

      recognition.onresult = (event) => {
        if (!isListening) return;
        resultReceived = true;
        let fullFinal = '';
        let lastInterim = '';
        for (let i = 0; i < event.results.length; i++) {
          const r = event.results[i];
          const t = r[0].transcript;
          if (r.isFinal) {
            fullFinal += t;
            console.log('[mic] FINAL result:', JSON.stringify(t), 'confidence:', r[0].confidence);
          } else {
            lastInterim = t;
            console.log('[mic] interim result:', JSON.stringify(t));
          }
        }
        inputText.value = fullFinal + (lastInterim ? ' ' + lastInterim : '');
        inputText.dispatchEvent(new Event('input'));
        if (fullFinal) resetSilenceTimer();
      };

      recognition.onerror = (event) => {
        console.log('[mic] EVENT: onerror —', event.error, event.message || '');
        if (event.error === 'not-allowed') {
          showWarning('麦克风权限被拒绝');
          micCleanup();
        } else if (event.error === 'no-speech') {
          showWarning('没有检测到语音');
          micCleanup();
        } else if (event.error === 'aborted') {
          console.log('[mic]   (aborted by user)');
        } else {
          showWarning('语音识别错误: ' + event.error);
          micCleanup();
        }
      };

      function resetSilenceTimer() {
        if (silenceTimer) clearTimeout(silenceTimer);
        const timeout = state.silenceTimeout;
        if (!timeout || timeout <= 0) return;  // 0 = 手动模式，不自动发送
        silenceTimer = setTimeout(() => {
          console.log('[mic] silence timeout — sending');
          if (isListening) {
            isListening = false;
            if (recognition) { try { recognition.abort(); } catch (e) { /* ignore */ } }
            micCleanup();
            if (inputText.value.trim()) sendMessage();
          }
        }, timeout * 1000);
      }

      recognition.onend = () => {
        console.log('[mic] EVENT: onend — isListening=' + isListening + " text='" + inputText.value.trim() + "'");
        if (isListening) {
          if (resultReceived) {
            console.log('[mic] onend: restarting');
            resetSilenceTimer();
            try { recognition.start(); } catch (e) { micCleanup(); }
          } else {
            console.log('[mic] onend: no result ever received');
            isListening = false;
            micCleanup();
            if (!speechDetected) {
              showWarning('没有检测到语音，请检查麦克风');
            } else {
              showWarning('语音识别服务无响应，请检查网络或重试');
            }
          }
        }
      };

      try {
        recognition.start();
        isListening = true;
        micBtn.className = 'mic mic-listening';
        inputText.placeholder = '说点什么...';
        setStatus('🎤 聆听中');
        console.log('[mic] recognition.start() OK');

        stuckTimer = setTimeout(() => {
          if (isListening && !resultReceived) {
            console.log('[mic] STUCK: 12s without any result');
            if (speechDetected) {
              showWarning('检测到声音但识别无结果，可能是网络问题或麦克风不兼容');
            } else {
              setStatus('🎤 没有检测到声音，请检查麦克风');
            }
          }
        }, 12000);
      } catch (e) {
        console.log('[mic] recognition.start() ERROR:', e);
        showWarning('启动语音识别失败: ' + e.message);
        micCleanup();
      }
    })
    .catch((err) => {
      console.log('[mic] getUserMedia DENIED:', err.message);
      showWarning('麦克风权限被拒绝，请在浏览器地址栏左侧点击🔒设置麦克风权限');
    });
}

function stopListening() {
  console.log("[mic] ======== stopListening ========");
  console.log("[mic] current text='" + inputText.value.trim() + "'");
  console.log('[mic] speechDetected=' + speechDetected + ' resultReceived=' + resultReceived);
  isListening = false;

  if (stuckTimer) { clearTimeout(stuckTimer); stuckTimer = null; }
  if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }

  if (recognition) {
    try {
      console.log('[mic] calling recognition.stop()');
      recognition.stop();
      console.log('[mic] recognition.stop() returned');
    } catch (e) {
      console.log('[mic] stop() error:', e);
      try { recognition.abort(); } catch (e2) { /* ignore */ }
    }
    recognition = null;
  }

  const text = inputText.value.trim();

  if (resultReceived && text) {
    micCleanup();
    sendMessage();
  } else {
    micCleanup();
    if (speechDetected && !resultReceived) {
      showWarning('检测到声音但无法识别为文字，请检查网络或尝试 Edge 浏览器');
    } else if (!speechDetected) {
      showWarning('没有检测到语音');
    } else {
      showWarning('语音识别失败');
    }
  }
}

// ── 外部接口 ──────────────────────────────────
/** 切换麦克风（开始/停止聆听） */
export function toggleMic() {
  if (isListening) {
    stopListening();
  } else {
    startListening();
  }
}

/** 切换输入模式（键盘/语音） */
export function toggleInputMode() {
  state.inputMode = state.inputMode === 'keyboard' ? 'voice' : 'keyboard';
  updateModeUI();
  if (state.inputMode === 'voice') {
    setStatus('🎤 语音模式 — 按空格键开始/结束');
    setTimeout(() => setStatus(''), 2500);
  } else {
    setStatus('');
  }
}
