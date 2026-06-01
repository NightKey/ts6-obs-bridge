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

    if (isConnected) {
        marker.classList.remove('status-disconnected');
        marker.classList.add('status-connected');
        if (textSpan) textSpan.textContent = 'Connected';
        if (elementId === "ts_status") {
            document.getElementById('btnConnectTS').disabled = true;
        } else {
            document.getElementById('btnConnectOBS').disabled = true;
        }
    } else {
        marker.classList.remove('status-connected');
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

    // Direct mapping of key-values to input fields by exact ID match
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
        obs_scene: document.getElementById('obs_scene').value
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
async function checkConnectionState() {
    const state = await apiFetch('get_state');
    if (!state) return;

    // Checks key cases exactly matching your specs: "teamspeak_connected" and "OBS_connected"
    if (state.hasOwnProperty('teamspeak_connected')) {
        updateStatusMarker('ts_status', state.teamspeak_connected);
        if (state.teamspeak_connected && document.getElementById("teamspeak_api").value == "") {
            await loadSettings();
        }
    }
    if (state.hasOwnProperty('OBS_connected')) {
        updateStatusMarker('obs_status', state.OBS_connected);
    }
}

// 4. Action button handlers for triggering connection flows
async function connectToTeamspeak() {
    if (document.getElementById("teamspeak_api").value == "") {
        showError("Please authorize the application in TeamSpeak 6", "Warning", true)
    }
    const response = await apiFetch('connect_teamspeak');
    if (response && response.hasOwnProperty('connected')) {
        updateStatusMarker('ts_status', response.connected);
    }
}

async function connectToOBS() {
    const response = await apiFetch('connect_obs');
    if (response && response.hasOwnProperty('connected')) {
        updateStatusMarker('obs_status', response.connected);
    }
}

// Optional helper for the Stop All action
async function stopAllConnections() {
    const response = await apiFetch("stop_all");
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
    document.getElementById('ts_status')?.addEventListener('click', openTeamspeakDiagnostics);
    document.getElementById('obs_status')?.addEventListener('click', openObsDiagnostics);
    document.getElementById('btnConnectTS')?.addEventListener('click', connectToTeamspeak);
    document.getElementById('btnConnectOBS')?.addEventListener('click', connectToOBS);
    document.getElementById('btnStop')?.addEventListener('click', stopAllConnections);
    document.getElementById('btnCloseError')?.addEventListener('click', () => {
        document.getElementById('errorPopup').classList.remove('show');
    });
});