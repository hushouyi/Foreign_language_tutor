/**
 * 全局状态 — 共享状态单例
 * =========================
 * 所有模块通过 import { state } 获取同一对象引用。
 * 直接修改属性即可，无需 setter。
 */

export const state = {
  langKey: 'english',
  langDisplay: 'English',
  characterName: 'Alice',
  isProcessing: false,
  inputMode: 'keyboard',   // 'keyboard' | 'voice'
  welcomeAudioUrls: [],
  welcomePlayed: false,

  // 语音识别静默超时（秒）
  // 0 = 手动模式（按空格开始/结束），1-5 = 静默 N 秒后自动发送
  silenceTimeout: 3,
};
