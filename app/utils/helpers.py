import requests
from flask import session
from sqlalchemy.orm import sessionmaker
from ..models import SessionLocal, User
from config import Config

def db_session():
    return SessionLocal()

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    db = db_session()
    u = db.query(User).filter_by(id=uid).first()
    db.close()
    return u

def login_user(user):
    session["user_id"] = user.id
    session["username"] = user.username

def logout_user():
    session.pop("user_id", None)
    session.pop("username", None)

def _pinata_headers():
    if Config.PINATA_JWT:
        return {"Authorization": f"Bearer {Config.PINATA_JWT}"}
    if Config.PINATA_API_KEY and Config.PINATA_API_SECRET:
        return {"pinata_api_key": Config.PINATA_API_KEY, "pinata_secret_api_key": Config.PINATA_API_SECRET}
    return {}

def _proxy_stream_cid(cid, filename=None):
    from flask import Response, stream_with_context
    
    url = f"{Config.PINATA_GATEWAY}/{cid}"
    try:
        r = requests.get(url, stream=True, timeout=30)
    except requests.RequestException as e:
        return (f"failed to fetch from gateway: {e}", 502)
    if r.status_code >= 400:
        return (f"gateway returned status {r.status_code}", 502)

    content_type = r.headers.get('content-type', 'application/octet-stream')
    content_length = r.headers.get('content-length')
    disposition = 'inline'
    if filename:
        disposition = f'attachment; filename="{filename}"'

    def generate():
        try:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        finally:
            r.close()

    headers = {'Content-Type': content_type, 'Content-Disposition': disposition}
    if content_length:
        headers['Content-Length'] = content_length

    return Response(stream_with_context(generate()), headers=headers)