// ============================================================================
// CHART CONFIGURATION CONSTANTS
// ============================================================================

export const SPACE_GROTESK_STACK = '"Space Grotesk", "SpaceGrotesk", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';

export const CHART_CONFIG = {
    TICKER_MIN: 32,          // never smaller than this
    TICKER_MAX: 64,          // never larger than this
    TICKER_RATIO: 0.75,      // ~% of each category band to occupy
    TICKER_VPAD: 4,    // breathing room inside the band
    UPDATE_MS: 300,
    TICKER_HEIGHT: 52,
    TICKER_DURATION_MS: 30000,
    MAX_TICKERS: 3,
    MIN_ACTIVE_BARS: 2,
    GAP_PREFIX: "__gap__:",
    GRID_TOP: 12,
    GRID_BOTTOM: 8,
    TARGET_BAND_PX: 68,      // desired px per row
    MIN_PLOT_PX: 140,        // keeps 1–2 rows compact
};

export const NAMES = [
    "LMAO Spam",
    "W Train",
    "Copium Crew",
    "Story Time",
    "6/7 Check",
    "GG EZ",
    "Question Marks"
];

export const WORDS = [
    "gg", "lol", "kappa", "pog", "nice", "bro", "nah", "ez", "carry", "clutch",
    "omg", "pls", "wow", "fast", "slow", "left", "right", "mid", "push", "hold",
    "stack", "rotate", "go", "stop", "win", "lose", "draw", "idk", "why", "true",
    "cap", "based", "clean", "peak", "safe", "greed", "alpha", "buff", "nerf",
    "rng", "tilt", "glhf", "wp", "value", "spam", "meta", "strat", "yep", "nope", "hype"
];

export const CHART_OPTIONS = {
    textStyle: {
        fontFamily: SPACE_GROTESK_STACK
    },
    xAxis: {
        max: 'dataMax',
        axisLabel: { show: false },
        splitLine: { show: false }
    },
    yAxis: {
        type: 'category',
        inverse: true,
        axisLine: { show: false },
        axisTick: { show: false },
        boundaryGap: false,
        axisLabel: {
            show: true,
            margin: 8, // was 12  ← tighter by ~33%
            width: 200,
            overflow: 'truncate',
            formatter: (val) =>
                String(val).startsWith(CHART_CONFIG.GAP_PREFIX) ? '' : `{pad|}{name|${val}}`,
            fontFamily: SPACE_GROTESK_STACK,
            fontSize: 21,
            fontWeight: 600,
            color: '#ffffff',
            rich: {
                pad: { width: 16, height: 1 },
                name: {
                    fontFamily: SPACE_GROTESK_STACK,
                    fontSize: 21,
                    fontWeight: 600,
                    color: '#ffffff',
                    padding: [0, 8, 0, 0]
                }
            }
        }
    },
    data: [],
    grid: {
        left: 8,
        right: 12,
        top: 2,
        bottom: 2,
        containLabel: true
    },
    series: [{
        type: 'bar',
        showBackground: false,
        itemStyle: {
            borderRadius: [8, 8, 8, 8],
            color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: '#7c3aed' },
                { offset: 0.3, color: '#9146ff' },
                { offset: 0.7, color: '#a855f7' },
                { offset: 1, color: '#bf94ff' }
            ]),
            shadowBlur: 28,
            shadowColor: 'rgba(145,70,255,0.8)',
            borderWidth: 2,
            borderColor: 'rgba(191,148,255,0.4)'
        },
        label: {
            show: true,
            position: 'right',
            distance: 6,
            valueAnimation: false,
            fontFamily: SPACE_GROTESK_STACK,
            fontSize: 18,
            color: '#ffffff',
            formatter: (p) => Math.round(Number(p?.data?.value ?? p?.value) || 0)
        },
        universalTransition: true,
        data: []
    }],
    animationDuration: 0,
    animationDurationUpdate: Math.floor(CHART_CONFIG.UPDATE_MS * 0.8),
    animationEasingUpdate: 'linear'
};
