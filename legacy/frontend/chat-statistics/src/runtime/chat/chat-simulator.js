// src/runtime/chat/chat-simulator.js
const list = document.getElementById('chat-list');
const newBtn = document.getElementById('chat-new');

if (list) {
    const maxKeep = 300;
    const rng = (a, b) => a + Math.random() * (b - a);
    const pick = (arr) => arr[(Math.random() * arr.length) | 0];
    const atBottom = () => (list.scrollTop + list.clientHeight >= list.scrollHeight - 8);

    const users = [
        'cjcraven11', 'rainingharries', 'leviShinpo', 'Samskio', 'noice_cook', 'LeLo_0X',
        'patient_zero0o', 'ahmadbaixc4', 'VORMSTERKING', 'qamrm', 'controlerplaer3',
        'tarokoala', 'anthonyny0', 'sukirulol', 'lil_Normie', 'arky', 'silky', 'ayyokoko',
        'happyPro', 'sneakyy', 'xeno', 'kaizok', 'peachtea', 'nixie', 'alina', 'qwertycat'
    ];

    const words = "lol lmao pog omg bro bruh nah fr ong cap based w w w spam ez insane wild rt cry mf sheesh ayo giga clutch peak cringe gigaW".split(' ');
    const templates = [
        '{{u}}: {{m}}',
        '{{u}}: {{m}} {{m}}',
        '{{u}}: {{m}} {{emote}}',
        '{{u}}: {{m}} {{m}} {{emote}}',
        '{{u}}: you gotta {{m}} the {{m}}',
        '{{u}}: say my name',
    ];

    const badgePool = [
        { key: 'sub', label: '🎖️' },
        { key: 'prime', label: '👑' },
        { key: 'gift', label: '🎁' },
        { key: 'mod', label: '🛡️' }
    ];

    const colorFromName = (name) => {
        let h = 0;
        for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
        const hue = h % 360;
        return `hsl(${hue} 80% 70%)`;
    };

    const makeLine = (display, msg, badges = []) => {
        const li = document.createElement('li');
        li.className = 'chat-line';

        const badgeWrap = document.createElement('span');
        badgeWrap.className = 'badges';
        for (const b of badges) {
            const span = document.createElement('span');
            span.className = 'badge';
            if (b.key === 'months') span.classList.add('badge--num');
            span.textContent = b.label;
            badgeWrap.appendChild(span);
        }

        const userEl = document.createElement('span');
        userEl.className = 'user';
        userEl.style.color = colorFromName(display);
        userEl.textContent = display;

        const sep = document.createElement('span');
        sep.className = 'sep';
        sep.textContent = ':';

        const msgEl = document.createElement('span');
        msgEl.className = 'msg';
        // very tiny emote parser: replace :emote: with a pill
        msgEl.innerHTML = msg.replace(/:emote:/g, '<i class="emote"></i>');

        li.appendChild(badgeWrap);
        li.appendChild(userEl);
        li.appendChild(sep);
        li.appendChild(msgEl);
        return li;
    };

    const compose = () => {
        const name = pick(users);
        const badges = [];
        const monthsPool = [1, 2, 3, 6, 12, 24, 36];

        if (Math.random() < 0.25) badges.push(pick(badgePool));
        if (Math.random() < 0.10) badges.push({ key: 'months', label: String(pick(monthsPool)), kind: 'num' });

        const tpl = pick(templates);
        const em = Math.random() < 0.35 ? ':emote:' : '';
        const m1 = pick(words).toUpperCase();
        const m2 = pick(words).toUpperCase();
        const msg = tpl
            .replace('{{u}}', name)
            .replace('{{m}}', m1)
            .replace('{{m}}', m2)    // second {{m}}
            .replace('{{emote}}', em);

        return makeLine(name, msg, badges);
    };

    const pushLine = () => {
        const stick = atBottom();
        const frag = document.createDocumentFragment();
        frag.appendChild(compose());
        list.appendChild(frag);

        while (list.children.length > maxKeep) list.removeChild(list.firstChild);

        if (stick) {
            list.scrollTop = list.scrollHeight;
            if (newBtn) newBtn.classList.remove('is-visible'), newBtn.hidden = true;
        } else {
            if (newBtn) newBtn.hidden = false, newBtn.classList.add('is-visible');
        }
    };

    // bursty arrival process
    const loop = () => {
        const base = 450;                 // base ms
        const burstChance = 0.18;
        const k = Math.random() < burstChance ? 0.35 : 1;
        const delay = rng(base * 0.6 * k, base * 1.5 * k);
        pushLine(); 
        setTimeout(loop, delay);
    };

    // pause autoscroll when user scrolls up
    list.addEventListener('scroll', () => {
        if (!newBtn) return;
        if (atBottom()) newBtn.classList.remove('is-visible'), newBtn.hidden = true;
    });
    if (newBtn) {
        newBtn.addEventListener('click', () => {
            list.scrollTop = list.scrollHeight;
            newBtn.classList.remove('is-visible');
            newBtn.hidden = true;
        });
    }

    // start
    setTimeout(loop, 600);
}
