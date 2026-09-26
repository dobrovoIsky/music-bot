const elements = {
    systemStatus: document.getElementById('system-status'),
    statusText: document.getElementById('status-text'),
    usersCount: document.getElementById('users-count'),
    songsCount: document.getElementById('songs-count'),
    toggleAcceptingBtn: document.getElementById('toggle-accepting'),
    nowPlayingContent: document.getElementById('now-playing-content'),
    queueList: document.getElementById('queue-list'),
    btnNext: document.getElementById('btn-next'),
    btnClear: document.getElementById('btn-clear')
};

let lastQueueData = null;

// Fetch queue and update UI
async function fetchQueue() {
    try {
        const res = await fetch('/api/queue');
        if (!res.ok) throw new Error('API Error');
        const data = await res.json();
        
        // Prevent unnecessary DOM updates if data hasn't changed (basic stringify check)
        const currentDataStr = JSON.stringify(data);
        if (currentDataStr !== lastQueueData) {
            updateUI(data);
            lastQueueData = currentDataStr;
        }
        
        elements.systemStatus.classList.remove('stopped');
        elements.statusText.textContent = 'Система работает';
    } catch (err) {
        console.error('Failed to fetch queue:', err);
        elements.systemStatus.classList.add('stopped');
        elements.statusText.textContent = 'Ошибка подключения';
    }
}

function updateUI(data) {
    // Stats
    elements.usersCount.textContent = data.total_users;
    elements.songsCount.textContent = data.total_songs;
    
    // Toggle Button
    if (data.accepting) {
        elements.toggleAcceptingBtn.classList.remove('off');
        elements.toggleAcceptingBtn.textContent = 'ВЫКЛЮЧИТЬ ПРИЕМ';
    } else {
        elements.toggleAcceptingBtn.classList.add('off');
        elements.toggleAcceptingBtn.textContent = 'ВКЛЮЧИТЬ ПРИЕМ';
    }
    
    // Now Playing
    if (data.playing) {
        const cover = data.playing.song.cover_url 
            ? `<img src="${data.playing.song.cover_url.replace('100x100', '300x300')}" class="cover-art" alt="cover">`
            : `<div class="cover-placeholder"></div>`;
            
        elements.nowPlayingContent.innerHTML = `
            ${cover}
            <div class="track-info">
                <h3 class="title">${data.playing.song.title}</h3>
                <p class="artist">${data.playing.song.artist}</p>
            </div>
        `;
    } else {
        elements.nowPlayingContent.innerHTML = `
            <div class="cover-placeholder"></div>
            <div class="track-info">
                <h3 class="title">Ничего не играет</h3>
                <p class="artist">Очередь пуста</p>
            </div>
        `;
    }
    
    // Queue List
    if (data.queue && data.queue.length > 0) {
        elements.queueList.innerHTML = data.queue.map((item, index) => {
            const cover = item.song.cover_url 
                ? `<img src="${item.song.cover_url}" class="queue-track-cover" alt="cover">`
                : `<div class="queue-track-cover" style="background: rgba(255,255,255,0.1)"></div>`;
                
            return `
                <div class="queue-item">
                    <span class="queue-index">${index + 1}</span>
                    ${cover}
                    <div class="queue-track-info">
                        <div class="queue-track-title">${item.song.title}</div>
                        <div class="queue-track-artist">${item.song.artist}</div>
                    </div>
                </div>
            `;
        }).join('');
    } else {
        elements.queueList.innerHTML = `<p class="empty-state">Очередь пуста</p>`;
    }
}

// Controls API
async function apiCall(endpoint) {
    try {
        const res = await fetch(endpoint, { method: 'POST' });
        if (res.ok) {
            await fetchQueue(); // Immediate refresh
        }
    } catch (e) {
        console.error(e);
    }
}

// Event Listeners
elements.btnNext.addEventListener('click', () => apiCall('/api/next'));
elements.btnClear.addEventListener('click', () => apiCall('/api/clear'));
elements.toggleAcceptingBtn.addEventListener('click', () => apiCall('/api/toggle_accepting'));

// Poll every 3 seconds
setInterval(fetchQueue, 3000);
fetchQueue(); // Initial fetch
