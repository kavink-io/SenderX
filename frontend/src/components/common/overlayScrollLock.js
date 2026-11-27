const scrollLockTokens = new Set();
let originalOverflow = '';

export function lockBodyScroll(token) {
  if (!scrollLockTokens.size) {
    originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
  }
  scrollLockTokens.add(token);
}

export function unlockBodyScroll(token) {
  scrollLockTokens.delete(token);
  if (!scrollLockTokens.size) {
    document.body.style.overflow = originalOverflow;
  }
}
