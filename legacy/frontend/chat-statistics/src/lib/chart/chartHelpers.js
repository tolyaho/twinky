// ============================================================================
// CHART HELPER UTILITIES
// ============================================================================

import { CHART_CONFIG } from '../../config/chartConfig.js';

export function getBarStartX(chart) {
    try {
        const x = chart.convertToPixel({ xAxisIndex: 0 }, 0); // x=0 → bar start
        return Number.isFinite(x) ? x : 0;
    } catch { return 0; }
}

export function getBarStartXFor(chart, name) {
    const option = chart.getOption();
    const grid = option.grid[0];
    const yAxis = option.yAxis[0];
    const data = yAxis.data || [];
    const nameIndex = data.indexOf(name);

    if (nameIndex === -1) return grid.left;

    // Calculate approximate position based on grid and chart dimensions
    return grid.left + 10; // Small offset for visual alignment
}

export function getYPixel(chart, categoryName) {
    try {
        const y = chart.convertToPixel({ yAxisIndex: 0 }, categoryName);
        return Number.isFinite(y) ? y : NaN;
    } catch { return NaN; }
}

export function gapNameOf(barName) {
    return `${CHART_CONFIG.GAP_PREFIX}${barName}`;
}

export function buildLayout(rows, expanded) {
    const categories = [];
    const data = [];

    // Sort rows by value (highest to lowest) before building layout
    const sortedRows = [...rows].sort((a, b) => b.value - a.value);

    sortedRows.forEach((row, index) => {
        if (!row.hidden) {
            categories.push(row.name);
            data.push({
                value: row.value,
                name: row.name,
                itemStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                        { offset: 0, color: '#7c3aed' },
                        { offset: 0.3, color: '#9146ff' },
                        { offset: 0.7, color: '#a855f7' },
                        { offset: 1, color: '#bf94ff' }
                    ])
                }
            });

            // Add gap if this row is expanded
            if (expanded.has(row.name)) {
                categories.push(gapNameOf(row.name));
                data.push({
                    value: 0,
                    name: gapNameOf(row.name),
                    itemStyle: { opacity: 0 }
                });
            }
        }
    });

    return { categories, data };
}
