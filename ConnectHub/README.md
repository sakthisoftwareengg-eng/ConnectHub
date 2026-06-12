# ConnectHub – Emergency Offline Messaging Platform

ConnectHub is a web application that enables users to queue and transmit emergency messages even when internet connectivity is down. Using browser-native **IndexedDB** for client-side storage and **Flask-SocketIO** for real-time online routing, ConnectHub bridges the gap between offline isolation and real-time connectivity.

---

## Technical Stack
- **Frontend**: HTML5, CSS3 (curated HSL dark/light modes, glassmorphism), Vanilla JavaScript.
- **Backend**: Python Flask, Flask-SocketIO (for real-time synchronization, typing indicators, and user status).
- **Database**: SQLite (managed with Flask-SQLAlchemy).

---

## Project Structure
```text
ConnectHub/
├── frontend/
│   ├── index.html          # Features showcase and landing page
│   ├── login.html          # User authentication login
│   ├── register.html       # User authentication registration
│   ├── dashboard.html      # Console stats, connection logs, recent feed
│   ├── contacts.html       # Emergency contacts manager (CRUD, priority)
│   ├── messages.html       # Chat module (live sockets + IndexedDB queues)
│   ├── emergency.html      # SOS One-click broadcast trigger
│   ├── css/
│   │   └── style.css       # Unified design styling
│   └── js/
│       ├── app.js          # IndexedDB setup, connection monitor, bg sync
│       ├── socket.js       # Real-time WebSocket event triggers
│       └── theme.js        # Light/Dark configuration switcher
├── backend/
│   ├── app.py              # Main Flask server runner
│   ├── models.py           # SQLite database schema models
│   ├── routes.py           # REST endpoints and static page routing
│   └── socketio_events.py  # WebSocket connection events
├── requirements.txt        # Backend python dependencies
└── README.md               # Setup and testing instructions
```

---

## Local Installation

Ensure you have **Python 3.8+** installed.

### 1. Setup Virtual Environment (Recommended)
Open a terminal in the root `ConnectHub/` directory and run:
```bash
python -m venv venv
```
Activate the virtual environment:
- **Windows (PowerShell)**: `.\venv\Scripts\Activate.ps1`
- **Windows (CMD)**: `.\venv\Scripts\activate.bat`
- **macOS / Linux**: `source venv/bin/activate`

### 2. Install Dependencies
Run the package installer:
```bash
pip install -r requirements.txt
```

### 3. Run the Server
Launch the application:
```bash
python backend/app.py
```

Access the application in your browser at:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## Verification & Offline Scenario Testing

ConnectHub features a built-in **Network Simulation Switch** to easily test offline-first states without having to disconnect your computer from the internet.

### Scenario A: Offline Message Sync Queue
1. Visit the platform, sign up a new account (e.g., `UserA`), and go to the **Contacts** tab.
2. Click **Add Contact**, enter `UserB` (or any name) and a phone number, select **High** priority, and click Save.
3. Click on the **Online** widget in the top navigation bar. It will turn orange and display **Offline (Sim)**. The platform is now completely disconnected from the backend.
4. Go to **Messages** and select your contact. Type a message and click Send.
5. Notice that the message bubble displays with a yellow **clock** status icon. An warning toast will verify that the message is queued inside IndexedDB.
6. Open your browser developer tools (**F12**), navigate to the **Application** or **Storage** tab, open **IndexedDB -> ConnectHubDB -> pending_messages**, and inspect the stored JSON.
7. Click the **Offline (Sim)** widget in the navbar again. It will turn green and say **Online**.
8. Observe the background sync:
   - A success toast will notify you that the queued message was synced.
   - The message bubble status icon in the thread updates to a green double check.
   - The message is uploaded to the SQLite backend and cleared from IndexedDB.

### Scenario B: SOS Emergency Broadcast
1. Go to the **SOS Console** tab.
2. Observe your priority contacts listed as broadcast targets.
3. Select a message template (e.g., `Medical Assistance`) or write a custom message.
4. Press the large red **SOS** trigger button and confirm.
5. If online, the server logs the alert and broadcasts a real-time message to your contacts, triggering an audible siren alarm for any connected recipient.
6. If offline, the SOS alert is stored in the IndexedDB buffer and will execute the broadcast automatically when the server is reachable.

### Scenario C: Offline Mesh Import/Export Backup
1. In the **Contacts** tab, click **Export JSON**. This downloads a full backup package containing your contacts, messaging history, and recent alerts.
2. This backup package can be transferred to nearby devices via Bluetooth/Wi-Fi Direct.
3. To import peer data on another client console, click **Import JSON** and upload the JSON package.
