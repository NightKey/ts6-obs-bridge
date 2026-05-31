const endpoint = '/get_obs_scenes';
const pollInterval = 2000; // Polls every 2 seconds

async function fetchObsData() {
    try {
        const response = await fetch(endpoint);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Unpack the new response object layout
        const data = await response.json();

        updateMessageQueue(data.message_queue);
        renderScenes(data.scenes);
    } catch (error) {
        console.error("Failed to fetch OBS data:", error);
        document.getElementById('sceneList').innerHTML = `
            <div class="empty-state" style="color: var(--status-red);">
                Failed to load OBS scenes. Retrying...
            </div>`;
    }
}

function updateMessageQueue(count) {
    const queueElement = document.getElementById('queueCounter');
    if (!queueElement) return;

    // Direct structural normalization fallback
    const queueVal = parseInt(count, 10) || 0;
    queueElement.textContent = queueVal;

    // Threshold coloring rules logic: Red if > 5, otherwise Green
    if (queueVal > 5) {
        queueElement.classList.remove('queue-normal');
        queueElement.classList.add('queue-warning');
    } else {
        queueElement.classList.remove('queue-warning');
        queueElement.classList.add('queue-normal');
    }
}

function renderScenes(scenes) {
    const listContainer = document.getElementById('sceneList');

    if (!scenes || scenes.length === 0) {
        listContainer.innerHTML = '<div class="empty-state">No scenes found in OBS profile</div>';
        return;
    }

    listContainer.innerHTML = scenes.map((scene, index) => {
        // Map native profile states to our namespaced theme variations
        const statusClass = scene.present ? 'status-speaking' : 'status-quiet';
        const badgeText = scene.present ? 'Live' : 'Inactive';

        // Incremental numbering string inside the avatar container
        const marker = String(index + 1).padStart(2, '0');

        // Loop down and render internal scene elements securely
        const sourcesHTML = (scene.all && scene.all.length > 0)
            ? `<div class="scene-sources">
                ${scene.all.map(source => `<span class="source-tag">${escapeHTML(source)}</span>`).join('')}
               </div>`
            : '<div class="scene-sources"><span class="source-tag" style="font-style: italic;">No sources</span></div>';

        return `
            <li class="user-item ${statusClass}">
                <div class="user-info" style="width: 75%;">
                    <div class="avatar">${marker}</div>
                    <div class="user-details">
                        <span class="user-name">${escapeHTML(scene.name)}</span>
                        ${sourcesHTML}
                    </div>
                </div>
                <span class="status-badge">${badgeText}</span>
            </li>
        `;
    }).join('');
}

// XSS mitigation handling for source text nodes coming out of the API layer
function escapeHTML(str) {
    return String(str).replace(/&/g, '&amp;')
                      .replace(/</g, '&lt;')
                      .replace(/>/g, '&gt;')
                      .replace(/"/g, '&quot;');
}

// Kickstart processing loop orchestration
fetchObsData();
setInterval(fetchObsData, pollInterval);