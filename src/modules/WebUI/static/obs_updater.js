const scenes = '/obs_scenes';
const reinitEndpoint = '/reinit_obs';
const currentGroup = "/current_group"
const groups = '/groups';
const group = "/group";
const pollInterval = 500;
let currentSelectedGroup = "default";

async function apiFetch(url, params = {}, doThrow = true) {
    const response = await fetch(url, params);
    if (!response.ok) {
        console.error(`api fetch failed on ${url} with status ${response.status}`);
        if (doThrow) throw response;
        else return null;
    }

    // Unpack the new response object layout
    return await response.json();
}

async function fetchObsData() {
    try {
        const data = await apiFetch(scenes);

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

async function fetchGroups() {
    try {
        const selector = document.getElementById('group-select');
        if (!selector) return;
        selector.innerHTML = '';
        const selectedGroup = await apiFetch(currentGroup);
        currentSelectedGroup = selectedGroup.group;
        const data = await apiFetch(groups);
        data.forEach((group) => {
            const element = document.createElement("option");
            element.value = group;
            element.innerText = group;
            element.selected = currentSelectedGroup === group;
            selector.appendChild(element);
        });
    } catch (error) {
        console.error("Failed to fetch OBS groups:", error);
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
                        return `<span class="source-tag" ${sourceStyle}>${escapeHTML(source.name)}${hasBlinking ? '︶' : ''}</span> ${sourceItems}`;
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
                ${scene.blinking ? '<span class="status-badge">👁️</span>': ''}
                <span class="status-badge">${badgeText}</span>
                <span class="${currentSelectedGroup !== scene.group ? ' crossed-out' : ''}">
                    <svg class="icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                        <path fill="currentColor" d="M5.75 2a.75.75 0 0 0-.75.75v11.5c0 1.24 1 2.25 2.25 2.25H9.5v3a2.5 2.5 0 1 0 5 0v-3h2.25c1.24 0 2.25-1 2.25-2.25V2.75a.75.75 0 0 0-.75-.75zm.75 9V3.5h6v1.75a.75.75 0 1 0 1.5 0V3.5h1v2.75a.75.75 0 1 0 1.5 0V3.5h1V11zm0 3.25V12.5h11v1.75c0 .41-.34.75-.75.75h-3a.75.75 0 0 0-.75.75v3.75a1 1 0 0 1-2 0v-3.75a.75.75 0 0 0-.75-.75h-3a.75.75 0 0 1-.75-.75"/>
                    </svg>
                </span>
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

        const result = await apiFetch(reinitEndpoint, { method: 'POST' }, false);
        if (result === null) return;

        // Immediately update data loop seamlessly for the user
        await fetchObsData();
        await fetchGroups();
    } catch (error) {
        console.error("Failed to reinitialize OBS backend:", error);
    } finally {
        // Restore interactive state
        reinitBtn.disabled = false;
        reinitBtn.classList.remove('spinning');
    }
}

async function setGroup() {
    const element = document.getElementById('group-select');
    try {
        await apiFetch(group, { method: 'POST', body: JSON.stringify({'value': element.value }) });
    } catch (e) {
        console.error(`Failed to set group to ${element.value}`, e.message);
    } finally {
        setTimeout(fetchGroups, 500);
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
    document.getElementById("group-select")?.addEventListener('change', setGroup);
});

// Kickstart processing loop orchestration
fetchGroups().then();
fetchObsData().then();
setInterval(fetchObsData, pollInterval);
