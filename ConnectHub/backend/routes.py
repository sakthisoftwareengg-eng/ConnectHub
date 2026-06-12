import json
from functools import wraps
from flask import Blueprint, request, jsonify, session, redirect, current_app
from models import db, User, Contact, Message, EmergencyAlert
from datetime import datetime

# Define blueprint
api_bp = Blueprint('api', __name__)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Unauthorized. Please log in."}), 401
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# PAGE ROUTING (Server-side Auth Redirects)
# ==========================================

@api_bp.route('/index.html')
@api_bp.route('/')
def serve_index():
    return current_app.send_static_file('index.html')

@api_bp.route('/login')
@api_bp.route('/login.html')
def serve_login():
    if 'user_id' in session:
        return redirect('/dashboard')
    return current_app.send_static_file('login.html')

@api_bp.route('/register')
@api_bp.route('/register.html')
def serve_register():
    if 'user_id' in session:
        return redirect('/dashboard')
    return current_app.send_static_file('register.html')

@api_bp.route('/dashboard')
@api_bp.route('/dashboard.html')
def serve_dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    return current_app.send_static_file('dashboard.html')

@api_bp.route('/contacts')
@api_bp.route('/contacts.html')
def serve_contacts():
    if 'user_id' not in session:
        return redirect('/login')
    return current_app.send_static_file('contacts.html')

@api_bp.route('/messages')
@api_bp.route('/messages.html')
def serve_messages():
    if 'user_id' not in session:
        return redirect('/login')
    return current_app.send_static_file('messages.html')

@api_bp.route('/emergency')
@api_bp.route('/emergency.html')
def serve_emergency():
    if 'user_id' not in session:
        return redirect('/login')
    return current_app.send_static_file('emergency.html')

# ==========================================
# AUTHENTICATION API
# ==========================================

@api_bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not username or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400

    try:
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        # Log in the user automatically
        session['user_id'] = new_user.id
        return jsonify({"message": "Registration successful", "user": new_user.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@api_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username_or_email = data.get('username', '').strip()
    password = data.get('password', '')

    if not username_or_email or not password:
        return jsonify({"error": "Username/Email and password are required"}), 400

    user = User.query.filter((User.username == username_or_email) | (User.email == username_or_email)).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username/email or password"}), 401

    session['user_id'] = user.id
    return jsonify({"message": "Login successful", "user": user.to_dict()})

@api_bp.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    session.pop('user_id', None)
    return jsonify({"message": "Logged out successfully"})

@api_bp.route('/api/auth/me', methods=['GET'])
def get_me():
    if 'user_id' not in session:
        return jsonify({"user": None}), 200
    user = User.query.get(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return jsonify({"user": None}), 200
    return jsonify({"user": user.to_dict()})

@api_bp.route('/api/users/search', methods=['GET'])
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    # Search for other users to send messages to
    current_user_id = session['user_id']
    users = User.query.filter(
        User.id != current_user_id,
        (User.username.like(f"%{query}%")) | (User.email.like(f"%{query}%"))
    ).limit(10).all()
    return jsonify([u.to_dict() for u in users])

# ==========================================
# EMERGENCY CONTACTS API
# ==========================================

@api_bp.route('/api/contacts', methods=['GET'])
@login_required
def get_contacts():
    current_user_id = session['user_id']
    query = request.args.get('q', '').strip()
    
    contacts_query = Contact.query.filter_by(user_id=current_user_id)
    if query:
        contacts_query = contacts_query.filter(Contact.contact_name.like(f"%{query}%") | Contact.phone_number.like(f"%{query}%"))
        
    contacts = contacts_query.order_index = contacts_query.order_by(Contact.priority_level == 'high', Contact.contact_name).all()
    
    # Check if contact names match registered platform users, so we can chat with them
    contacts_list = []
    for c in contacts:
        d = c.to_dict()
        # Find if this contact is a registered user on our platform by checking phone or name match
        matched_user = User.query.filter(User.username == c.contact_name).first()
        d['platform_user_id'] = matched_user.id if matched_user else None
        contacts_list.append(d)

    return jsonify(contacts_list)

@api_bp.route('/api/contacts', methods=['POST'])
@login_required
def create_contact():
    data = request.get_json() or {}
    name = data.get('contact_name', '').strip()
    phone = data.get('phone_number', '').strip()
    priority = data.get('priority_level', 'medium').lower()

    if not name or not phone:
        return jsonify({"error": "Contact name and phone number are required"}), 400
    
    if priority not in ['high', 'medium', 'low']:
        priority = 'medium'

    try:
        new_contact = Contact(
            user_id=session['user_id'],
            contact_name=name,
            phone_number=phone,
            priority_level=priority
        )
        db.session.add(new_contact)
        db.session.commit()
        return jsonify(new_contact.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/contacts/<int:contact_id>', methods=['PUT'])
@login_required
def update_contact(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=session['user_id']).first()
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    data = request.get_json() or {}
    name = data.get('contact_name', contact.contact_name).strip()
    phone = data.get('phone_number', contact.phone_number).strip()
    priority = data.get('priority_level', contact.priority_level).lower()

    if not name or not phone:
        return jsonify({"error": "Contact name and phone number are required"}), 400
        
    if priority not in ['high', 'medium', 'low']:
        priority = 'medium'

    try:
        contact.contact_name = name
        contact.phone_number = phone
        contact.priority_level = priority
        db.session.commit()
        return jsonify(contact.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/contacts/<int:contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    contact = Contact.query.filter_by(id=contact_id, user_id=session['user_id']).first()
    if not contact:
        return jsonify({"error": "Contact not found"}), 404

    try:
        db.session.delete(contact)
        db.session.commit()
        return jsonify({"message": "Contact deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# MESSAGING API (Sync & History)
# ==========================================

@api_bp.route('/api/messages/history', methods=['GET'])
@login_required
def get_message_history():
    current_user_id = session['user_id']
    contact_user_id = request.args.get('contact_id')
    query = request.args.get('q', '').strip()

    if not contact_user_id:
        return jsonify({"error": "contact_id parameter is required"}), 400

    try:
        contact_user_id = int(contact_user_id)
    except ValueError:
        return jsonify({"error": "Invalid contact_id"}), 400

    messages_query = Message.query.filter(
        ((Message.sender_id == current_user_id) & (Message.receiver_id == contact_user_id)) |
        ((Message.sender_id == contact_user_id) & (Message.receiver_id == current_user_id))
    )

    if query:
        messages_query = messages_query.filter(Message.message.like(f"%{query}%"))

    messages = messages_query.order_by(Message.timestamp.asc()).all()
    
    # Mark incoming messages as delivered if they are still 'sent' or 'pending'
    updated = False
    for msg in messages:
        if msg.receiver_id == current_user_id and msg.status in ['pending', 'sent']:
            msg.status = 'delivered'
            updated = True
    
    if updated:
        db.session.commit()

    return jsonify([m.to_dict() for m in messages])

@api_bp.route('/api/messages/sync', methods=['POST'])
@login_required
def sync_offline_messages():
    """
    Accepts a list of messages that were created offline.
    Flushes them to the main database and broadcasts them to active recipients if connected.
    """
    current_user_id = session['user_id']
    data = request.get_json() or {}
    offline_messages = data.get('messages', [])

    if not isinstance(offline_messages, list):
        return jsonify({"error": "Invalid payload format. Expected list in 'messages'."}), 400

    synced_ids = []
    failed_ids = []
    
    socketio_ref = current_app.extensions.get('socketio')

    for msg_data in offline_messages:
        msg_id = msg_data.get('id')
        receiver_id = msg_data.get('receiver_id')
        text = msg_data.get('message', '').strip()
        timestamp_str = msg_data.get('timestamp')

        if not msg_id or not receiver_id or not text:
            if msg_id:
                failed_ids.append(msg_id)
            continue

        try:
            # Check if this message already exists to prevent duplicate syncs
            existing = Message.query.get(msg_id)
            if existing:
                synced_ids.append(msg_id)
                continue

            # Parse timestamp if provided
            timestamp = datetime.utcnow()
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except ValueError:
                    pass

            new_message = Message(
                id=msg_id,
                sender_id=current_user_id,
                receiver_id=receiver_id,
                message=text,
                status='sent',
                timestamp=timestamp
            )
            
            db.session.add(new_message)
            db.session.commit()
            
            # Broadcast message via socket io if user is active
            if socketio_ref:
                # Emit message to the recipient's room
                socketio_ref.emit('receive_message', new_message.to_dict(), room=f"user_{receiver_id}")
                # Update status immediately if delivered successfully in SocketIO room logic
                # For this application, we can assume sent is successful. 
                # If they are online, socket.js will update status to delivered.
            
            synced_ids.append(msg_id)
        except Exception as e:
            db.session.rollback()
            if msg_id:
                failed_ids.append(msg_id)
            print(f"Error syncing message {msg_id}: {str(e)}")

    return jsonify({
        "success": True,
        "synced": synced_ids,
        "failed": failed_ids
    })

# ==========================================
# EMERGENCY SOS API
# ==========================================

@api_bp.route('/api/emergency/sos', methods=['POST'])
@login_required
def trigger_sos():
    current_user_id = session['user_id']
    user = User.query.get(current_user_id)
    data = request.get_json() or {}
    custom_msg = data.get('message', '').strip()
    
    timestamp = datetime.utcnow()
    timestamp_str = timestamp.strftime('%H:%M:%S')
    
    alert_msg = custom_msg if custom_msg else f"EMERGENCY! This is an SOS alert from {user.username}. I need immediate help. Timestamp: {timestamp_str}."
    
    try:
        # Save SOS Alert in Database
        alert = EmergencyAlert(
            user_id=current_user_id,
            alert_message=alert_msg,
            timestamp=timestamp
        )
        db.session.add(alert)
        db.session.commit()
        
        # Query all priority contacts of this user who are registered platform users
        priority_contacts = Contact.query.filter_by(user_id=current_user_id).all()
        
        socketio_ref = current_app.extensions.get('socketio')
        
        # Broadcast alert to all contacts (and create emergency messages in database)
        sent_notifications = []
        for contact in priority_contacts:
            matched_user = User.query.filter(User.username == contact.contact_name).first()
            
            # If the contact is a platform user, generate a direct system emergency message
            if matched_user:
                import uuid
                msg_id = str(uuid.uuid4())
                sos_msg = Message(
                    id=msg_id,
                    sender_id=current_user_id,
                    receiver_id=matched_user.id,
                    message=f"[SOS ALERT] {alert_msg}",
                    status='sent',
                    timestamp=timestamp
                )
                db.session.add(sos_msg)
                
                # Emit real-time SOS notification to contact via socket
                if socketio_ref:
                    socketio_ref.emit('receive_message', sos_msg.to_dict(), room=f"user_{matched_user.id}")
                    socketio_ref.emit('sos_broadcast', {
                        "sender_username": user.username,
                        "alert_message": alert_msg,
                        "timestamp": timestamp.isoformat()
                    }, room=f"user_{matched_user.id}")
                    sent_notifications.append(contact.contact_name)
                    
        db.session.commit()
        
        # Also broadcast alert globally to all users on the platform in emergencies
        if socketio_ref:
            socketio_ref.emit('sos_broadcast_global', {
                "sender_username": user.username,
                "alert_message": alert_msg,
                "timestamp": timestamp.isoformat()
            })

        return jsonify({
            "message": "SOS alert broadcasted successfully",
            "alert": alert.to_dict(),
            "notified_contacts": sent_notifications
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@api_bp.route('/api/emergency/alerts', methods=['GET'])
@login_required
def get_alerts():
    # Fetch alerts for the dashboard activity log
    alerts = EmergencyAlert.query.order_by(EmergencyAlert.timestamp.desc()).limit(15).all()
    results = []
    for a in alerts:
        d = a.to_dict()
        d['username'] = a.user.username
        results.append(d)
    return jsonify(results)

# ==========================================
# BACKUP & OFFLINE peer sync UTILITY
# ==========================================

@api_bp.route('/api/backup/export', methods=['GET'])
@login_required
def export_backup():
    current_user_id = session['user_id']
    user = User.query.get(current_user_id)
    
    contacts = Contact.query.filter_by(user_id=current_user_id).all()
    messages = Message.query.filter((Message.sender_id == current_user_id) | (Message.receiver_id == current_user_id)).all()
    alerts = EmergencyAlert.query.filter_by(user_id=current_user_id).all()
    
    backup_data = {
        "export_metadata": {
            "platform": "ConnectHub",
            "exporter_username": user.username,
            "exported_at": datetime.utcnow().isoformat()
        },
        "contacts": [c.to_dict() for c in contacts],
        "messages": [m.to_dict() for m in messages],
        "alerts": [a.to_dict() for a in alerts]
    }
    
    response = jsonify(backup_data)
    response.headers['Content-Disposition'] = f'attachment; filename=connecthub_backup_{user.username}.json'
    return response

@api_bp.route('/api/backup/import', methods=['POST'])
@login_required
def import_backup():
    current_user_id = session['user_id']
    
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
        
    file = request.files['file']
    if not file.filename.endswith('.json'):
        return jsonify({"error": "Only JSON files can be imported"}), 400
        
    try:
        data = json.load(file)
    except Exception as e:
        return jsonify({"error": f"Invalid JSON file format: {str(e)}"}), 400
        
    contacts_imported = 0
    messages_imported = 0
    
    try:
        # Import Contacts
        for c_data in data.get('contacts', []):
            name = c_data.get('contact_name')
            phone = c_data.get('phone_number')
            priority = c_data.get('priority_level', 'medium')
            
            if not name or not phone:
                continue
                
            # Avoid duplicate contact names/phones
            existing = Contact.query.filter_by(user_id=current_user_id, contact_name=name, phone_number=phone).first()
            if not existing:
                new_contact = Contact(
                    user_id=current_user_id,
                    contact_name=name,
                    phone_number=phone,
                    priority_level=priority
                )
                db.session.add(new_contact)
                contacts_imported += 1
                
        # Import Messages
        for m_data in data.get('messages', []):
            msg_id = m_data.get('id')
            sender_id = m_data.get('sender_id')
            receiver_id = m_data.get('receiver_id')
            text = m_data.get('message')
            status = m_data.get('status', 'sent')
            timestamp_str = m_data.get('timestamp')
            
            if not msg_id or not text:
                continue
                
            # Verify if this message is linked to our user
            if sender_id != current_user_id and receiver_id != current_user_id:
                # If importing peer data, map the sender/receiver appropriately if users exist, 
                # or skip to prevent message poisoning.
                continue
                
            existing_msg = Message.query.get(msg_id)
            if not existing_msg:
                timestamp = datetime.utcnow()
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except ValueError:
                        pass
                        
                new_msg = Message(
                    id=msg_id,
                    sender_id=sender_id,
                    receiver_id=receiver_id,
                    message=text,
                    status=status,
                    timestamp=timestamp
                )
                db.session.add(new_msg)
                messages_imported += 1
                
        db.session.commit()
        return jsonify({
            "success": True,
            "contacts_imported": contacts_imported,
            "messages_imported": messages_imported
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Import failed: {str(e)}"}), 500

# ==========================================
# DASHBOARD STATS API
# ==========================================

@api_bp.route('/api/dashboard/stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    current_user_id = session['user_id']
    
    total_contacts = Contact.query.filter_by(user_id=current_user_id).count()
    messages_sent = Message.query.filter_by(sender_id=current_user_id).count()
    
    # Standard SQLite/SQLAlchemy queries
    emergency_alerts_sent = EmergencyAlert.query.filter_by(user_id=current_user_id).count()
    
    # Pending messages are query from IndexedDB locally, but let's query backend pending messages as fallback
    pending_messages = Message.query.filter_by(sender_id=current_user_id, status='pending').count()
    
    # Recent activity stream
    recent_messages = Message.query.filter(
        (Message.sender_id == current_user_id) | (Message.receiver_id == current_user_id)
    ).order_by(Message.timestamp.desc()).limit(5).all()
    
    recent_alerts = EmergencyAlert.query.order_by(EmergencyAlert.timestamp.desc()).limit(3).all()
    
    activity = []
    for rm in recent_messages:
        action = "Sent message to" if rm.sender_id == current_user_id else "Received message from"
        partner_id = rm.receiver_id if rm.sender_id == current_user_id else rm.sender_id
        partner = User.query.get(partner_id)
        partner_name = partner.username if partner else "Unknown"
        activity.append({
            "type": "message",
            "description": f"{action} {partner_name}",
            "timestamp": rm.timestamp.isoformat(),
            "status": rm.status
        })
        
    for ra in recent_alerts:
        activity.append({
            "type": "sos",
            "description": f"SOS Alert triggered by {ra.user.username}: '{ra.alert_message[:30]}...'",
            "timestamp": ra.timestamp.isoformat(),
            "status": "broadcasted"
        })
        
    # Sort activity by timestamp desc
    activity.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify({
        "total_contacts": total_contacts,
        "messages_sent": messages_sent,
        "pending_messages": pending_messages,
        "emergency_alerts_sent": emergency_alerts_sent,
        "recent_activity": activity[:6]
    })
