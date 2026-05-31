const endpoint = '/get_teamspeak_user_map';
const pollInterval = 2000; // Polls every 2 seconds

async function fetchUserMap() {
    try {
        const response = await fetch(endpoint);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const users = await response.json();
        renderUsers(users);
    } catch (error) {
        console.error("Failed to fetch TeamSpeak data:", error);
        document.getElementById('userList').innerHTML = `
            <div class="empty-state" style="color: var(--color-muted);">
                Failed to load users. Retrying...
            </div>`;
    }
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