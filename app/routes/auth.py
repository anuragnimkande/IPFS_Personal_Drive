# app/routes/auth.py
from flask import render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

# relative imports (important!)
from ..models import User, db_session
from ..utils.helpers import login_user, logout_user, current_user

def init_auth_routes(app):
    @app.route("/")
    def index():
        if current_user():
            return redirect(url_for('dashboard'))
        return render_template('index.html')

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "GET":
            return render_template('register.html', error=None)
            
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            return render_template('register.html', error="username & password required")
            
        db = db_session()
        existing = db.query(User).filter_by(username=username).first()
        if existing:
            db.close()
            return render_template('register.html', error="username already exists")
            
        u = User(username=username, password_hash=generate_password_hash(password))
        db.add(u)
        db.commit()
        db.refresh(u)
        db.close()
        
        login_user(u)
        return redirect(url_for('dashboard'))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "GET":
            return render_template('login.html', error=None)
            
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        db = db_session()
        u = db.query(User).filter_by(username=username).first()
        db.close()

        if not u:
            return render_template('login.html', error="Invalid username (Register first?)")
        
        if not check_password_hash(u.password_hash, password):
            return render_template('login.html', error="Invalid username or password")
            
        login_user(u)
        return redirect(url_for('dashboard'))

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for('index'))
