# ECharts Demo

Modern, Sorbet-themed dashboard that highlights a Twitch-style chat feed, live ticker overlays, and an animated bar chart powered by ECharts. The UI stays framework‑free and leans on native ES modules for clarity.

## Project Layout

```
echarts-demo/
├── index.html
├── src/
│   ├── app.js
│   ├── components/
│   │   ├── chart/bar/
│   │   │   ├── BarChart.js
│   │   │   └── index.js
│   │   ├── chat/
│   │   │   ├── index.js
│   │   │   ├── statistics/
│   │   │   │   ├── ChatStatistics.js
│   │   │   │   └── index.js
│   │   │   └── summary/
│   │   │       ├── ChatSummary.js
│   │   │       └── index.js
│   │   └── index.js
│   ├── config/
│   │   └── chartConfig.js
│   ├── lib/
│   │   ├── chart/chartHelpers.js
│   │   └── messages/messageGenerator.js
│   ├── runtime/
│   │   ├── blob/init-blob-viewer.js
│   │   └── chat/chat-simulator.js
│   ├── styles/
│   │   ├── base/layout.css
│   │   ├── components/chat/chat-panel.css
│   │   ├── components/navigation/navbar.css
│   │   ├── effects/glass-liquid.css
│   │   ├── effects/ticker.css
│   │   ├── loaders/spline-loader.css
│   │   └── theme/BarStyle.js
│   └── assets/
│       └── icons/
├── package.json
├── package-lock.json
└── README.md
```

## File Guide

| Path | Purpose |
| --- | --- |
| `index.html` | Static shell that wires fonts, CSS bundles, inline widgets, and module scripts; containers (`#bar-chart`, `#chat-statistics-root`, etc.) live here. |
| `src/app.js` | Application entry: bootstraps global styles, instantiates components, and keeps a registry for resize/destroy helpers. |
| `src/components/chart/bar/BarChart.js` | ECharts integration, ticker overlay handling, resize math, and rendering loop for the animated bar chart. |
| `src/components/chat/statistics/ChatStatistics.js` | Renders the chat statistics card, simulates metrics per range, and dispatches range/change events. |
| `src/components/chat/summary/ChatSummary.js` | Generates narrative chat summaries, range picker, and refresh animations for the summary card. |
| `src/components/index.js` | Barrel that exposes every component through a single import surface (`import { BarChart, … } from './components'`). |
| `src/config/chartConfig.js` | Single source of truth for chart dimensions, ticker timing, label formatting, and demo data presets. |
| `src/lib/chart/chartHelpers.js` | Math helpers for translating rows to ECharts categories, locating pixels, and shaping layout gaps. |
| `src/lib/messages/messageGenerator.js` | Creates the pseudo chat dataset (rows, tickers, slugs) used to drive the chart animation. |
| `src/runtime/blob/init-blob-viewer.js` | Guards Spline viewer interactions (scroll/pinch) and nudges layout on load so the blob renders crisply. |
| `src/runtime/chat/chat-simulator.js` | Vanilla chat simulator that generates list items, autoscroll logic, and new-message CTA visibility. |
| `src/styles/base/layout.css` | Global resets, layout scaffolding, chart/timer positioning, and responsive breakpoints. |
| `src/styles/components/navigation/navbar.css` | Styles the sticky navbar, logo, link hover states, and profile/support buttons. |
| `src/styles/components/chat/chat-panel.css` | Handles the right-hand chat dock, badges, message pills, and notification button. |
| `src/styles/effects/glass-liquid.css` | Shared glassmorphism cards, blob container, and shimmer effects. |
| `src/styles/effects/ticker.css` | Styling for ticker overlays that float above bars when a row is expanded. |
| `src/styles/loaders/spline-loader.css` | Loader/animation polish for Spline embeds and hero art. |
| `src/styles/theme/BarStyle.js` | Gradient/lighting config piped into ECharts through the global `window.barStyle` helper. |
| `assets/` | Contains icons or static imagery referenced by CSS/HTML if needed. |

Use this table when onboarding teammates—each row answers “what does this file own?”

## Development

1. **Install dependencies**
   ```bash
   npm install
   ```
2. **Run a dev server** (any static server works):
   ```bash
   npx http-server .
   # or python3 -m http.server 8000
   ```
3. **Open the app**  
   `http://localhost:8080` (or your chosen port).

### Working With Components
- Import from the barrel: `import { ChatStatistics } from './components';`
- Keep UI-only tweaks inside the relevant CSS module to avoid leaking styles globally.
- Shared constants belong in `src/config`; shared logic in `src/lib`.

### Configuration
```javascript
import { CHART_CONFIG } from './src/config/chartConfig.js';

// Example tweaks
CHART_CONFIG.UPDATE_MS = 500;   // slower animation loop
CHART_CONFIG.MAX_TICKERS = 5;   // allow more concurrent tickers
```

## Browser Support

Tested on the latest Chrome, Firefox, Edge, and Safari with ES module support.

## License

MIT — use, remix, and learn freely.***
