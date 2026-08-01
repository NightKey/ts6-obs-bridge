const endpoint = '/get_teamspeak_user_map';
const pollInterval = 2000; // Polls every 2 seconds

async function fetchUserMap() {
    try {
        const response = await fetch(endpoint);
        if (!response.ok) {
            throw response;
        }
        const result = await response.json();
        setSyncIndicator(result.connected);
        renderUsers(result.users);
    } catch (response) {
        console.error("Failed to fetch TeamSpeak data:", response.status);
        setSyncIndicator(false);
        const syncIndicator = document.getElementById('live-indicator');
        syncIndicator.classList.remove("connected", "disconnected")
        syncIndicator.classList.add("failed")
        let message = "Failed to load TeamSpeak connections. Retrying..."
        if (response.status === 503) {
            message = response.statusText
        }
        document.getElementById('userList').innerHTML = `
            <div class="empty-state">
                ${message}
            </div>`;
    }
}

function setSyncIndicator(connected) {
    const syncIndicator = document.getElementById('live-indicator');
    syncIndicator.classList.remove("connected", "disconnected", "failed");
    syncIndicator.classList.remove("connected");
    syncIndicator.classList.add(connected ? "connected" : "disconnected");
    syncIndicator.innerText = connected ? "connected" : "disconnected";
}

function renderUsers(users) {
    const listContainer = document.getElementById('userList');

    if (!users || users.length === 0) {
        listContainer.innerHTML = '<div class="empty-state">Channel is empty</div>';
        return;
    }

    // Map server statuses to clean CSS classes
    const statusClassMap = {
        'Quiet': 'status-quiet',
        'Speaking': 'status-speaking',
        'Muted': 'status-muted',
        'Left': 'status-left'
    };

    // Build structural list components safely using map/join strings
    listContainer.innerHTML = users.map(user => {
        const statusClass = statusClassMap[user.status] || 'status-quiet';
        const initials = user.name ? user.name.substring(0, 2).toUpperCase() : '??';

        return `
            <li class="user-item ${statusClass}" data-id="${user.id}">
                <div class="user-info">
                    <div class="avatar">${initials}</div>
                    <div class="user-details">
                        <span class="user-name">${escapeHTML(user.name)}</span>
                        <span class="user-id">ID: ${user.id}</span>
                    </div>
                </div>
                <span class="status-badge">${escapeHTML(user.status)}</span>
            </li>
        `;
    }).join('');
}

// Simple helper to prevent XSS injection issues from arbitrary usernames
function escapeHTML(str) {
    return String(str).replace(/&/g, '&amp;')
                      .replace(/</g, '&lt;')
                      .replace(/>/g, '&gt;')
                      .replace(/"/g, '&quot;');
}

// Initialize execution loop once script handles parse initialization
fetchUserMap();
setInterval(fetchUserMap, pollInterval);