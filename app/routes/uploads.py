import json
import requests
from flask import jsonify, request, send_file
from app.models import Upload, db_session
from config import Config
from app.utils.helpers import current_user, _pinata_headers, _proxy_stream_cid
import io

def init_upload_routes(app):
    @app.route("/upload", methods=["POST"])
    def upload():
        u = current_user()
        if not u:
            return jsonify(error="authentication required"), 401
            
        if "file" not in request.files:
            return jsonify(error="no file provided"), 400
            
        file = request.files["file"]
        if file.filename == "":
            return jsonify(error="no filename"), 400

        files = {"file": (file.filename, file.stream, file.mimetype)}
        headers = _pinata_headers()
        
        try:
            resp = requests.post(Config.PINATA_PIN_FILE_URL, files=files, headers=headers, timeout=180)
        except requests.RequestException as e:
            return jsonify(error="pinata request failed", detail=str(e)), 502

        if resp.status_code not in (200, 201):
            return jsonify(error="pinata error", status_code=resp.status_code, body=resp.text), 502

        data = resp.json()
        cid = data.get("IpfsHash") or data.get("ipfsHash")
        if not cid:
            return jsonify(error="no IpfsHash in pinata response", response=data), 502

        db = db_session()
        up = Upload(cid=cid, filename=file.filename, content_type=file.mimetype, user_id=u.id, pinata_response=json.dumps(data))
        db.add(up)
        db.commit()
        db.refresh(up)
        db.close()

        return jsonify(cid=cid, gateway_url=f"{Config.PINATA_GATEWAY}/{cid}", id=up.id)

    @app.route("/my_uploads")
    def my_uploads():
        u = current_user()
        if not u:
            return jsonify(error="authentication required"), 401
            
        db = db_session()
        rows = db.query(Upload).filter_by(user_id=u.id).order_by(Upload.uploaded_at.desc()).all()
        files = [{
            "id": r.id, 
            "cid": r.cid, 
            "filename": r.filename, 
            "content_type": r.content_type, 
            "uploaded_at": r.uploaded_at.isoformat()
        } for r in rows]
        db.close()
        return jsonify(files=files)

    @app.route("/preview_file/<int:upload_id>")
    def preview_file(upload_id):
        """Serve file content directly for preview"""
        u = current_user()
        if not u:
            return jsonify(error="authentication required"), 401
            
        db = db_session()
        upload = db.query(Upload).filter_by(id=upload_id, user_id=u.id).first()
        db.close()
        
        if not upload:
            return jsonify(error="file not found"), 404

        try:
            # Fetch file from IPFS via Pinata gateway
            gateway_url = f"{Config.PINATA_GATEWAY}/{upload.cid}"
            response = requests.get(gateway_url, stream=True, timeout=30)
            
            if response.status_code != 200:
                return jsonify(error="failed to fetch file from IPFS"), 502

            # Get the file content
            file_content = response.content
            content_type = upload.content_type or response.headers.get('content-type', 'application/octet-stream')
            
            # Create a file-like object from the content
            file_obj = io.BytesIO(file_content)
            
            return send_file(
                file_obj,
                mimetype=content_type,
                as_attachment=False,
                download_name=upload.filename
            )
            
        except requests.RequestException as e:
            return jsonify(error="failed to fetch file", detail=str(e)), 502

    @app.route("/preview_content/<int:upload_id>")
    def preview_content(upload_id):
        """Get file info and content for preview"""
        u = current_user()
        if not u:
            return jsonify(error="authentication required"), 401
            
        db = db_session()
        upload = db.query(Upload).filter_by(id=upload_id, user_id=u.id).first()
        db.close()
        
        if not upload:
            return jsonify(error="file not found"), 404

        try:
            # Fetch file from IPFS
            gateway_url = f"{Config.PINATA_GATEWAY}/{upload.cid}"
            response = requests.get(gateway_url, timeout=30)
            
            if response.status_code != 200:
                return jsonify(error="failed to fetch file from IPFS"), 502

            content_type = upload.content_type or response.headers.get('content-type', 'application/octet-stream')
            
            # For text-based files, return the actual content
            if (content_type.startswith('text/') or 
                'json' in content_type or 
                'javascript' in content_type or
                'xml' in content_type):
                
                return jsonify({
                    "type": "text",
                    "content": response.text,
                    "filename": upload.filename,
                    "content_type": content_type,
                    "cid": upload.cid
                })
            
            # For binary files, return the file URL
            else:
                return jsonify({
                    "type": "binary",
                    "url": f"/preview_file/{upload_id}",
                    "filename": upload.filename,
                    "content_type": content_type,
                    "cid": upload.cid
                })
                
        except requests.RequestException as e:
            return jsonify(error="failed to fetch file", detail=str(e)), 502

    @app.route('/download/<int:upload_id>')
    def download_by_id(upload_id):
        u = current_user()
        if not u:
            return "authentication required", 401
            
        db = db_session()
        up = db.query(Upload).filter_by(id=upload_id).first()
        db.close()
        
        if not up:
            return "not found", 404
        if up.user_id != u.id:
            return "forbidden: not owner", 403
            
        return _proxy_stream_cid(up.cid, filename=up.filename)

    @app.route('/download_by_cid/<cid>')
    def download_by_cid(cid):
        u = current_user()
        if not u:
            return "authentication required", 401
            
        db = db_session()
        up = db.query(Upload).filter_by(cid=cid, user_id=u.id).first()
        db.close()
        
        if not up:
            return "not found or not owner", 404
            
        return _proxy_stream_cid(cid, filename=up.filename)

    @app.route('/delete/<int:upload_id>', methods=['DELETE'])
    def delete_upload(upload_id):
        u = current_user()
        if not u:
            return jsonify(error="authentication required"), 401
            
        db = db_session()
        up = db.query(Upload).filter_by(id=upload_id, user_id=u.id).first()
        
        if not up:
            db.close()
            return jsonify(error="file not found"), 404
            
        try:
            db.delete(up)
            db.commit()
            db.close()
            
            return jsonify(success=True, message="File removed from your drive")
        except Exception as e:
            db.rollback()
            db.close()
            return jsonify(error=str(e)), 500