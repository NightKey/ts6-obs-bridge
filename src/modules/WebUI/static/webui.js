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

// 1. On load: Fetch existing settings and populate the form
async function loadSettings() {
    const data = await apiFetch('get_settings');
    if (!data) return;

    const hostInput = document.getElementById('host');
    const portInput = document.getElementById('port');

    if (hostInput && data.host !== undefined) {
        hostInput.value = data.host;
    }
    if (portInput && data.port !== undefined) {
        portInput.value = data.port;
    }
}

// 2. Change WebUI Event: Send payload to server and redirect on success
async function changeWebui() {
    const submitBtn = document.getElementById('submit-btn');
    const host = document.getElementById('host').value.trim();
    const port = document.getElementById('port').value.trim();

    // Basic front-end verification
    if (!host || !port) {
        showError("Please fill out both the Host and Port fields.", "Empty fields");
        return;
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Updating...";
    }

    const response = await apiFetch('change_webui', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ host, port })
    });

    if (response) {
        if (submitBtn) {
            submitBtn.textContent = "Redirecting in 2s...";
        }
        setTimeout(() => {
            window.location.href = `http://${host}:${port}`;
        }, 2000);
    } else {
        // Re-enable interactive items upon failure
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = "Update";
        }
    }
}

// 3. Error Popup Visual Handler
function showError(message, title, temporary = false) {
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

// Initialization and Event Listeners linking everything once the document loaded
document.addEventListener('DOMContentLoaded', () => {
    // Populate form data on entry
    loadSettings().then();

    // Bind event listeners to DOM buttons using specified IDs
    document.getElementById('submit-btn')?.addEventListener('click', (e) => {
        e.preventDefault();
        changeWebui().then();
    });

    document.getElementById('btnCloseError')?.addEventListener('click', () => {
        document.getElementById('errorPopup').classList.remove('show');
    });
});