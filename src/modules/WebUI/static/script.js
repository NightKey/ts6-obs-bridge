// Helper function to handle fetch requests safely
async function apiFetch(endpoint, options = {}) {
    const response = await fetch(`${endpoint}`, options);
    if (!response.ok) {
        var errorMessage = response.statusText;
        if (response.status === 500) {
            var errorMessage = await response.text();

            const parser = new DOMParser();
            const doc = parser.parseFromString(errorMessage, 'text/html');

            var errorMessage = doc.body.lastChild.data;
        }
        showError(errorMessage, `API Error on [${endpoint}]`);
        return null;
    }
    return await response.json();
}

// Function to dynamically update the UI connection status markers
function updateStatusMarker(elementId, isConnected) {
    const marker = document.getElementById(elementId);
    if (!marker) return;

    const textSpan = marker.querySelector('.status-text');

    // Clean out all temporary states
    marker.classList.remove('status-disconnected', 'status-connected', 'status-connecting');

    if (isConnected) {
        marker.classList.add('status-connected');
        if (textSpan) textSpan.textContent = 'Connected';
        if (elementId === "ts_status") {
            document.getElementById('btnConnectTS').disabled = true;
        } else {
            document.getElementById('btnConnectOBS').disabled = true;
        }
    } else {
        marker.classList.add('status-disconnected');
        if (textSpan) textSpan.textContent = 'Disconnected';
        if (elementId === "ts_status") {
            document.getElementById('btnConnectTS').disabled = false;
        } else {
            document.getElementById('btnConnectOBS').disabled = false;
        }
    }
}

// 1. On load: Fetch existing settings and populate the form
async function loadSettings() {
    const data = await apiFetch('get_settings');
    if (!data) return;

    const fields = [
        'teamspeak_ip', 'teamspeak_port', 'teamspeak_api',
        'obs_ip', 'obs_port', 'obs_password', 'obs_scene'
    ];

    fields.forEach(fieldId => {
        const input = document.getElementById(fieldId);
        if (input && data[fieldId] !== undefined) {
            input.value = data[fieldId];
        }
    });

    // Load in the auto-connect value at the start
    const autoconnectInput = document.getElementById('autoconnect');
    if (autoconnectInput && data.autoconnect !== undefined) {
        autoconnectInput.checked = !!data.autoconnect;
        toggleConnectButtons(!!data.autoconnect);
    }
}

// 2. Save Button Event: package inputs into JSON and POST to update_settings
async function saveSettings() {
    const btnSave = document.getElementById('btnSave');

    // Quick visual feedback disabling button during request
    if (btnSave) btnSave.disabled = true;

    const payload = {
        teamspeak_ip: document.getElementById('teamspeak_ip').value || document.getElementById('teamspeak_ip').placeholder,
        teamspeak_port: parseInt(document.getElementById('teamspeak_port').value || document.getElementById('teamspeak_port').placeholder, 10),
        teamspeak_api: document.getElementById('teamspeak_api').value,
        obs_ip: document.getElementById('obs_ip').value || document.getElementById('obs_ip').placeholder,
        obs_port: parseInt(document.getElementById('obs_port').value || document.getElementById('obs_port').placeholder, 10),
        obs_password: document.getElementById('obs_password').value,
        obs_scene: document.getElementById('obs_scene').value,
        autoconnect: document.getElementById('autoconnect').checked
    };

    const response = await apiFetch('update_settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    });

    if (response) {
        alert('Settings saved successfully!');
        await loadSettings();
    } else {
        alert('Failed to save settings.');
    }

    if (btnSave) btnSave.disabled = false;
}

// 3. Periodic update: check state of connections every 3 seconds
var delay_count = 0;
var last_teamspeak_status = false;
var last_obs_status = false;
async function checkConnectionState() {
    const state = await apiFetch('get_state');
    if (!state) return;

    // Checks key cases exactly matching your specs: "teamspeak_connected" and "OBS_connected"
    if (state.hasOwnProperty('teamspeak_connected')) {
        if (delay_count === 0 || last_teamspeak_status != state.teamspeak_connected) {
            last_teamspeak_status = state.teamspeak_connected;
            updateStatusMarker('ts_status', state.teamspeak_connected);
            if (state.teamspeak_connected && document.getElementById("teamspeak_api").value == "") {
                await loadSettings();
            }
        }
    }
    if (state.hasOwnProperty('OBS_connected')) {
        if (delay_count === 0 || last_obs_status != state.OBS_connected) {
            last_obs_status = state.OBS_connected;
            updateStatusMarker('obs_status', state.OBS_connected);
        }
    }
    if (delay_count > 0) {
        delay_count --;
    }
}

async function toggleAutoConnect() {
    const toggle = document.getElementById('autoconnect');

    if (!toggle) return;

    await apiFetch('toggle_autoconnect', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ "value": toggle.checked })
    });

    toggleConnectButtons(toggle.checked);
    if (toggle.checked) {
        setMarkerToConnecting('ts_status');
        setMarkerToConnecting('obs_status');
        delay_count = 3;
        warnTemaSpeak();
    }
}

// Toggle button visibilities depending on autoconnect state
function toggleConnectButtons(isAutoConnect) {
    const btnAll = document.getElementById('btnConnectAll');
    const btnTS = document.getElementById('btnConnectTS');
    const btnOBS = document.getElementById('btnConnectOBS');

    if (!btnAll || !btnTS || !btnOBS) return;

    if (isAutoConnect) {
        btnAll.style.display = 'block';
        btnTS.style.display = 'none';
        btnOBS.style.display = 'none';
    } else {
        btnAll.style.display = 'none';
        btnTS.style.display = 'block';
        btnOBS.style.display = 'block';
    }
}

function setMarkerToConnecting(elementId, isDisconnecting=false) {
    const marker = document.getElementById(elementId);
    if (!marker) return;

    const textSpan = marker.querySelector('.status-text');
    marker.classList.remove('status-disconnected', 'status-connected');
    marker.classList.add('status-connecting');
    if (textSpan) textSpan.textContent = isDisconnecting ? "Disconnecting..." : 'Connecting...';

    if (elementId === "ts_status") {
        document.getElementById('btnConnectTS').disabled = true;
    } else {
        document.getElementById('btnConnectOBS').disabled = true;
    }
}

// 4. Action button handlers for triggering connection flows
async function connectAllConnections() {
    const btn = document.getElementById('btnConnectAll');
    if (btn) btn.disabled = true;
    setMarkerToConnecting('ts_status');
    setMarkerToConnecting('obs_status');

    await apiFetch('connect_all');

    if (btn) btn.disabled = false;
    delay_count = 3;
    await checkConnectionState();
}

function warnTemaSpeak() {
    if (document.getElementById("teamspeak_api").value == "") {
        showError("Please authorize the application in TeamSpeak 6", "Warning", true);
    }
}

async function connectToTeamspeak() {
    warnTemaSpeak();

    const btn = document.getElementById('btnConnectTS');
    if (btn) btn.disabled = true;
    setMarkerToConnecting('ts_status');

    await apiFetch('connect_teamspeak');

    if (btn) btn.disabled = false;
    delay_count = 3;
    await checkConnectionState();
}

async function connectToOBS() {
    const btn = document.getElementById('btnConnectOBS');
    if (btn) btn.disabled = true;
    setMarkerToConnecting('obs_status');

    await apiFetch('connect_obs');

    if (btn) btn.disabled = false;
    delay_count = 3;
    await checkConnectionState();
}

// Optional helper for the Stop All action
async function stopAllConnections() {
    const btn = document.getElementById('btnStop');
    if (btn) btn.disabled = true;

    // Set both to connecting/waiting visual patterns while closing
    setMarkerToConnecting('ts_status', true);
    setMarkerToConnecting('obs_status', true);

    await apiFetch("stop_all");

    if (btn) btn.disabled = false;
    delay_count = 3;
    await checkConnectionState();
}

function showError(message, title, temporary=false) {
    const popup = document.getElementById('errorPopup');
    const msgTitle = document.getElementById('errorPopupTitle');
    const msgElement = document.getElementById('errorMessage');

    if (!popup || !msgElement || !msgTitle) return;

    msgTitle.textContent = title;
    msgElement.textContent = message;

    popup.classList.add('show');

    // Auto-dismiss after 10 seconds (optional)
    if (temporary) {
        setTimeout(() => {
            popup.classList.remove('show');
        }, 10000);
    }
}

function openTeamspeakDiagnostics() {
    window.open("/teamspeak");
}

function openObsDiagnostics() {
    window.open("/obs");
}

// Initialization and Event Listeners linking everything once the document loaded
document.addEventListener('DOMContentLoaded', () => {
    // Populate form data on entry
    loadSettings();

    // Setup initial connection state check, then run every 3000ms (3 seconds)
    checkConnectionState();
    setInterval(checkConnectionState, 3000);

    // Bind event listeners to DOM buttons using specified IDs
    document.getElementById('btnSave')?.addEventListener('click', saveSettings);
    document.getElementById('btnConnectAll')?.addEventListener('click', connectAllConnections);
    document.getElementById('ts_status')?.addEventListener('click', openTeamspeakDiagnostics);
    document.getElementById('obs_status')?.addEventListener('click', openObsDiagnostics);
    document.getElementById('btnConnectTS')?.addEventListener('click', connectToTeamspeak);
    document.getElementById('btnConnectOBS')?.addEventListener('click', connectToOBS);
    document.getElementById('btnStop')?.addEventListener('click', stopAllConnections);
    document.getElementById('btnCloseError')?.addEventListener('click', () => {
        document.getElementById('errorPopup').classList.remove('show');
    });
    document.getElementById('autoconnect')?.addEventListener('change', toggleAutoConnect);
});