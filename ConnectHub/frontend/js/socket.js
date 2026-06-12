/**
 * ConnectHub – Real-Time WebSocket Logic
 * Manages Socket.IO connection, message dispatch, status updates, 
 * typing indicators, and emergency SOS alerts.
 */

let socket = null;
window.onlineUsers = new Set();

function initSocketConnection() {
    // Only connect if user is authenticated and socket is not already initialized
    const path = window.location.pathname;
    const isAuthPage = path.includes('login') || path.includes('register') || path === '/' || path.endsWith('index.html');
    
    if (isAuthPage) return; // Don't connect on login or landing pages

    // If socket.io script is loaded successfully
    if (typeof io === 'undefined') {
        console.warn('Socket.IO client script not loaded. Real-time features disabled.');
        return;
    }

    if (socket) {
        return;
    }

    console.log('Connecting to ConnectHub WebSocket server...');
    socket = io();

    // ==========================================
    // SOCKET EVENT HANDLERS
    // ==========================================
    
    socket.on('connect', () => {
        console.log('WebSocket connection established.');
        // If simulation was previously active, deactivate it to be safe
        if (localStorage.getItem('simulate_offline') === 'true') {
            socket.disconnect();
        }
    });

    socket.on('disconnect', () => {
        console.log('WebSocket connection dropped.');
        window.onlineUsers.clear();
        window.dispatchEvent(new CustomEvent('connecthub-socket-disconnected'));
    });

    // Receive list of all currently online users on connect
    socket.on('online_users_list', (usersList) => {
        window.onlineUsers = new Set(usersList);
        window.dispatchEvent(new CustomEvent('connecthub-online-list-updated'));
    });

    // Real-time status toggle (Online/Offline)
    socket.on('user_status_change', (data) => {
        const userId = parseInt(data.user_id);
        if (data.status === 'online') {
            window.onlineUsers.add(userId);
        } else {
            window.onlineUsers.delete(userId);
        }
        window.dispatchEvent(new CustomEvent('connecthub-user-status-changed', { detail: data }));
    });

    // Incoming messages
    socket.on('receive_message', async (message) => {
        console.log('Received real-time message:', message);
        
        // Cache locally in IndexedDB
        if (typeof dbSave === 'function') {
            await dbSave('cached_messages', message);
        }

        // Fire delivery receipt to server immediately if recipient (this client) has seen it
        socket.emit('mark_as_delivered', { id: message.id });

        // Trigger notification toast (unless it's an SOS which has a separate broadcast handler)
        if (!message.message.startsWith('[SOS ALERT]')) {
            showToast('New Message', `Received a message.`, 'success');
        }

        // Dispatch local event for chat screen
        window.dispatchEvent(new CustomEvent('connecthub-receive-message', { detail: message }));
    });

    // Message delivery status update (sent -> delivered)
    socket.on('message_status_update', async (data) => {
        console.log('Message status updated:', data);
        
        if (typeof dbGetAll === 'function') {
            // Update status inside Cached Messages IndexedDB
            const cached = await dbGetAll('cached_messages');
            const match = cached.find(m => m.id === data.id);
            if (match) {
                match.status = data.status;
                await dbSave('cached_messages', match);
            }
        }

        // Notify UI components
        window.dispatchEvent(new CustomEvent('connecthub-message-status-updated', { detail: data }));
    });

    // Typing state from peers
    socket.on('typing_status', (data) => {
        window.dispatchEvent(new CustomEvent('connecthub-typing-status', { detail: data }));
    });

    // SOS broadcast from priority contact
    socket.on('sos_broadcast', (data) => {
        showToast('🚨 SOS EMERGENCY ALERT', `${data.sender_username.toUpperCase()}: "${data.alert_message}"`, 'error');
        
        // Broadcast local sound alert or alert system
        playSOSAlertSound();

        window.dispatchEvent(new CustomEvent('connecthub-sos-broadcast', { detail: data }));
    });

    // SOS broadcast globally
    socket.on('sos_broadcast_global', (data) => {
        showToast('⚠️ REGIONAL SOS ALERT', `${data.sender_username.toUpperCase()} has sent an emergency broadcast!`, 'warning');
    });
}

// Function to emit a real-time message
function socketSendMessage(msgId, receiverId, text) {
    if (socket && socket.connected) {
        socket.emit('send_message', {
            id: msgId,
            receiver_id: receiverId,
            message: text
        });
        return true;
    }
    return false; // Returns false if server is unreachable (offline queue fallback)
}

// Function to emit typing state
function socketSendTypingState(receiverId, isTyping) {
    if (socket && socket.connected) {
        socket.emit('typing', {
            receiver_id: receiverId,
            is_typing: isTyping
        });
    }
}

// Audio SOS Alert simulator using browser Audio Synth (zero external assets needed)
function playSOSAlertSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        
        // SOS Siren sequence
        const playTone = (freq, duration, delay) => {
            setTimeout(() => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                
                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
                
                gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + duration - 0.05);
                
                osc.connect(gain);
                gain.connect(audioCtx.destination);
                
                osc.start();
                osc.stop(audioCtx.currentTime + duration);
            }, delay);
        };
        
        // Play 3 short, 3 long, 3 short beep sequence (SOS)
        let delay = 0;
        const shortBeep = 150;
        const longBeep = 350;
        const pause = 100;
        
        // S (. . .)
        for (let i = 0; i < 3; i++) {
            playTone(880, 0.1, delay);
            delay += shortBeep + pause;
        }
        delay += 150; // Pause between letters
        
        // O (- - -)
        for (let i = 0; i < 3; i++) {
            playTone(660, 0.25, delay);
            delay += longBeep + pause;
        }
        delay += 150;
        
        // S (. . .)
        for (let i = 0; i < 3; i++) {
            playTone(880, 0.1, delay);
            delay += shortBeep + pause;
        }
    } catch (e) {
        console.warn('Audio Context failed to play alert tone:', e);
    }
}

// ==========================================
// EVENT LIFECYCLE MANAGEMENT
// ==========================================

// Handle simulated offline switch
window.addEventListener('connecthub-offline-simulation', () => {
    if (socket) {
        socket.disconnect();
        socket = null;
        console.log('Simulating offline: WebSocket closed.');
    }
});

// Auto initialize when DOM loads
document.addEventListener('DOMContentLoaded', () => {
    // Check auth status periodically, then initialize socket
    setTimeout(initSocketConnection, 500);
});
