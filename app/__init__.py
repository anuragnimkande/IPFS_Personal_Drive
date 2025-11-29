from flask import Flask
from config import Config
from .models import init_db


def create_app():
    app = Flask(__name__)
    app.secret_key = Config.FLASK_SECRET
    
    # Initialize database
    init_db()
    
    # Register routes
    from .routes.auth import init_auth_routes
    from .routes.uploads import init_upload_routes
    from .routes.dashboard import init_dashboard_routes

    
    init_auth_routes(app)
    init_dashboard_routes(app)
    init_upload_routes(app)
    
    return app