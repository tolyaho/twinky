// ============================================================================
// MAIN APPLICATION ENTRY POINT
// ============================================================================

import { BarChart, ChatStatistics, ChatSummary } from './components/index.js';

class App {
    constructor() {
        this.components = new Map();
        this.init();
    }   

    init() {
        this.setupGlobalStyles();
        this.initializeComponents();
        this.setupGlobalEventListeners();
    }

    setupGlobalStyles() {
        // Add any global styles or theme setup here
        document.documentElement.style.setProperty('--app-primary-color', '#7c3aed');
        document.documentElement.style.setProperty('--app-secondary-color', '#bf94ff');
    }

    initializeComponents() {
        // Initialize the bar chart component
        const barChartContainer = document.getElementById('bar-chart');
        if (barChartContainer) {
            const barChart = new BarChart('bar-chart');
            this.components.set('barChart', barChart);
        }

        const chatStatsRoot = document.getElementById('chat-statistics-root');
        if (chatStatsRoot) {
            const chatStats = new ChatStatistics('chat-statistics-root');
            this.components.set('chatStatistics', chatStats);
        }

        const chatSummaryRoot = document.getElementById('chat-summary-root');
        if (chatSummaryRoot) {
            const chatSummary = new ChatSummary('chat-summary-root');
            this.components.set('chatSummary', chatSummary);
        }
    }

    setupGlobalEventListeners() {
        // Global resize handler
        window.addEventListener('resize', () => {
            this.components.forEach(component => {
                if (component.resize) {
                    component.resize();
                }
            });
        });

        // Global error handler
        window.addEventListener('error', (event) => {
            console.error('Global error:', event.error);
        });
    }

    // Public API methods
    getComponent(name) {
        return this.components.get(name);
    }

    destroy() {
        this.components.forEach(component => {
            if (component.destroy) {
                component.destroy();
            }
        });
        this.components.clear();
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});

// Export for potential module usage
export default App;
