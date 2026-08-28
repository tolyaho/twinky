// ============================================================================
// BAR STYLE CONFIGURATION
// ============================================================================

const neon = {
  base: '#9146ff',  // Twitch purple
  tip: '#bf94ff'   // Lighter luxury purple
};

const barStyle = {
  itemStyle: {
    borderRadius: [10, 10, 10, 10],
    color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
      { offset: 0, color: '#7c3aed' },    // Deep purple
      { offset: 0.3, color: neon.base },  // Twitch purple
      { offset: 0.7, color: '#a855f7' },  // Medium purple
      { offset: 1, color: neon.tip }      // Light luxury purple
    ]),
    shadowBlur: 28,
    shadowColor: 'rgba(145,70,255,0.72)',
    shadowOffsetX: 0,
    shadowOffsetY: 0
  },
  backgroundStyle: {
    // Enhanced track glow
    color: 'rgba(145,70,255,0.06)',
    borderRadius: [10, 10, 10, 10],
    shadowBlur: 16,
    shadowColor: 'rgba(145,70,255,0.16)'
  },
  label: {
    show: true,
    position: 'right',
    distance: 6,
    valueAnimation: true,
    formatter: function(params) {
      // Access the value from the data object
      const value = params.data ? params.data.value : params.value;
      return Math.round(value || 0);
    }
  }
};

// Export to global scope
window.barStyle = barStyle;