from flask import session, request
from flask_socketio import emit, join_room, leave_room
from models import db, Message, User
from datetime import datetime

# Global set to track currently connected user IDs
active_users = set()

def init_socketio_events(socketio):
    
    @socketio.on('connect')
    def handle_connect():
        user_id = session.get('user_id')
        if not user_id:
            # Reject connection if not authenticated
            return False
            
        # Add to active users
        active_users.add(user_id)
        
        # Join a private room dedicated to this user's ID
        join_room(f"user_{user_id}")
        
        # Broadcast that this user is online
        emit('user_status_change', {
            'user_id': user_id,
            'status': 'online'
        }, broadcast=True)
        
        # Send back list of currently online users to the connected client
        emit('online_users_list', list(active_users))
        print(f"User {user_id} connected. Sid: {request.sid}")

    @socketio.on('disconnect')
    def handle_disconnect():
        user_id = session.get('user_id')
        if user_id:
            active_users.discard(user_id)
            leave_room(f"user_{user_id}")
            
            # Broadcast that user went offline
            emit('user_status_change', {
                'user_id': user_id,
                'status': 'offline'
            }, broadcast=True)
            print(f"User {user_id} disconnected.")

    @socketio.on('send_message')
    def handle_send_message(data):
        """
        Handles sending a single real-time message.
        """
        sender_id = session.get('user_id')
        if not sender_id:
            return
            
        receiver_id = data.get('receiver_id')
        message_text = data.get('message', '').strip()
        msg_id = data.get('id') # Client-generated UUID

        if not receiver_id or not message_text or not msg_id:
            return

        try:
            receiver_id = int(receiver_id)
        except ValueError:
            return

        # Determine delivery status based on recipient active state
        is_recipient_online = receiver_id in active_users
        initial_status = 'delivered' if is_recipient_online else 'sent'

        # Check if message already exists (e.g. if synced via REST already)
        existing_msg = Message.query.get(msg_id)
        if existing_msg:
            # Just update and emit status update
            if existing_msg.status == 'pending':
                existing_msg.status = initial_status
                db.session.commit()
            emit('message_status_update', {
                'id': msg_id,
                'status': existing_msg.status
            }, room=f"user_{sender_id}")
            return

        new_message = Message(
            id=msg_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=message_text,
            status=initial_status,
            timestamp=datetime.utcnow()
        )

        try:
            db.session.add(new_message)
            db.session.commit()
            
            msg_dict = new_message.to_dict()
            
            # 1. Forward the message to the recipient
            emit('receive_message', msg_dict, room=f"user_{receiver_id}")
            
            # 2. Inform the sender about the delivery status confirmation
            emit('message_status_update', {
                'id': msg_id,
                'status': initial_status
            }, room=f"user_{sender_id}")
            
        except Exception as e:
            db.session.rollback()
            emit('message_status_update', {
                'id': msg_id,
                'status': 'failed'
            }, room=f"user_{sender_id}")
            print(f"Error saving real-time message: {str(e)}")

    @socketio.on('mark_as_delivered')
    def handle_mark_as_delivered(data):
        """
        Fires when a recipient client receives a message in their UI.
        """
        msg_id = data.get('id')
        if not msg_id:
            return
            
        msg = Message.query.get(msg_id)
        if msg and msg.status == 'sent':
            msg.status = 'delivered'
            try:
                db.session.commit()
                # Notify sender
                emit('message_status_update', {
                    'id': msg_id,
                    'status': 'delivered'
                }, room=f"user_{msg.sender_id}")
            except Exception as e:
                db.session.rollback()
                print(f"Failed to mark message delivered: {str(e)}")

    @socketio.on('typing')
    def handle_typing(data):
        """
        Handles real-time typing indicators.
        """
        sender_id = session.get('user_id')
        receiver_id = data.get('receiver_id')
        is_typing = data.get('is_typing', False)
        
        if sender_id and receiver_id:
            try:
                receiver_id = int(receiver_id)
                emit('typing_status', {
                    'sender_id': sender_id,
                    'is_typing': is_typing
                }, room=f"user_{receiver_id}")
            except ValueError:
                pass
