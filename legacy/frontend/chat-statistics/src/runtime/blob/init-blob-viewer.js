// src/runtime/blob/init-blob-viewer.js
const viewer = document.getElementById('brandBlob');
if (!viewer) return;

const nudge = () => { viewer.getBoundingClientRect(); };

const ready = (window.customElements?.whenDefined?.('spline-viewer')) || Promise.resolve();

// Some macOS Chrome builds need a layout pass after the element renders.
ready.then(() => {
  viewer.addEventListener('load', nudge, { once: true });
  requestAnimationFrame(nudge);
  setTimeout(nudge, 120);
});
