// Fullscreen on phones.
//
// Android/desktop: the Fullscreen API works on any element, but only
// from a user gesture, so the first tap/click requests it (and locks
// landscape where supported).
//
// iPhone: Safari only allows fullscreen for <video>. The way to run
// without browser bars is launching from a home-screen icon (the
// manifest + apple-mobile-web-app-capable make that a fullscreen web
// app), so when not already launched that way, show a one-time tip.
(() => {
  const standalone = navigator.standalone
    || matchMedia('(display-mode: fullscreen), (display-mode: standalone)').matches;
  const root = document.documentElement;

  // Automatic fullscreen on the first tap/click: on for the deployed
  // site, off for local previews (localhost).
  // Phones/tablets only (touch as the main pointer); never on desktop.
  const AUTO_FULLSCREEN = !['localhost', '127.0.0.1'].includes(location.hostname)
    && matchMedia('(pointer: coarse)').matches;

  if (!standalone && root.requestFullscreen) {
    if (!AUTO_FULLSCREEN) return;
    const goFullscreen = () => {
      if (document.fullscreenElement) return;
      root.requestFullscreen({ navigationUI: 'hide' })
        .then(() => screen.orientation?.lock?.('landscape'))
        .catch(() => {});
    };
    // Every gesture, so it comes back after the user leaves fullscreen.
    addEventListener('pointerup', goFullscreen, { capture: true });
    addEventListener('keydown', goFullscreen, { capture: true });
    return;
  }

  // iPhone/iPad (iPadOS reports itself as a Mac with touch).
  const ios = /iPhone|iPod|iPad/.test(navigator.userAgent)
    || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1);
  let dismissed = false;
  try { dismissed = localStorage.getItem('fsTipDismissed') === '1'; } catch {}
  if (!ios || standalone || dismissed) return;

  const share = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">'
    + '<path fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    + 'stroke-linejoin="round" d="M12 3v12M8 7l4-4 4 4M6 11H5v10h14V11h-1"/></svg>';
  const tip = document.createElement('div');
  tip.id = 'fs-tip';
  tip.innerHTML = `
    <b>Play fullscreen on iPhone / iPad</b>
    <ol>
      <li>Tap the <b>Share</b> button ${share} in Safari's toolbar.</li>
      <li>Scroll down and tap <b>Add to Home Screen</b>.</li>
      <li>Tap <b>Add</b>, then open BombSquad from the new icon.</li>
    </ol>
    <div class="fs-actions">
      <button data-a="never">Don't show again</button>
      <button data-a="close">Got it</button>
    </div>`;
  tip.addEventListener('click', e => {
    const a = e.target.closest('button')?.dataset.a;
    if (!a) return;
    if (a === 'never') {
      try { localStorage.setItem('fsTipDismissed', '1'); } catch {}
    }
    tip.remove();
  });
  addEventListener('load', () => document.body.appendChild(tip));
})();
