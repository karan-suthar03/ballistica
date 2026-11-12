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

  const ios = /iPhone|iPod/.test(navigator.userAgent);
  let dismissed = false;
  try { dismissed = localStorage.getItem('fsTipDismissed') === '1'; } catch {}
  if (!ios || standalone || dismissed) return;

  const tip = document.createElement('div');
  tip.id = 'fs-tip';
  tip.innerHTML = 'For fullscreen: tap <b>Share</b> then <b>Add to Home Screen</b>,'
    + ' and open the game from that icon. <span>✕</span>';
  tip.addEventListener('click', () => {
    tip.remove();
    try { localStorage.setItem('fsTipDismissed', '1'); } catch {}
  });
  addEventListener('load', () => document.body.appendChild(tip));
  setTimeout(() => tip.remove(), 15000);
})();
