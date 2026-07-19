// Helper function to handle fetch requests safely
async function apiFetch(endpoint, options = {}) {
    const response = await fetch(`${endpoint}`, options);
    if (!response.ok) {
        let errorMessage = response.statusText;
        if (response.status === 500) {
            errorMessage = await response.text();

            const parser = new DOMParser();
            const doc = parser.parseFromString(errorMessage, 'text/html');

            errorMessage = doc.body.lastChild.data;
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
        'obs_ip', 'obs_port', 'obs_password',
        'blink_time', 'low_blink_interval', 'high_blink_interval'
    ];

    let missingCount = 0
    fields.forEach(fieldId => {
        const input = document.getElementById(fieldId);
        if (data[fieldId] === null) {
            missingCount++;
        }
        if (input && data[fieldId] !== undefined && data[fieldId] !== null) {
            input.value = data[fieldId];
        } else if (input) {
            switch (fieldId) {
                case 'blink_time':
                    input.value = 150;
                    break;
                case 'low_blink_interval':
                    input.value = 1000;
                    break;
                case 'high_blink_interval':
                    input.value = 3000;
                    break;
                default: break;
            }
        }
    });

    if (missingCount > 2) {
        // No settings present!
        animateButtonToggleHide("ts_hide", "ts-form-grid");
        animateButtonToggleHide("obs_hide", "obs-form-grid");
        showError("No settings were present when starting the application!\nPlease save the settings!", "Missing settings", true)
    }

    // Handle range visualization sync after loading values
    updateSliderVisuals();

    // Load in the auto-connect value at the start
    const autoconnectInput = document.getElementById('autoconnect');
    if (autoconnectInput && data['autoconnect'] !== undefined) {
        autoconnectInput.checked = !!data['autoconnect'];
        toggleConnectButtons(!!data['autoconnect']);
    }

    // Load in 'blinking enabled' value
    const blinkingEnabledInput = document.getElementById('blinking_enabled');
    if (blinkingEnabledInput && data['blink_enabled'] !== undefined) {
        blinkingEnabledInput.checked = !!data['blink_enabled'];
        hideOrShowBlinkingSliders(!data['blink_enabled']);
    }
}

// Double slider handling & visualization rendering helper
function updateSliderVisuals() {
    const blinkTime = document.getElementById('blink_time');
    const lowInterval = document.getElementById('low_blink_interval');
    const highInterval = document.getElementById('high_blink_interval');
    const track = document.getElementById('rangeTrack');

    if (blinkTime) {
        // Output as milliseconds (e.g., "450ms") since the range is 10ms - 1000ms
        document.getElementById('blink_time_val').textContent = `${blinkTime.value}ms`;
    }

    if (lowInterval && highInterval && track) {
        const min = parseInt(lowInterval.min);
        const max = parseInt(lowInterval.max);
        const val1 = parseInt(lowInterval.value);
        const val2 = parseInt(highInterval.value);

        // Highlight portion calculation
        const percentLeft = ((val1 - min) / (max - min)) * 100;
        const percentRight = ((val2 - min) / (max - min)) * 100;

        track.style.background = `linear-gradient(to right, rgba(90, 101, 133, 0.4) ${percentLeft}%, var(--color-sec-dark) ${percentLeft}%, var(--color-sec-dark) ${percentRight}%, rgba(90, 101, 133, 0.4) ${percentRight}%)`;
        document.getElementById('blink_interval_val').textContent = `${(val1 / 1000).toFixed(1)}s - ${(val2 / 1000).toFixed(1)}s`;
    }
}

// Overlapping handler behavior configurations for range inputs
function initSliders() {
    const lowInput = document.getElementById('low_blink_interval');
    const highInput = document.getElementById('high_blink_interval');
    const blinkTimeInput = document.getElementById('blink_time');

    if (lowInput && highInput) {
        // Force the active slider's z-index hierarchy forward dynamically to prevent stuck overlaps
        lowInput.addEventListener('mousedown', () => lowInput.style.zIndex = '4');
        highInput.addEventListener('mousedown', () => highInput.style.zIndex = '4');
        lowInput.addEventListener('touchstart', () => lowInput.style.zIndex = '4');
        highInput.addEventListener('touchstart', () => highInput.style.zIndex = '4');

        lowInput.addEventListener('input', () => {
            lowInput.style.zIndex = '4';
            highInput.style.zIndex = '2';
            if (parseInt(lowInput.value) > parseInt(highInput.value) - 100) {
                lowInput.value = parseInt(highInput.value) - 100;
            }
            updateSliderVisuals();
        });

        highInput.addEventListener('input', () => {
            highInput.style.zIndex = '4';
            lowInput.style.zIndex = '2';
            if (parseInt(highInput.value) < parseInt(lowInput.value) + 100) {
                highInput.value = parseInt(lowInput.value) + 100;
            }
            updateSliderVisuals();
        });
    }

    if (blinkTimeInput) {
        blinkTimeInput.addEventListener('input', updateSliderVisuals);
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
        autoconnect: document.getElementById('autoconnect').checked,

        // Custom added slider payloads
        blink_time: parseInt(document.getElementById('blink_time').value, 10),
        low_blink_interval: parseInt(document.getElementById('low_blink_interval').value, 10),
        high_blink_interval: parseInt(document.getElementById('high_blink_interval').value, 10),

        // Save blinking enabled state
        "blinking enabled": document.getElementById('blinking_enabled').checked
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
let delay_count = 0;
let last_teamspeak_status = false;
let last_obs_status = false;
async function checkConnectionState() {
    const state = await apiFetch('get_state');
    if (!state) return;

    // Checks key cases exactly matching your specs: "teamspeak_connected" and "OBS_connected"
    if (state.hasOwnProperty('teamspeak_connected')) {
        if (delay_count === 0 || (last_teamspeak_status !== state.teamspeak_connected)) {
            last_teamspeak_status = state.teamspeak_connected;
            updateStatusMarker('ts_status', state.teamspeak_connected);
            if (state.teamspeak_connected && document.getElementById("teamspeak_api").value === "") {
                await loadSettings();
            }
        }
    }
    if (state.hasOwnProperty('OBS_connected')) {
        if (delay_count === 0 || last_obs_status !== state.OBS_connected) {
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

// Toggle blinking on demand endpoint caller
async function toggleBlinking() {
    const toggle = document.getElementById('blinking_enabled');
    if (!toggle) return;

    await apiFetch('set_blinking', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ "value": toggle.checked })
    });

    hideOrShowBlinkingSliders(!toggle.checked);
}

function hideOrShowBlinkingSliders(hide) {
    const singleSlider = document.getElementById("blinking-single-slider");
    const dualSlider = document.getElementById("blinking-dual-slider");
    if (!singleSlider || !dualSlider) return;

    if (hide) {
        singleSlider.classList.add("hidden");
        dualSlider.classList.add("hidden");
    } else {
        singleSlider.classList.remove("hidden");
        dualSlider.classList.remove("hidden");
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
    if (document.getElementById("teamspeak_api").value === "") {
        showError("Please authorize the application in TeamSpeak 6", "Warning", true);
    }
}

async function connectToTeamspeak() {
    if (last_teamspeak_status) return;
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
    if (last_obs_status) return;
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
    if (last_teamspeak_status) setMarkerToConnecting('ts_status', true);
    if (last_obs_status) setMarkerToConnecting('obs_status', true);

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

function animateButtonToggleHide(buttonName, gridName) {
    const button = document.getElementById(buttonName);
    const grid = document.getElementById(gridName);

    if (!button || !grid) return;

    if (button.classList.contains("show")) {
        button.classList.remove("show");
        button.classList.add("hide");

        grid.classList.remove("hidden");
    } else {
        button.classList.add("show");
        button.classList.remove("hide");

        grid.classList.add("hidden");
    }
}

// Initialization and Event Listeners linking everything once the document loaded
document.addEventListener('DOMContentLoaded', () => {
    // Populate form data on entry
    loadSettings().then();

    // Setup multi-range visual callbacks
    initSliders();

    // Setup initial connection state check, then run every 3000ms (3 seconds)
    checkConnectionState().then();
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
    document.getElementById('ts_hide')?.addEventListener('click', () => {
        animateButtonToggleHide("ts_hide", "ts-form-grid");
    });
    document.getElementById('obs_hide')?.addEventListener('click', () => {
        animateButtonToggleHide("obs_hide", "obs-form-grid");
    });
    document.getElementById('autoconnect')?.addEventListener('change', toggleAutoConnect);
    document.getElementById('blinking_enabled')?.addEventListener('change', toggleBlinking);
});