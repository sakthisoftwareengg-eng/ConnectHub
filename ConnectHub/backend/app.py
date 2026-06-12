import os
from flask import Flask
from flask_socketio import SocketIO
from models import db
from routes import api_bp
from socketio_events import init_socketio_events

def create_app():
    # Configure Flask to serve static files from the frontend sibling directory
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    
    # Session key config
    app.secret_key = os.environ.get('SECRET_KEY', 'connecthub_secure_emergency_session_key_99x')
    
    # Configure SQLite database path explicitly in the backend directory
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_path = os.path.join(base_dir, 'database.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize Database
    db.init_app(app)
    
    # Initialize SocketIO with support for cross-origin and session sharing
    socketio = SocketIO(app, cors_allowed_origins="*", manage_session=True)
    
    # Register page and API routes
    app.register_blueprint(api_bp)
    
    # Bind SocketIO events
    init_socketio_events(socketio)
    
    # Ensure database tables are created
    with app.app_context():
        db.create_all()
        print(f"Database initialized at: {db_path}")
        
    return app, socketio

if __name__ == '__main__':
    app, socketio = create_app()
    # Host on all interfaces, port 5000 for local network sharing access
    print("ConnectHub is running. Access locally at http://127.0.0.1:5000")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
