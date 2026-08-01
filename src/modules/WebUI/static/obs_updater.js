const endpoint = '/get_obs_scenes';
const reinitEndpoint = '/reinit_obs'
const pollInterval = 500;

async function fetchObsData() {
    try {
        const response = await fetch(endpoint);
        if (!response.ok) {
            throw response;
        }

        // Unpack the new response object layout
        const data = await response.json();

        updateMessageQueue(data.message_queue);
        setSyncIndicator(data.connected);
        renderScenes(data.scenes);
    } catch (response) {
        console.error("Failed to fetch OBS data:", response.status);
        setSyncIndicator(false);
        const syncIndicator = document.getElementById('live-indicator');
        syncIndicator.classList.remove("connected", "disconnected")
        syncIndicator.classList.add("failed")
        let message = "Failed to load OBS scenes. Retrying..."
        if (response.status === 503) {
            message = response.statusText
        }
        document.getElementById('sceneList').innerHTML = `
            <div class="empty-state">
                ${message}
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

function setSyncIndicator(connected) {
    const syncIndicator = document.getElementById('live-indicator');
    syncIndicator.classList.remove("connected", "disconnected", "failed");
    syncIndicator.classList.remove("connected");
    syncIndicator.classList.add(connected ? "connected" : "disconnected");
    syncIndicator.innerText = connected ? "connected" : "disconnected";
}

function renderScenes(scenes) {
    const listContainer = document.getElementById('sceneList');

    if (!scenes || scenes.length === 0) {
        listContainer.innerHTML = '<div class="empty-state">No scenes found in OBS profile</div>';
        return;
    }

    listContainer.innerHTML = scenes.map((scene, index) => {
        // Map native profile states to our namespaced theme variations
        let statusClass = scene.present ? 'status-present' : 'status-left';
        const badgeText = scene.present ? 'Present' : 'Inactive';

        // Incremental numbering string inside the avatar container
        const marker = String(index + 1).padStart(2, '0');

        // Loop down and render internal scene elements securely
        const sourcesHTML = (scene.all && scene.all.length > 0)
            ? `<div class="scene-sources">
                    ${scene.all.map(source => {
                        let hasBlinking = false;
                        let enabledOverride = false;
                        const sourceItems = source.subItems.map(subItem => {
                            if (subItem.name === "blinking") {
                                hasBlinking = true;
                                enabledOverride = subItem.enabled;
                            } else {
                                const subItemStyle = subItem.enabled
                                    ? ''
                                    : 'style="opacity: 0.4; border-style: dashed;"';
                                return `<span class="source-tag" ${subItemStyle}>${escapeHTML(source.name)}-${escapeHTML(subItem.name)}</span>`;
                            }
                        }).join('');
                        const sourceStyle = source.enabled || enabledOverride
                            ? ''
                            : 'style="opacity: 0.4; border-style: dashed;"';
                        if (source.enabled && source.name === "muted") {
                            statusClass = "status-muted";
                        }
                        return `<span class="source-tag" ${sourceStyle}>${escapeHTML(source.name)}${hasBlinking ? ' ︶' : ''}</span> ${sourceItems}`;
                    }).join('')}
                </div>`
            : '<div class="scene-sources"><span class="source-tag" style="font-style: italic;">No sources</span></div>';

        return `
            <li class="user-item ${statusClass}">
                <div class="user-info" style="width: 75%;">
                    <div class="avatar">
                        <span class="user-name">${escapeHTML(scene.name)}</span>
                    </div>
                    <div class="user-details">
                        ${sourcesHTML}
                    </div>
                </div>
                ${scene.blinking ? '<span class="status-badge">👁</span>': ''}
                <span class="status-badge">${badgeText}</span>
            </li>
        `;
    }).join('');
}

async function reinitializeObs() {
    const reinitBtn = document.getElementById('refreshObsBtn');
    if (!reinitBtn) return;

    try {
        // Optimistically disable UI interaction during transition
        reinitBtn.disabled = true;
        reinitBtn.classList.add('spinning');

        const response = await fetch(reinitEndpoint, { method: 'POST' }); // Adjust to method: 'GET' if required by backend

        if (!response.ok) {
            throw new Error(`Reinit failed with status: ${response.status}`);
        }

        // Immediately update data loop seamlessly for the user
        await fetchObsData();
    } catch (error) {
        console.error("Failed to reinitialize OBS backend:", error);
    } finally {
        // Restore interactive state
        reinitBtn.disabled = false;
        reinitBtn.classList.remove('spinning');
    }
}

// XSS mitigation handling for source text nodes coming out of the API layer
function escapeHTML(str) {
    return String(str).replace(/&/g, '&amp;')
                      .replace(/</g, '&lt;')
                      .replace(/>/g, '&gt;')
                      .replace(/"/g, '&quot;');
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('refreshObsBtn')?.addEventListener('click', reinitializeObs);
});

// Kickstart processing loop orchestration
fetchObsData();
setInterval(fetchObsData, pollInterval);