// Loading screen shown until the game is actually running.
//
// Stages and where each sits on the bar:
//   download   0-80%  file_packager progress ("Downloading data... (a/b)")
//   engine    80-88%  wasm runtime up, Python/engine booting
//   loading   88-97%  app LOADING state ('@@stage loading' from bawebplus)
//   running     100%  app RUNNING ('@@stage running'); fade out shortly
//                     after so the menu's own fade-in is what shows.
// The '@@stage' lines are printed by bawebplus.web_stage on fd 1.
const Loader = (() => {
  const root = document.getElementById('loader');
  const fill = root.querySelector('.fill');
  const pct = root.querySelector('.pct');
  const stage = root.querySelector('.stage');
  const hint = root.querySelector('.hint');
  let shown = 0;
  let creep = null;

  function set(label, value) {
    if (root.classList.contains('error')) return;
    stage.textContent = label;
    shown = Math.max(shown, value);
    fill.style.width = `${shown}%`;
    pct.textContent = `${Math.floor(shown)}%`;
  }

  // Booting has no progress events; creep toward `limit` so it doesn't
  // look frozen during the several seconds of engine start.
  function creepTo(limit) {
    clearInterval(creep);
    creep = setInterval(() => {
      if (shown < limit - 0.2) set(stage.textContent, shown + (limit - shown) * 0.06);
    }, 250);
  }

  return {
    download(loaded, total) {
      set('Downloading game data', total ? (80 * loaded) / total : 0);
    },
    engine() {
      set('Starting engine', 80);
      hint.textContent = 'Almost there…';
      creepTo(88);
    },
    stage(name) {
      if (name === 'loading') {
        set('Loading assets', 88);
        creepTo(97);
      } else if (name === 'running') {
        clearInterval(creep);
        set('Ready', 100);
        setTimeout(() => root.classList.add('done'), 500);
        setTimeout(() => root.remove(), 1200);
      }
    },
    error(message) {
      clearInterval(creep);
      stage.textContent = 'Something went wrong';
      hint.textContent = `${message} — try reloading the page.`;
      root.classList.add('error');
    },
  };
})();
