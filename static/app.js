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

// ====== State ======
let lastData = null;
let currentYTId = null;
let player = null;
let isPlayerReady = false;
let playbackStarted = false;
let wakeLock = null;

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
            onReady: () => { isPlayerReady = true; },
            onStateChange: onPlayerStateChange
        }
    });
};

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

    // Trigger first song to play
    await apiCall('/api/next');
    // Fetch immediately to get the new PLAYING state
    await fetchQueue();
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
        
        const str = JSON.stringify(data);
        if (str !== lastData) {
            updateUI(data);
            lastData = str;
        }

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

        // Play in YouTube if new song
        if (s.youtube_id && s.youtube_id !== currentYTId) {
            currentYTId = s.youtube_id;
            if (isPlayerReady && playbackStarted) {
                player.loadVideoById(s.youtube_id);
            }
        }
    } else {
        els.trackTitle.textContent = 'Очікування...';
        els.trackArtist.textContent = 'Додайте пісню через бота';
        els.trackCover.classList.add('hidden');
        els.trackCoverPlaceholder.classList.remove('hidden');
        
        if (currentYTId) {
            currentYTId = null;
            if (isPlayerReady && playbackStarted) {
                player.stopVideo();
            }
        }
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
    if (isPlayerReady && playbackStarted) player.stopVideo();
    currentYTId = null;
});
els.toggleBtn.addEventListener('click', () => apiCall('/api/toggle_accepting'));

// ====== Polling ======
setInterval(fetchQueue, 3000);
fetchQueue();
