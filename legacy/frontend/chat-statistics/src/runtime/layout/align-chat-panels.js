// Aligns the stream chat dock with the chat statistics card bottom edge.
(function alignChatPanels() {
    const mainContent = document.querySelector('.main-content');
    const chatDock = document.querySelector('.chat-dock');
    const statsRoot = document.getElementById('chat-statistics-root');

    if (!mainContent || !chatDock || !statsRoot) return;

    const getStatsCard = () => statsRoot.querySelector('.chat-statistics');
    let rafId = null;

    const applyAlignment = () => {
        rafId = null;
        const statsCard = getStatsCard();
        if (!statsCard) return;

        const mainRect = mainContent.getBoundingClientRect();
        const statsRect = statsCard.getBoundingClientRect();

        // Offset between stats bottom and main content bottom (cannot be negative)
        const offset = Math.max(0, Math.round(mainRect.bottom - statsRect.bottom));
        chatDock.style.bottom = `${offset}px`;
    };

    const scheduleAlignment = () => {
        if (rafId !== null) return;
        rafId = requestAnimationFrame(applyAlignment);
    };

    window.addEventListener('resize', scheduleAlignment);
    window.addEventListener('orientationchange', scheduleAlignment);
    statsRoot.addEventListener('chat-statistics:refresh', scheduleAlignment);

    const observer = new MutationObserver(scheduleAlignment);
    observer.observe(statsRoot, { childList: true, subtree: true });

    scheduleAlignment();
})();
