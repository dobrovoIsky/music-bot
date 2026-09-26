// ====== DOM Elements ======
const $ = id => document.getElementById(id);

const els = {
    statusBadge: $('status-badge'),
    statusText: $('status-text'),
    usersCount: $('users-count'),
    songsCount: $('songs-count'),
    toggleBtn: $('toggle-accepting'),
    trackDisplay: $('track-display'),
    trackTitle: $('track-title'),
    trackArtist: $('track-artist'),
    trackCover: $('track-cover'),
    trackCoverPlaceholder: $('track-cover-placeholder'),
    queueList: $('queue-list'),
    queueCount: $('queue-count'),
    btnNext: $('btn-next'),
    btnClear: $('btn-clear'),
    startOverlay: $('start-overlay'),
    ytWrapper: $('youtube-player-wrapper'),
    wakeLockToggle: $('wake-lock-toggle')
};

// A normal YouTube URL opens the installed app when the device is configured for it.
const openYouTube = document.createElement('a');
openYouTube.className = 'ctrl-btn';
openYouTube.textContent = '▶ Відкрити в YouTube';
openYouTube.target = '_blank';
openYouTube.rel = 'noopener noreferrer';
openYouTube.style.textDecoration = 'none';
openYouTube.style.display = 'none';
document.querySelector('.player-controls').append(openYouTube);
openYouTube.addEventListener('click', () => {
    if (isPlayerReady && playbackStarted) player.pauseVideo();
});

// ====== State ======
let lastData = null;
let currentYTId = null;
let player = null;
let isPlayerReady = false;
let playbackStarted = false;
let wakeLock = null;
let latestQueue = null;

// ====== Wake Lock (keep screen on) ======
async function requestWakeLock() {
    if (!('wakeLock' in navigator)) return;
    try {
        wakeLock = await navigator.wakeLock.request('screen');
        wakeLock.addEventListener('release', () => { wakeLock = null; });
    } catch (e) { /* silently fail */ }
}

async function releaseWakeLock() {
    if (wakeLock) {
        await wakeLock.release();
        wakeLock = null;
    }
}

els.wakeLockToggle.addEventListener('change', (e) => {
    if (e.target.checked) requestWakeLock();
    else releaseWakeLock();
});

// Request on load
requestWakeLock();

// Re-request on visibility change (wake lock gets released when tab is hidden)
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && els.wakeLockToggle.checked) {
        requestWakeLock();
    }
});

// ====== YouTube Player ======
window.onYouTubeIframeAPIReady = function() {
    player = new YT.Player('youtube-player', {
        height: '100%',
        width: '100%',
        playerVars: {
            autoplay: 0,
            controls: 1,
            rel: 0,
            modestbranding: 1,
            playsinline: 1
        },
        events: {
            onReady: () => {
                isPlayerReady = true;
                syncPlayback();
            },
            onStateChange: onPlayerStateChange,
            onError: (event) => {
                const details = {
                    2: 'Некоректний ID відео.',
                    5: 'Це відео не підтримує відтворення в браузері.',
                    100: 'Відео видалене або приватне.',
                    101: 'Автор заборонив відтворення на інших сайтах.',
                    150: 'Автор заборонив відтворення на інших сайтах.',
                    153: 'YouTube не отримав дані про сайт. Перевірте налаштування Referer.'
                };
                els.trackArtist.textContent = `Помилка YouTube ${event.data}: ${details[event.data] || 'Не вдалося відтворити відео.'}`;
                console.error('YouTube player error:', event.data);
            }
        }
    });
};

function syncPlayback() {
    if (!isPlayerReady || !playbackStarted || !latestQueue) return;
    const videoId = latestQueue.playing?.song.youtube_id;
    if (videoId && videoId !== currentYTId) {
        player.loadVideoById(videoId);
        currentYTId = videoId;
    } else if (!videoId && currentYTId) {
        player.stopVideo();
        currentYTId = null;
    }
}

function onPlayerStateChange(event) {
    // YT.PlayerState.ENDED === 0
    if (event.data === 0 && playbackStarted) {
        // Song ended, auto-skip to next
        apiCall('/api/next');
    }
}

// ====== Start Playback ======
els.startOverlay.addEventListener('click', async () => {
    playbackStarted = true;
    els.startOverlay.classList.add('hidden');
    els.ytWrapper.classList.remove('hidden');

    // Resume the current track; advance only when nothing is playing yet.
    await fetchQueue();
    if (!latestQueue?.playing && latestQueue?.queue?.length) {
        await apiCall('/api/next');
    }
    syncPlayback();
});

// ====== API ======
async function apiCall(endpoint) {
    try {
        const res = await fetch(endpoint, { method: 'POST' });
        if (res.ok) await fetchQueue();
    } catch (e) {
        console.error('API Error:', e);
    }
}

async function fetchQueue() {
    try {
        const res = await fetch('/api/queue');
        if (!res.ok) throw new Error();
        const data = await res.json();
        latestQueue = data;
        
        const str = JSON.stringify(data);
        if (str !== lastData) {
            updateUI(data);
            lastData = str;
        }
        syncPlayback();

        els.statusBadge.classList.remove('offline');
        els.statusText.textContent = 'Онлайн';
    } catch (e) {
        els.statusBadge.classList.add('offline');
        els.statusText.textContent = 'Офлайн';
    }
}

// ====== UI Update ======
function updateUI(data) {
    // Stats
    els.usersCount.textContent = data.total_users;
    els.songsCount.textContent = data.total_songs;

    // Toggle accepting
    const toggleText = els.toggleBtn.querySelector('.toggle-text');
    if (data.accepting) {
        els.toggleBtn.classList.remove('paused');
        els.toggleBtn.classList.add('accepting');
        toggleText.textContent = 'Прийом увімк.';
    } else {
        els.toggleBtn.classList.remove('accepting');
        els.toggleBtn.classList.add('paused');
        toggleText.textContent = 'Прийом вимк.';
    }

    // Now Playing
    if (data.playing) {
        const s = data.playing.song;
        if (/^[\w-]{11}$/.test(s.youtube_id || '')) {
            openYouTube.href = `https://www.youtube.com/watch?v=${s.youtube_id}`;
            openYouTube.style.display = '';
        } else {
            openYouTube.removeAttribute('href');
            openYouTube.style.display = 'none';
        }
        els.trackTitle.textContent = s.title;
        els.trackArtist.textContent = s.artist;

        if (s.cover_url) {
            els.trackCover.src = s.cover_url;
            els.trackCover.classList.remove('hidden');
            els.trackCoverPlaceholder.classList.add('hidden');
        } else {
            els.trackCover.classList.add('hidden');
            els.trackCoverPlaceholder.classList.remove('hidden');
        }

    } else {
        openYouTube.removeAttribute('href');
        openYouTube.style.display = 'none';
        els.trackTitle.textContent = 'Очікування...';
        els.trackArtist.textContent = 'Додайте пісню через бота';
        els.trackCover.classList.add('hidden');
        els.trackCoverPlaceholder.classList.remove('hidden');
        
    }

    // Queue
    const queueItems = data.queue || [];
    const countLabel = queueItems.length === 1 ? '1 трек' : `${queueItems.length} треків`;
    els.queueCount.textContent = countLabel;

    if (queueItems.length > 0) {
        els.queueList.innerHTML = queueItems.map((item, i) => {
            const cover = item.song.cover_url
                ? `<img src="${item.song.cover_url}" class="queue-cover" alt="">`
                : `<div class="queue-cover-placeholder"></div>`;
            return `
                <div class="queue-item">
                    <span class="queue-idx">${i + 1}</span>
                    ${cover}
                    <div class="queue-info">
                        <div class="queue-title">${item.song.title}</div>
                        <div class="queue-artist">${item.song.artist}</div>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        els.queueList.innerHTML = `
            <div class="empty-state">
                <span class="empty-icon">🎶</span>
                <p>Черга порожня</p>
                <p class="empty-sub">Пасажири можуть додати пісні через Telegram-бота</p>
            </div>
        `;
    }
}

// ====== Event Listeners ======
els.btnNext.addEventListener('click', () => apiCall('/api/next'));
els.btnClear.addEventListener('click', () => {
    apiCall('/api/clear');
});
els.toggleBtn.addEventListener('click', () => apiCall('/api/toggle_accepting'));

// ====== Polling ======
setInterval(fetchQueue, 3000);
fetchQueue();
