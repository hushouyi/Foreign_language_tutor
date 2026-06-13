/**
 * 自动滚动管理 — 微信风格
 * ===========================
 * 监听消息区滚动，用户在顶部时显示「↓ 最新消息」浮标。
 * 所有函数可安全多次调用。
 */

const messagesEl = document.getElementById('messages');
let userScrolledUp = false;

export function initScroll() {
  messagesEl.addEventListener('scroll', () => {
    const atBottom = messagesEl.scrollHeight - messagesEl.scrollTop - messagesEl.clientHeight < 40;
    if (atBottom) {
      userScrolledUp = false;
      hideScrollHint();
    } else if (!userScrolledUp) {
      userScrolledUp = true;
      showScrollHint();
    }
  }, { passive: true });
}

function showScrollHint() {
  let hint = document.getElementById('scroll-hint');
  if (!hint) {
    hint = document.createElement('button');
    hint.id = 'scroll-hint';
    hint.textContent = '↓ 最新消息';
    hint.addEventListener('click', scrollBottom);
    messagesEl.appendChild(hint);
  }
}

function hideScrollHint() {
  document.getElementById('scroll-hint')?.remove();
}

export function scrollBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
  userScrolledUp = false;
  hideScrollHint();
}

export function autoScrollIfNeeded() {
  if (!userScrolledUp) {
    requestAnimationFrame(() => scrollBottom());
  }
}
