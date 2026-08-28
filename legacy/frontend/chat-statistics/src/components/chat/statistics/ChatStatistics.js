// ============================================================================
// CHAT STATISTICS CARD COMPONENT
// ============================================================================

export class ChatStatistics {
    constructor(containerId = 'chat-statistics-root', options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = options;
        this.rangeOptions = options.rangeOptions ?? [
            { label: 'Last 5 Minutes', value: '5m' },
            { label: 'Last 15 Minutes', value: '15m' },
            { label: 'Last 30 Minutes', value: '30m' },
            { label: 'Last 1 Hour', value: '1h' },
            { label: 'Today', value: 'today' }
        ];
        this.selectedRange = options.defaultRange ?? this.rangeOptions[0]?.value ?? '5m';
        this.stats = {
            messagesPerMin: 0,
            uniqueViewers: 0,
            giftedSubs: 0,
            channelPoints: 0,
            newFollowers: 0,
            clipsShared: 0
        };
        this.autoRefreshMs = options.autoRefreshMs ?? 60000;
        this.autoRefreshTimer = null;
        this.refreshAnimationTimer = null;
        this.numberFormatter = new Intl.NumberFormat('en-US');

        this.handleRangeChange = this.handleRangeChange.bind(this);
        this.handleRefresh = this.handleRefresh.bind(this);

        if (!this.container) return;
        this.render();
    }

    render() {
        if (!this.container) return;
        const optionsMarkup = this.rangeOptions.map(opt =>
            `<option value="${opt.value}" ${opt.value === this.selectedRange ? 'selected' : ''}>${opt.label}</option>`
        ).join('');

        this.container.innerHTML = `
            <div class="glass chat-statistics">
                <div class="glass-body chat-statistics-body">
                    <header class="chat-statistics__header">
                        <div>
                            <h3 class="chat-statistics__title">Chat Statistics</h3>
                        </div>
                        <div class="chat-statistics__controls">
                            <div class="chat-statistics__range">
                                <div class="chat-statistics__select-wrap">
                                    <select class="chat-statistics__select" data-chat-range>
                                        ${optionsMarkup}
                                    </select>
                                </div>
                            </div>
                            <button class="chat-statistics__refresh" type="button" data-chat-refresh aria-label="Refresh chat statistics">
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
                    <div class="chat-statistics__stats">
                        <div class="chat-statistics__stat">
                            <span class="chat-statistics__label">Messages / min</span>
                            <span class="chat-statistics__value" data-chat-messages>284</span>
                        </div>
                        <div class="chat-statistics__stat">
                            <span class="chat-statistics__label">Unique Viewers</span>
                            <span class="chat-statistics__value" data-chat-viewers>1,126</span>
                        </div>
                        <div class="chat-statistics__stat chat-statistics__stat--highlight">
                            <span class="chat-statistics__label">Gifted Subs</span>
                            <span class="chat-statistics__value" data-chat-subs>42</span>
                        </div>
                        <div class="chat-statistics__stat">
                            <span class="chat-statistics__label">Channel Points Spent</span>
                            <span class="chat-statistics__value" data-chat-points>12,800</span>
                        </div>
                        <div class="chat-statistics__stat">
                            <span class="chat-statistics__label">New Followers</span>
                            <span class="chat-statistics__value" data-chat-followers>126</span>
                        </div>
                        <div class="chat-statistics__stat">
                            <span class="chat-statistics__label">Clips Shared</span>
                            <span class="chat-statistics__value" data-chat-clips>18</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.cacheElements();
        this.bindEvents();
        this.refreshStats({ emitEvent: false, animate: false });
        this.scheduleAutoRefresh();
    }

    cacheElements() {
        this.rangeSelect = this.container.querySelector('[data-chat-range]');
        this.refreshBtn = this.container.querySelector('[data-chat-refresh]');
        this.messagesEl = this.container.querySelector('[data-chat-messages]');
        this.viewersEl = this.container.querySelector('[data-chat-viewers]');
        this.subsEl = this.container.querySelector('[data-chat-subs]');
        this.pointsEl = this.container.querySelector('[data-chat-points]');
        this.followersEl = this.container.querySelector('[data-chat-followers]');
        this.clipsEl = this.container.querySelector('[data-chat-clips]');
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
        const changeEvent = new CustomEvent('chat-statistics:range-change', {
            detail: {
                value: this.selectedRange,
                label: this.getRangeLabel(this.selectedRange)
            }
        });
        this.container.dispatchEvent(changeEvent);
        this.refreshStats({ animate: false, reason: 'range-change' });
        this.scheduleAutoRefresh();
    }

    handleRefresh(event) {
        if (event) event.preventDefault();
        this.refreshStats({ animate: true, reason: 'manual' });
        this.scheduleAutoRefresh();
    }

    refreshStats({ animate = false, emitEvent = true, reason = 'manual' } = {}) {
        const stats = this.generateRandomStats(this.selectedRange);
        this.stats = stats;
        this.applyStats(stats);

        if (animate && this.refreshBtn) {
            this.refreshBtn.classList.add('is-refreshing');
            if (this.refreshAnimationTimer) clearTimeout(this.refreshAnimationTimer);
            this.refreshAnimationTimer = setTimeout(() => this.refreshBtn?.classList.remove('is-refreshing'), 900);
        }

        if (emitEvent && this.container) {
            const refreshEvent = new CustomEvent('chat-statistics:refresh', {
                detail: {
                    range: this.selectedRange,
                    label: this.getRangeLabel(this.selectedRange),
                    stats,
                    reason
                }
            });
            this.container.dispatchEvent(refreshEvent);
        }
    }

    applyStats(stats) {
        if (this.messagesEl) {
            this.messagesEl.textContent = this.numberFormatter.format(stats.messagesPerMin);
        }
        if (this.viewersEl) {
            this.viewersEl.textContent = this.numberFormatter.format(stats.uniqueViewers);
        }
        if (this.subsEl) {
            this.subsEl.textContent = this.numberFormatter.format(stats.giftedSubs);
        }
        if (this.pointsEl) {
            this.pointsEl.textContent = this.numberFormatter.format(stats.channelPoints);
        }
        if (this.followersEl) {
            this.followersEl.textContent = this.numberFormatter.format(stats.newFollowers);
        }
        if (this.clipsEl) {
            this.clipsEl.textContent = this.numberFormatter.format(stats.clipsShared);
        }
    }

    generateRandomStats(rangeValue) {
        const presets = {
            '5m': { minutes: 5, msgRate: [220, 360], uniqueRatio: [0.18, 0.26], subs: [2, 12], points: [1800, 3800], followers: [6, 18], clips: [0, 3] },
            '15m': { minutes: 15, msgRate: [200, 320], uniqueRatio: [0.2, 0.28], subs: [8, 28], points: [5200, 9200], followers: [14, 40], clips: [1, 6] },
            '30m': { minutes: 30, msgRate: [180, 280], uniqueRatio: [0.22, 0.3], subs: [18, 48], points: [9400, 15800], followers: [26, 70], clips: [2, 10] },
            '1h': { minutes: 60, msgRate: [150, 240], uniqueRatio: [0.24, 0.32], subs: [32, 82], points: [16800, 28400], followers: [44, 120], clips: [4, 16] },
            'today': { minutes: 360, msgRate: [120, 200], uniqueRatio: [0.26, 0.34], subs: [120, 260], points: [64000, 112000], followers: [160, 340], clips: [10, 40] }
        };
        const fallback = { minutes: 30, msgRate: [150, 260], uniqueRatio: [0.22, 0.3], subs: [18, 48], points: [9400, 15800], followers: [26, 70], clips: [2, 10] };
        const preset = presets[rangeValue] ?? fallback;
        const messagesPerMin = this.randomInt(preset.msgRate[0], preset.msgRate[1]);
        const uniqueRatio = this.randomBetween(preset.uniqueRatio[0], preset.uniqueRatio[1]);
        const uniqueViewers = Math.max(1, Math.round(messagesPerMin * preset.minutes * uniqueRatio));
        const giftedSubs = this.randomInt(preset.subs[0], preset.subs[1]);
        const channelPoints = this.randomInt(preset.points[0], preset.points[1]);
        const newFollowers = this.randomInt(preset.followers[0], preset.followers[1]);
        const clipsShared = this.randomInt(preset.clips[0], preset.clips[1]);
        return { messagesPerMin, uniqueViewers, giftedSubs, channelPoints, newFollowers, clipsShared };
    }

    randomInt(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }

    randomBetween(min, max) {
        return Math.random() * (max - min) + min;
    }

    scheduleAutoRefresh() {
        this.clearAutoRefresh();
        if (!Number.isFinite(this.autoRefreshMs) || this.autoRefreshMs <= 0) return;
        this.autoRefreshTimer = setInterval(() => this.refreshStats({ animate: false, reason: 'auto' }), this.autoRefreshMs);
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

export default ChatStatistics;
