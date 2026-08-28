// ============================================================================
// MESSAGE GENERATION UTILITIES
// ============================================================================

import { NAMES, WORDS } from '../../config/chartConfig.js';

/**
 * Generate random messages for ticker display
 * @param {string[]} names - Array of names to generate messages for
 * @param {string[]} words - Array of words to use in messages
 * @returns {Object} Object mapping names to arrays of messages
 */
export function generateMessagesByName(names = NAMES, words = WORDS) {
    return Object.fromEntries(
        names.map(n => [n, Array.from({ length: 100 }, () => {
            const len = 3 + (Math.random() * 5 | 0);
            return Array.from({ length: len }, () =>
                words[(Math.random() * words.length) | 0]
            ).join(' ');
        })])
    );
}

/**
 * Create initial data rows for the chart
 * @param {string[]} names - Array of names
 * @returns {Object[]} Array of row objects
 */
export function createInitialRows(names = NAMES) {
    return names.slice(0, 6).map(n => ({
        name: n,
        value: 50 + Math.random() * 50,
        hidden: false
    })).sort((a, b) => b.value - a.value); // Sort by value descending
}

/**
 * Convert string to URL-friendly slug
 * @param {string} s - String to convert
 * @returns {string} Slugified string
 */
export function slug(s) {
    return s.toLowerCase().replace(/[^a-z0-9]+/g, '-');
}
