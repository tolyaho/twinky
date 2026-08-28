// ============================================================================
// BAR CHART COMPONENT
// ============================================================================

import { CHART_CONFIG, CHART_OPTIONS, SPACE_GROTESK_STACK } from '../../../config/chartConfig.js';
import { generateMessagesByName, createInitialRows, slug } from '../../../lib/messages/messageGenerator.js';
import { getBarStartX, getBarStartXFor, getYPixel, gapNameOf, buildLayout } from '../../../lib/chart/chartHelpers.js';

export class BarChart {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.chart = null;
        this.overlay = null;
        this.activeTickers = new Map();
        this.expanded = new Set();
        this.tickerH = CHART_CONFIG.TICKER_HEIGHT;
        this.baseGridPadTop = CHART_CONFIG.GRID_TOP ?? 12;
        this.baseGridPadBottom = CHART_CONFIG.GRID_BOTTOM ?? 8;
        this.gridPadTop = this.baseGridPadTop;
        this.gridPadBottom = this.baseGridPadBottom;

        // Merge with default options
        this.options = { ...CHART_OPTIONS, ...options };

        // Initialize data
        this.rows = createInitialRows();
        this.messagesByName = generateMessagesByName();
        this.nextToggleAt = Date.now() + 5000; // Initialize toggle timing

        // Bind methods
        this.tick = this.tick.bind(this);
        this.handleResize = this.handleResize.bind(this);
        this.handleClick = this.handleClick.bind(this);

        this.init();
    }

    init() {
        this.ensureFontsLoaded().then(() => {
            this.createChart();
            this.setupEventListeners();
            this.startUpdateLoop();
        });
    }

    async ensureFontsLoaded() {
        const fontAPI = document.fonts;
        if (!fontAPI || typeof fontAPI.load !== 'function') return;

        try {
            const promises = [
                fontAPI.load('16px "Palatino"'),
                fontAPI.load('16px "Palatino Linotype"')
            ];

            if (fontAPI.ready && typeof fontAPI.ready.then === 'function') {
                promises.push(fontAPI.ready.catch(() => undefined));
            }

            await Promise.all(promises);
        } catch {
            // ignore font loading issues; browser will fall back
        }
    }

    readGridPads() {
        const cs = getComputedStyle(this.container);
        const t = parseFloat(cs.getPropertyValue('--chart-pad-top'));
        const b = parseFloat(cs.getPropertyValue('--chart-pad-bottom'));
        const defTop = (CHART_CONFIG.GRID_TOP ?? 12);
        const defBot = (CHART_CONFIG.GRID_BOTTOM ?? 8);
        this.baseGridPadTop = Number.isFinite(t) ? t : defTop;
        this.baseGridPadBottom = Number.isFinite(b) ? b : defBot;
        this.gridPadTop = this.baseGridPadTop;
        this.gridPadBottom = this.baseGridPadBottom;
    }

    createChart() {
        this.chart = echarts.init(this.container, undefined, { renderer: 'canvas' });
        this.chart.setOption(this.options);
        window.chart = this.chart;
        this.chart.on('finished', () => this.repositionTickers());
        this.readGridPads();
    }


    setupEventListeners() {
        this.chart.on('click', this.handleClick);
        window.addEventListener('resize', this.handleResize);

        // Add ResizeObserver for container size changes
        if (window.ResizeObserver) {
            const resizeObserver = new ResizeObserver(() => {
                if (this.chart) {
                    this.chart.resize();
                }
            });
            resizeObserver.observe(this.container);

            // Store reference for cleanup
            this.resizeObserver = resizeObserver;
        }
    }

    startUpdateLoop() {
        this.readGridPads();
        this.renderFrame();
        this.updateInterval = setInterval(this.tick, CHART_CONFIG.UPDATE_MS);
    }


    handleClick(p) {
        if (p.componentType !== 'series' || p.seriesType !== 'bar') return;
        const nm = String(p.name || '');
        if (nm.startsWith(CHART_CONFIG.GAP_PREFIX)) return;
        this.showTickerFor(nm);
    }

    handleResize() {
        this.readGridPads();
        this.chart.resize();
        this.renderFrame();
    }

    renderFrame() {
        const { categories, data } = buildLayout(this.rows, this.expanded);

        const cats = categories.slice();
        const vals = data.slice();
        const isGap = v => String(v).startsWith(CHART_CONFIG.GAP_PREFIX);
        // Keep all gaps - don't strip leading/trailing gaps

        const totalBands = cats.length || 1;

        const gridLeft = 16, gridRight = 64;
        const baseTop = this.baseGridPadTop ?? (CHART_CONFIG.GRID_TOP ?? 12);
        const baseBottom = this.baseGridPadBottom ?? (CHART_CONFIG.GRID_BOTTOM ?? 8);
        const h = this.container.clientHeight;

        // Dynamic grid height to prevent stretching with few categories
        const TARGET_BAND = CHART_CONFIG.TARGET_BAND_PX ?? 56;   // desired px per row
        const MIN_PLOT = CHART_CONFIG.MIN_PLOT_PX ?? 140;  // keeps 1–2 rows compact
        const MAX_PLOT = Math.max(80, h - (baseTop + baseBottom));     // never overflow card

        let desiredPlotH = totalBands * TARGET_BAND;
        desiredPlotH = Math.max(MIN_PLOT, Math.min(MAX_PLOT, desiredPlotH));

        const slack = Math.max(0, h - desiredPlotH - baseTop - baseBottom);
        const extraTop = (totalBands <= 3) ? slack / 2 : 0;
        const extraBottom = slack - extraTop;
        const gridTop = baseTop + extraTop;
        const dynamicBottom = baseBottom + extraBottom;
        this.gridPadTop = gridTop;
        this.gridPadBottom = dynamicBottom;

        // recompute plotH/bandH using the new bottom
        const plotH = h - (gridTop + dynamicBottom);
        const bandH = plotH / totalBands;
        const BAR_RATIO = 0.72, BAR_MIN = 12, BAR_MAX = 46;
        const barWidthPx = Math.max(BAR_MIN, Math.min(BAR_MAX, Math.floor(bandH * BAR_RATIO)));
        this.barWidthPx = barWidthPx;

        const TR = CHART_CONFIG.TICKER_RATIO ?? 0.75;
        const TMIN = CHART_CONFIG.TICKER_MIN ?? 24;  // was smaller before
        const TMAX = CHART_CONFIG.TICKER_MAX ?? 80;

        let tH = Math.floor(bandH * TR);
        tH = Math.max(tH, TMIN);
        tH = Math.min(tH, barWidthPx - 4, TMAX);
        this.tickerH = tH;

        this.lastCats = cats;
        this.bandH = bandH;

        this.chart.setOption({
            yAxis: {
                type: 'category',
                data: cats,
                boundaryGap: true,             // centers bars when there are few categories
                axisLine: { show: false },
                axisTick: { show: false },
                axisLabel: {
                    show: true,
                    margin: 8,
                    width: 200,
                    overflow: 'truncate',
                    formatter: (val) =>
                        String(val).startsWith(CHART_CONFIG.GAP_PREFIX) ? '' : `{pad|}{name|${val}}`,
                    fontFamily: SPACE_GROTESK_STACK,
                    fontSize: 17,
                    fontWeight: 600,
                    color: '#ffffff',
                    rich: {
                        pad: { width: 16, height: 1 },
                        name: {
                            fontFamily: SPACE_GROTESK_STACK,
                            fontSize: 17,
                            fontWeight: 600,
                            color: '#ffffff',
                            padding: [0, 8, 0, 0]
                        }
                    }
                }
            },
            grid: {
                left: gridLeft,
                right: gridRight,
                top: gridTop,
                bottom: this.gridPadBottom,    // use the dynamic bottom
                containLabel: true
            },
            series: [{
                ...CHART_OPTIONS.series[0],
                data: vals,
                barWidth: barWidthPx,
                barCategoryGap: '24%'
            }]
        }, false);

        if (this.overlay) {
            this.overlay.style.top = (this.gridPadTop ?? 12) + 'px';
            this.overlay.style.bottom = (this.gridPadBottom ?? 8) + 'px';
            this.overlay.style.setProperty('--ticker-h', this.tickerH + 'px');
        }

        this.activeTickers.forEach(({ rowEl }) => rowEl.style.setProperty('--ticker-h', this.tickerH + 'px'));

        this.repositionTickers();
        requestAnimationFrame(() => this.repositionTickers());
    }


    tick() {
        // Jitter real bars
        for (const r of this.rows) {
            if (!r.hidden) {
                r.value = Math.max(0, r.value + (Math.random() - 0.5) * 2);
            }
        }

        // Occasional appear/disappear
        const now = Date.now();
        if (now >= this.nextToggleAt) {
            const visIdxs = this.rows.map((r, i) => ({ r, i })).filter(x => !x.r.hidden);
            const hidIdxs = this.rows.map((r, i) => ({ r, i })).filter(x => x.r.hidden);

            let wantShow = false;
            if (visIdxs.length <= CHART_CONFIG.MIN_ACTIVE_BARS) wantShow = true;
            else if (hidIdxs.length === 0) wantShow = false;
            else wantShow = Math.random() < 0.5;

            if (wantShow && hidIdxs.length) {
                this.rows[hidIdxs[(Math.random() * hidIdxs.length) | 0].i].hidden = false;
            } else if (!wantShow && visIdxs.length > CHART_CONFIG.MIN_ACTIVE_BARS) {
                const idx = visIdxs[(Math.random() * visIdxs.length) | 0].i;
                const nm = this.rows[idx].name;
                const id = 'ticker-' + slug(nm);
                if (this.activeTickers.has(id)) this.hideTicker(id);
                this.rows[idx].hidden = true;
            }
            this.rescheduleToggle();
        }

        this.renderFrame();
    }

    rescheduleToggle() {
        this.nextToggleAt = Date.now() + 20000 + Math.random() * 15000;
    }

    // Ticker management methods
    ensureOverlay() {
        if (this.overlay) return;
        this.overlay = document.createElement('div');
        this.overlay.className = 'ticker-layer';
        this.overlay.setAttribute('aria-hidden', 'true');
        this.container.style.position = 'relative';
        this.container.appendChild(this.overlay);
        this.overlay.style.setProperty('--ticker-h', this.tickerH + 'px');

        // align overlay with ECharts grid (critical)
        this.overlay.style.left = '0px';
        this.overlay.style.right = '0px';
        this.overlay.style.top = (this.gridPadTop ?? 0) + 'px';
        this.overlay.style.bottom = (this.gridPadBottom ?? 0) + 'px';
    }

    makeTickerRow(name) {
        const row = document.createElement('div');
        row.className = 'ticker-row';
        row.style.setProperty('--ticker-h', this.tickerH + 'px');
        row.dataset.name = name;
        row.id = 'ticker-' + slug(name);

        const mask = document.createElement('div');
        mask.className = 'ticker-mask';
        const track = document.createElement('div');
        track.className = 'ticker-track';

        const msgs = this.messagesByName[name] || [];
        for (let k = 0; k < 2; k++) {
            for (let i = 0; i < msgs.length; i++) {
                const pill = document.createElement('div');
                pill.className = 'msg-box';
                pill.textContent = msgs[i];
                track.appendChild(pill);
            }
        }

        mask.appendChild(track);
        row.appendChild(mask);
        return { row, track, mask };
    }

    startMarquee(track) {
        const contentW = track.scrollWidth;
        const pxPerSec = 130;
        track.style.animationDuration = Math.max(6, contentW / pxPerSec) + 's';
    }

    positionTickerAtGap(rowEl, barName) {
        const opt = this.chart.getOption();
        const yData = opt.yAxis?.[0]?.data || [];
        const grid = opt.grid?.[0] || {};

        const toNum = (v) => (typeof v === 'number') ? v : parseFloat(v) || 0;
        const topPad = toNum(grid.top ?? this.gridPadTop ?? 12);
        const botPad = toNum(grid.bottom ?? this.gridPadBottom ?? 8);

        const chartH = this.chart.getHeight();
        const plotH = Math.max(1, chartH - topPad - botPad);
        const bands = Math.max(1, yData.length);
        const bandH = plotH / bands;
        const gapNm = gapNameOf(barName);

        const halfTicker = this.tickerH / 2;
        const halfBar = (this.barWidthPx ?? bandH) / 2;
        const vPad = CHART_CONFIG.TICKER_VPAD ?? 0;

        // Prefer the centre of the GAP category (it already reserves space for the ticker)
        let centerY = getYPixel(this.chart, gapNm);

        // If the GAP is not in the axis (or conversion failed) fall back to the bar itself.
        if (!Number.isFinite(centerY)) {
            const barCenter = getYPixel(this.chart, barName);
            if (Number.isFinite(barCenter)) {
                centerY = barCenter + halfBar + vPad + halfTicker;
            }
        }

        // Last fallback – derive position from the category index so the ticker never floats away.
        if (!Number.isFinite(centerY)) {
            let idx = yData.indexOf(gapNm);
            if (idx < 0) idx = yData.indexOf(barName);
            if (idx < 0) idx = 0;
            const base = topPad + (idx + 0.5) * bandH;
            centerY = base;
        }

        // Clamp the ticker so it always sits within the plotted grid window.
        const minCenter = topPad + halfTicker;
        const maxCenter = chartH - botPad - halfTicker;
        const clampedCenter = Math.max(minCenter, Math.min(maxCenter, centerY));

        // Convert to overlay coordinates (origin = grid top).
        const overlayTop = Math.round(clampedCenter - halfTicker - topPad);
        rowEl.style.top = overlayTop + 'px';
        rowEl.style.setProperty('--ticker-h', this.tickerH + 'px');

        // Horizontal anchor aligns with the axis label text (bar titles).
        const axisLabel = opt.yAxis?.[0]?.axisLabel || {};
        const labelWidth = toNum(axisLabel.width);
        const labelMargin = toNum(axisLabel.margin);
        const padWidth = axisLabel?.rich?.pad ? toNum(axisLabel.rich.pad.width) : 0;
        const barStartX = Math.round(getBarStartX(this.chart));
        let rowLeft = barStartX;
        if (labelWidth > 0 || labelMargin > 0 || padWidth > 0) {
            rowLeft = barStartX - labelMargin - labelWidth + padWidth;
        }
        rowEl.style.setProperty('--ticker-left', Math.max(0, Math.round(rowLeft)) + 'px');
    }


    enforceMaxTickers(exemptId = null) {
        while (this.activeTickers.size >= CHART_CONFIG.MAX_TICKERS) {
            const oldestId = this.activeTickers.keys().next().value;
            if (oldestId === exemptId) {
                const ids = Array.from(this.activeTickers.keys());
                const candidate = ids.find(k => k !== exemptId);
                if (!candidate) break;
                this.hideTicker(candidate);
            } else {
                this.hideTicker(oldestId);
            }
        }
    }

    showTickerFor(barName) {
        this.ensureOverlay();

        const id = 'ticker-' + slug(barName);
        if (this.activeTickers.has(id)) { this.hideTicker(id); return; }

        this.enforceMaxTickers();
        this.expanded.add(barName);
        this.renderFrame();

        const { row, track } = this.makeTickerRow(barName);
        this.overlay.appendChild(row);

        const positionTicker = () => {
            this.positionTickerAtGap(row, barName);
            this.startMarquee(track);
        };

        positionTicker();

        const activate = () => row.classList.add('enter');
        if (typeof requestAnimationFrame === 'function') {
            requestAnimationFrame(activate);
        } else {
            activate();
        }

        let fallback = null;
        const finalizePlacement = () => {
            positionTicker();
            this.chart.off('finished', finalizePlacement);
            if (fallback !== null) {
                clearTimeout(fallback);
                fallback = null;
            }
        };

        this.chart.on('finished', finalizePlacement);
        fallback = setTimeout(finalizePlacement, 360);

        const timer = setTimeout(() => this.hideTicker(id), CHART_CONFIG.TICKER_DURATION_MS);
        this.activeTickers.set(id, { rowEl: row, killTimer: timer, name: barName });
    }
    hideTicker(id) {
        const entry = this.activeTickers.get(id);
        if (!entry) return;
        const { rowEl, killTimer, name } = entry;
        clearTimeout(killTimer);

        const cleanup = () => {
            if (rowEl.parentNode) rowEl.parentNode.removeChild(rowEl);
            this.activeTickers.delete(id);
            this.expanded.delete(name);
            this.renderFrame();
        };

        let fallbackTimer = null;

        const onEnd = (e) => {
            if (e.target !== rowEl || e.animationName !== 'ticker-rise') return;
            rowEl.removeEventListener('animationend', onEnd);
            if (fallbackTimer !== null) {
                clearTimeout(fallbackTimer);
                fallbackTimer = null;
            }
            cleanup();
        };

        fallbackTimer = setTimeout(() => {
            rowEl.removeEventListener('animationend', onEnd);
            cleanup();
        }, 520); // safety net if animation event is skipped

        rowEl.addEventListener('animationend', onEnd);
        rowEl.classList.remove('enter');
        rowEl.classList.add('exit');
    }

    repositionTickers() {
        this.activeTickers.forEach(({ rowEl, name }) => this.positionTickerAtGap(rowEl, name));
    }

    // Public API methods
    destroy() {
        if (this.chart) {
            this.chart.dispose();
            this.chart = null;
        }
        window.removeEventListener('resize', this.handleResize);
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        clearInterval(this.updateInterval);
    }

    resize() {
        if (this.chart) {
            this.chart.resize();
        }
    }
}
