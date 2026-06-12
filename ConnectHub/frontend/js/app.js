/**
 * ConnectHub – Core Offline JavaScript Logic
 * Contains:
 *  - IndexedDB Manager (Offline-first queues)
 *  - Connectivity Monitor & Heartbeat
 *  - Background Synchronization
 *  - Toast Notification Engine
 *  - Global SOS Modal & Utilities
 */

// ==========================================
// CONFIGURATION & GLOBAL STATE
// ==========================================
const API_BASE = '';
let dbInstance = null;
let currentUser = null;

// ==========================================
// INDEXEDDB DATABASE MANAGER
// ==========================================
const DB_NAME = 'ConnectHubDB';
const DB_VERSION = 1;

function initDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onerror = (event) => {
            console.error('IndexedDB open error:', event.target.error);
            reject(event.target.error);
        };

        request.onsuccess = (event) => {
            dbInstance = event.target.result;
            console.log('IndexedDB initialized successfully.');
            resolve(dbInstance);
        };

        request.onupgradeneeded = (event) => {
            const db = event.target.result;

            // 1. Pending Messages store (offline-composed messages queue)
            if (!db.objectStoreNames.contains('pending_messages')) {
                db.createObjectStore('pending_messages', { keyPath: 'id' });
            }

            // 2. Cached Messages store (history viewer cache)
            if (!db.objectStoreNames.contains('cached_messages')) {
                db.createObjectStore('cached_messages', { keyPath: 'id' });
            }

            // 3. Cached Contacts store (contacts cache)
            if (!db.objectStoreNames.contains('cached_contacts')) {
                db.createObjectStore('cached_contacts', { keyPath: 'id' });
            }
            
            console.log('IndexedDB schema upgraded.');
        };
    });
}

// Helper: Save item to a store
function dbSave(storeName, item) {
    return new Promise((resolve, reject) => {
        if (!dbInstance) return reject('DB not initialized');
        const transaction = dbInstance.transaction([storeName], 'readwrite');
        const store = transaction.objectStore(transaction.objectStoreNames[0]);
        const request = store.put(item);

        request.onsuccess = () => resolve(true);
        request.onerror = (e) => reject(e.target.error);
    });
}

// Helper: Get all items from a store
function dbGetAll(storeName) {
    return new Promise((resolve, reject) => {
        if (!dbInstance) return reject('DB not initialized');
        const transaction = dbInstance.transaction([storeName], 'readonly');
        const store = transaction.objectStore(transaction.objectStoreNames[0]);
        const request = store.getAll();

        request.onsuccess = () => resolve(request.result);
        request.onerror = (e) => reject(e.target.error);
    });
}

// Helper: Delete item from a store
function dbDelete(storeName, id) {
    return new Promise((resolve, reject) => {
        if (!dbInstance) return reject('DB not initialized');
        const transaction = dbInstance.transaction([storeName], 'readwrite');
        const store = transaction.objectStore(transaction.objectStoreNames[0]);
        const request = store.delete(id);

        request.onsuccess = () => resolve(true);
        request.onerror = (e) => reject(e.target.error);
    });
}

// Helper: Clear store
function dbClear(storeName) {
    return new Promise((resolve, reject) => {
        if (!dbInstance) return reject('DB not initialized');
        const transaction = dbInstance.transaction([storeName], 'readwrite');
        const store = transaction.objectStore(transaction.objectStoreNames[0]);
        const request = store.clear();

        request.onsuccess = () => resolve(true);
        request.onerror = (e) => reject(e.target.error);
    });
}

// ==========================================
// TOAST NOTIFICATION ENGINE
// ==========================================
function showToast(title, message, type = 'success') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let iconSvg = '';
    if (type === 'success') {
        iconSvg = `<svg viewBox="0 0 24 24"><path stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M22 11.08V12a10 10 0 1 1-5.93-9.14M22 4L12 14.01l-3-3"/></svg>`;
    } else if (type === 'error') {
        iconSvg = `<svg viewBox="0 0 24 24"><path stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01"/></svg>`;
    } else { // warning
        iconSvg = `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" stroke-width="2"/><line x1="12" y1="16" x2="12.01" y2="16" stroke="currentColor" stroke-width="2"/></svg>`;
    }

    toast.innerHTML = `
        <div class="toast-icon">${iconSvg}</div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
    `;

    container.appendChild(toast);

    // Auto-remove toast after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'slide-in-toast 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) reverse';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ==========================================
// CONNECTIVITY MONITOR & AUTO-SYNC
// ==========================================
let isApplicationOnline = navigator.onLine;

function updateConnectivityUI() {
    const widget = document.getElementById('network-status-widget');
    if (!widget) return;

    const isSimulated = localStorage.getItem('simulate_offline') === 'true';
    const textSpan = widget.querySelector('.network-text');

    widget.className = 'network-widget';
    
    if (isSimulated) {
        widget.classList.add('simulated-offline');
        textSpan.innerText = 'Offline (Sim)';
        isApplicationOnline = false;
    } else if (navigator.onLine) {
        widget.classList.add('online');
        textSpan.innerText = 'Online';
        isApplicationOnline = true;
    } else {
        widget.classList.add('offline');
        textSpan.innerText = 'Offline';
        isApplicationOnline = false;
    }
}

// Check network status on backend (Heartbeat)
async function checkBackendHeartbeat() {
    if (localStorage.getItem('simulate_offline') === 'true') {
        isApplicationOnline = false;
        updateConnectivityUI();
        return;
    }

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 sec timeout

        const response = await fetch('/api/auth/me', {
            method: 'GET',
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        const wasOffline = !isApplicationOnline;
        isApplicationOnline = response.ok;
        
        updateConnectivityUI();

        if (wasOffline && isApplicationOnline) {
            showToast('Connection Restored', 'Back online. Syncing queued messages...', 'success');
            syncOfflineQueue();
        }
    } catch (error) {
        if (isApplicationOnline) {
            isApplicationOnline = false;
            updateConnectivityUI();
            showToast('Connection Lost', 'Server is currently unreachable. Switched to offline queue.', 'warning');
        }
    }
}

// Toggle manual offline mode simulation
function toggleOfflineSimulation() {
    const isSimulated = localStorage.getItem('simulate_offline') === 'true';
    if (isSimulated) {
        localStorage.setItem('simulate_offline', 'false');
        showToast('Simulation Disabled', 'Reconnecting to platform...', 'success');
        checkBackendHeartbeat();
    } else {
        localStorage.setItem('simulate_offline', 'true');
        showToast('Simulation Enabled', 'Platform set to Offline Mode.', 'warning');
        isApplicationOnline = false;
        updateConnectivityUI();
        // Fire disconnected event for websocket client
        window.dispatchEvent(new CustomEvent('connecthub-offline-simulation'));
    }
}

// Sync offline queue to server
async function syncOfflineQueue() {
    if (!isApplicationOnline) return;

    try {
        const pending = await dbGetAll('pending_messages');
        if (pending.length === 0) return;

        console.log(`Syncing ${pending.length} pending messages...`);

        const response = await fetch('/api/messages/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ messages: pending })
        });

        if (response.ok) {
            const result = await response.json();
            
            // Delete successfully synced messages from queue
            for (const id of result.synced) {
                await dbDelete('pending_messages', id);
                // Optionally update cached messages status
                const cached = pending.find(m => m.id === id);
                if (cached) {
                    cached.status = 'sent';
                    await dbSave('cached_messages', cached);
                }
            }

            if (result.synced.length > 0) {
                showToast('Sync Complete', `Synchronized ${result.synced.length} emergency messages.`, 'success');
                // Trigger event so chat pages reload
                window.dispatchEvent(new CustomEvent('connecthub-synced', { detail: result.synced }));
            }
        }
    } catch (err) {
        console.error('Error syncing offline queue:', err);
    }
}

// ==========================================
// USER SESSION AUTH CHECK
// ==========================================
async function checkAuth() {
    try {
        const res = await fetch('/api/auth/me');
        const data = await res.json();
        currentUser = data.user;
        
        const path = window.location.pathname;
        const isAuthPage = path.includes('login') || path.includes('register') || path === '/' || path.endsWith('index.html');
        
        if (!currentUser) {
            if (!isAuthPage) {
                window.location.href = '/login';
            }
        } else {
            // Update username in nav bar if exists
            const userDisplay = document.getElementById('user-username-display');
            if (userDisplay) {
                userDisplay.innerText = currentUser.username;
            }
            if (isAuthPage && path !== '/' && !path.endsWith('index.html')) {
                window.location.href = '/dashboard';
            }
        }
    } catch (e) {
        console.error('Session verification failed:', e);
    }
}

// Logout handler
async function handleLogout() {
    try {
        const res = await fetch('/api/auth/logout', { method: 'POST' });
        if (res.ok) {
            dbClear('pending_messages');
            dbClear('cached_messages');
            dbClear('cached_contacts');
            showToast('Logged Out', 'Successfully signed out.', 'success');
            setTimeout(() => { window.location.href = '/login'; }, 1000);
        }
    } catch (e) {
        console.error('Logout error:', e);
    }
}

// ==========================================
// GLOBAL EMERGENCY SOS MODAL
// ==========================================
function setupGlobalSOSModal() {
    // Check if floating button exists, if not add it dynamically if user is logged in
    const path = window.location.pathname;
    const isAuthPage = path.includes('login') || path.includes('register') || path === '/' || path.endsWith('index.html');
    
    if (isAuthPage) return; // Do not display floating SOS on login/landing

    let sosBtn = document.querySelector('.floating-sos-btn');
    if (!sosBtn) {
        sosBtn = document.createElement('button');
        sosBtn.className = 'floating-sos-btn';
        sosBtn.id = 'global-floating-sos-btn';
        sosBtn.title = 'EMERGENCY SOS';
        sosBtn.innerHTML = `
            <svg viewBox="0 0 24 24">
                <path d="M12 9v4M12 17h.01" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        `;
        document.body.appendChild(sosBtn);
    }

    let sosOverlay = document.querySelector('.sos-overlay');
    if (!sosOverlay) {
        sosOverlay = document.createElement('div');
        sosOverlay.className = 'sos-overlay';
        sosOverlay.id = 'global-sos-overlay';
        sosOverlay.innerHTML = `
            <div class="glass-card sos-modal">
                <h2>CONFIRM EMERGENCY SOS</h2>
                <p style="margin-bottom: 20px; color: var(--text-secondary);">
                    This will broadcast an emergency alert with your current location/timestamp to ALL your priority contacts.
                </p>
                <div class="form-group" style="text-align: left;">
                    <label class="form-label">Custom SOS Message (Optional)</label>
                    <input type="text" id="global-sos-message-input" class="form-control" placeholder="I need immediate medical/safety assistance.">
                </div>
                <div style="display: flex; gap: 15px; margin-top: 25px;">
                    <button class="btn btn-secondary" id="global-sos-cancel-btn" style="flex: 1;">Cancel</button>
                    <button class="btn btn-danger" id="global-sos-confirm-btn" style="flex: 1;">TRIGGER SOS</button>
                </div>
            </div>
        `;
        document.body.appendChild(sosOverlay);
    }

    // Modal Events
    sosBtn.addEventListener('click', () => {
        sosOverlay.classList.add('active');
        document.getElementById('global-sos-message-input').focus();
    });

    document.getElementById('global-sos-cancel-btn').addEventListener('click', () => {
        sosOverlay.classList.remove('active');
    });

    document.getElementById('global-sos-confirm-btn').addEventListener('click', async () => {
        const msgInput = document.getElementById('global-sos-message-input');
        const customMessage = msgInput.value.trim();
        
        sosOverlay.classList.remove('active');
        
        // Execute SOS trigger
        try {
            if (!isApplicationOnline) {
                // If completely offline, store alert in local pending queue (or cache)
                showToast('Offline SOS Stored', 'Cannot broadcast SOS immediately. SOS has been saved to local offline database and will sync once connection returns!', 'error');
                // Save locally
                const alertObj = {
                    id: Date.now(),
                    alert_message: customMessage || "EMERGENCY! I need immediate help.",
                    timestamp: new Date().toISOString()
                };
                await dbSave('pending_messages', {
                    id: 'sos_' + alertObj.id,
                    receiver_id: 0, // 0 = Broadcast to all
                    message: `[OFFLINE SOS ALERT] ${alertObj.alert_message}`,
                    status: 'pending',
                    timestamp: alertObj.timestamp
                });
                msgInput.value = '';
                return;
            }

            const response = await fetch('/api/emergency/sos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: customMessage })
            });

            if (response.ok) {
                const resData = await response.json();
                showToast('SOS Broadcasted', `Alert sent. Notified ${resData.notified_contacts.length} priority contacts.`, 'success');
                msgInput.value = '';
                // Reload dashboard activity if on dashboard page
                window.dispatchEvent(new CustomEvent('connecthub-sos-triggered'));
            } else {
                showToast('SOS Broadcast Failed', 'Server rejected request.', 'error');
            }
        } catch (err) {
            showToast('SOS Error', 'Failed to communicate with server.', 'error');
        }
    });
}

// ==========================================
// INITIALIZATION ON DOM CONTENT LOADED
// ==========================================
document.addEventListener('DOMContentLoaded', async () => {
    // Initialize DB first
    await initDB();

    // Check Authentication state
    await checkAuth();

    // Setup network indicator widget event listener
    const widget = document.getElementById('network-status-widget');
    if (widget) {
        widget.addEventListener('click', toggleOfflineSimulation);
    }

    // Bind Logout Button
    const logoutBtn = document.getElementById('navbar-logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }

    // Set initial network view
    updateConnectivityUI();

    // Heartbeat check every 10 seconds
    setInterval(checkBackendHeartbeat, 10000);

    // Initial check right after load
    checkBackendHeartbeat();

    // Handle standard online/offline events
    window.addEventListener('online', () => {
        checkBackendHeartbeat();
    });
    window.addEventListener('offline', () => {
        isApplicationOnline = false;
        updateConnectivityUI();
        showToast('Network Offline', 'Your browser has lost internet connection.', 'warning');
    });

    // Setup the floating SOS button
    setupGlobalSOSModal();
});
