// ============================================================================
// CHAT SUMMARY CARD COMPONENT
// ============================================================================

const SUMMARY_EMOTES = ['PogChamp', 'PepeLaugh', 'OMEGALUL', 'BibleThump', 'Kappa', 'KEKW', 'PepeHands'];
const SUMMARY_TOPICS = ['new skin drops', 'speedrun times', 'ranked grind', 'giveaway rumors', 'team comps'];
const SUMMARY_MOODS = ['amped', 'chill', 'chaotic', 'helpful', 'snarky', 'wholesome'];
const SUMMARY_CALLOUTS = ['mods warning about spoilers', 'viewers spamming hydrate reminders', 'a surprise host', 'a clutch playback moment'];
const SUMMARY_TRENDS = ['clip spam', 'copypasta trains', 'prediction payouts', 'VIP shoutouts', 'BTTV emote walls'];

export class ChatSummary {
    constructor(containerId = 'chat-summary-root', options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = options;
        this.rangeOptions = options.rangeOptions ?? [
            { label: 'Last 5 Minutes', value: '5m', minutes: 5 },
            { label: 'Last 15 Minutes', value: '15m', minutes: 15 },
            { label: 'Last 30 Minutes', value: '30m', minutes: 30 },
            { label: 'Last 1 Hour', value: '1h', minutes: 60 },
            { label: 'Today', value: 'today', minutes: 360 }
        ];
        this.selectedRange = options.defaultRange ?? this.rangeOptions[0]?.value ?? '5m';
        this.autoRefreshMs = options.autoRefreshMs ?? 60000;
        this.autoRefreshTimer = null;
        this.refreshAnimationTimer = null;

        this.handleRangeChange = this.handleRangeChange.bind(this);
        this.handleRefresh = this.handleRefresh.bind(this);

        if (!this.container) return;
        this.render();
    }

    render() {
        const optionsMarkup = this.rangeOptions.map(opt =>
            `<option value="${opt.value}" ${opt.value === this.selectedRange ? 'selected' : ''}>${opt.label}</option>`
        ).join('');

        this.container.innerHTML = `
            <div class="glass chat-summary-card">
                <div class="glass-body chat-summary-body">
                    <header class="chat-summary__header">
                        <h3 class="chat-summary__title">Chat Summary</h3>
                        <div class="chat-statistics__controls">
                            <div class="chat-statistics__range">
                                <div class="chat-statistics__select-wrap">
                                    <select class="chat-statistics__select" data-chat-summary-range>
                                        ${optionsMarkup}
                                    </select>
                                </div>
                            </div>
                            <button class="chat-statistics__refresh" type="button" data-chat-summary-refresh aria-label="Refresh chat summary">
                                <svg viewBox="0 0 24 24" aria-hidden="true">
                                    <path d="M4 11a8 8 0 0 1 13.66-4.66M20 13a8 8 0 0 1-13.66 4.66"
                                        fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
                                        stroke-linejoin="round" />
                                    <path d="M4 4v5h5M20 20v-5h-5" fill="none" stroke="currentColor" stroke-width="1.6"
                                        stroke-linecap="round" stroke-linejoin="round" />
                                </svg>
                            </button>
                        </div>
                    </header>
                    <p class="chat-summary__text" data-chat-summary-text>
                        Loading chat mood...
                    </p>
                </div>
            </div>
        `;

        this.cacheElements();
        this.bindEvents();
        this.refreshSummary({ emitEvent: false, animate: false });
        this.scheduleAutoRefresh();
    }

    cacheElements() {
        this.rangeSelect = this.container.querySelector('[data-chat-summary-range]');
        this.refreshBtn = this.container.querySelector('[data-chat-summary-refresh]');
        this.summaryText = this.container.querySelector('[data-chat-summary-text]');
    }

    bindEvents() {
        if (this.rangeSelect) {
            this.rangeSelect.removeEventListener('change', this.handleRangeChange);
            this.rangeSelect.addEventListener('change', this.handleRangeChange);
        }
        if (this.refreshBtn) {
            this.refreshBtn.removeEventListener('click', this.handleRefresh);
            this.refreshBtn.addEventListener('click', this.handleRefresh);
        }
    }

    handleRangeChange(event) {
        this.selectedRange = event.target.value;
        this.refreshSummary({ animate: false, reason: 'range-change' });
        this.scheduleAutoRefresh();
    }

    handleRefresh(event) {
        if (event) event.preventDefault();
        this.refreshSummary({ animate: true, reason: 'manual' });
        this.scheduleAutoRefresh();
    }

    refreshSummary({ animate = false, emitEvent = true, reason = 'manual' } = {}) {
        const summary = this.generateSummary(this.selectedRange);
        if (this.summaryText) {
            this.summaryText.textContent = summary;
        }

        if (animate && this.refreshBtn) {
            this.refreshBtn.classList.add('is-refreshing');
            if (this.refreshAnimationTimer) clearTimeout(this.refreshAnimationTimer);
            this.refreshAnimationTimer = setTimeout(() => this.refreshBtn?.classList.remove('is-refreshing'), 900);
        }

        if (emitEvent && this.container) {
            const detail = {
                range: this.selectedRange,
                label: this.getRangeLabel(this.selectedRange),
                summary,
                reason
            };
            this.container.dispatchEvent(new CustomEvent('chat-summary:refresh', { detail }));
        }
    }

    generateSummary(rangeValue) {
        const range = this.rangeOptions.find(opt => opt.value === rangeValue) ?? this.rangeOptions[0];
        const minutes = range?.minutes ?? 15;
        const mood = this.pick(SUMMARY_MOODS);
        const emote = this.pick(SUMMARY_EMOTES);
        const topic = this.pick(SUMMARY_TOPICS);
        const callout = this.pick(SUMMARY_CALLOUTS);
        const trend = this.pick(SUMMARY_TRENDS);
        const hypePercent = this.randomInt(40, 92);
        const viewerMentions = this.randomInt(3, 8);

        return [
            `Chat feels ${mood} over the last ${minutes} minutes with about ${hypePercent}% of lines echoing ${emote}.`,
            `Viewers keep circling around ${topic} while ${callout} steals side attention.`,
            `Mods flagged ${viewerMentions} spicy tangents but the room resets quickly.`,
            `Several regulars are driving ${trend}, giving the feed a steady rhythm.`,
            `Overall tone stays upbeat with plenty of reaction spam whenever the streamer pivots topics.`
        ].join(' ');
    }

    scheduleAutoRefresh() {
        this.clearAutoRefresh();
        if (!Number.isFinite(this.autoRefreshMs) || this.autoRefreshMs <= 0) return;
        this.autoRefreshTimer = setInterval(() => this.refreshSummary({ animate: false, reason: 'auto' }), this.autoRefreshMs);
    }

    clearAutoRefresh() {
        if (this.autoRefreshTimer) {
            clearInterval(this.autoRefreshTimer);
            this.autoRefreshTimer = null;
        }
    }

    getRangeLabel(value) {
        return this.rangeOptions.find(opt => opt.value === value)?.label || 'Custom';
    }

    pick(arr) {
        return arr[(Math.random() * arr.length) | 0];
    }

    randomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    destroy() {
        this.clearAutoRefresh();
        if (this.refreshAnimationTimer) {
            clearTimeout(this.refreshAnimationTimer);
            this.refreshAnimationTimer = null;
        }
        if (this.rangeSelect) {
            this.rangeSelect.removeEventListener('change', this.handleRangeChange);
        }
        if (this.refreshBtn) {
            this.refreshBtn.removeEventListener('click', this.handleRefresh);
        }
        if (this.container) {
            this.container.innerHTML = '';
        }
    }
}

export default ChatSummary;
