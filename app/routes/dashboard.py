from flask import render_template, redirect, url_for
from config import Config
from ..utils.helpers import current_user
from ..models import Upload, db_session

def init_dashboard_routes(app):
    @app.route("/dashboard")  # Add this decorator to handle both routes
    def dashboard():
        u = current_user()
        if not u:
            return redirect(url_for('login'))
        
        db = db_session()
        files = db.query(Upload).filter_by(user_id=u.id).order_by(Upload.uploaded_at.desc()).all()
        db.close()
        
        return render_template('dashboard.html', gateway=Config.PINATA_GATEWAY, files=files)