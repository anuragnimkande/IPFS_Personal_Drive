# app/routes/auth.py
from flask import render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from ..models import User, db_session, SECURITY_QUESTIONS
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
            return render_template('register.html', error=None, security_questions=SECURITY_QUESTIONS)
            
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        security_question = request.form.get("security_question", "").strip()
        security_answer = request.form.get("security_answer", "").strip()
        
        if not username or not password or not security_question or not security_answer:
            return render_template('register.html', 
                                error="All fields are required",
                                security_questions=SECURITY_QUESTIONS)
            
        if len(password) < 6:
            return render_template('register.html',
                                error="Password must be at least 6 characters",
                                security_questions=SECURITY_QUESTIONS)
            
        db = db_session()
        existing = db.query(User).filter_by(username=username).first()
        if existing:
            db.close()
            return render_template('register.html',
                                error="Username already exists",
                                security_questions=SECURITY_QUESTIONS)
            
        # Validate security question
        valid_questions = [q[0] for q in SECURITY_QUESTIONS]
        if security_question not in valid_questions:
            db.close()
            return render_template('register.html',
                                error="Invalid security question",
                                security_questions=SECURITY_QUESTIONS)
            
        u = User(
            username=username, 
            password_hash=generate_password_hash(password),
            security_question=security_question
        )
        u.set_security_answer(security_answer)
        
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
            return render_template('login.html', error="Invalid username")
        
        if not check_password_hash(u.password_hash, password):
            return render_template('login.html', error="Invalid password")
            
        login_user(u)
        return redirect(url_for('dashboard'))

    @app.route("/forgot-password/verify", methods=["POST"])
    def verify_security_question():
        username = request.json.get("username", "").strip()
        
        db = db_session()
        user = db.query(User).filter_by(username=username).first()
        db.close()
        
        if not user:
            return jsonify({"success": False, "error": "Username not found"})
        
        return jsonify({
            "success": True,
            "security_question": user.security_question
        })

    @app.route("/forgot-password/reset", methods=["POST"])
    def reset_password():
        username = request.json.get("username", "").strip()
        security_answer = request.json.get("security_answer", "").strip()
        new_password = request.json.get("new_password", "")
        
        if not username or not security_answer or not new_password:
            return jsonify({"success": False, "error": "All fields are required"})
        
        if len(new_password) < 6:
            return jsonify({"success": False, "error": "Password must be at least 6 characters"})
        
        db = db_session()
        user = db.query(User).filter_by(username=username).first()
        
        if not user:
            db.close()
            return jsonify({"success": False, "error": "Username not found"})
        
        if not user.check_security_answer(security_answer):
            db.close()
            return jsonify({"success": False, "error": "Incorrect security answer"})
        
        # Update password
        user.password_hash = generate_password_hash(new_password)
        db.commit()
        db.close()
        
        return jsonify({"success": True})

    @app.route("/logout")
    def logout():
        logout_user()
        return redirect(url_for('index'))
    
    