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
        if file.filename == "" or not file.filename:
            return jsonify(error="no filename"), 400

        # Reset file stream to beginning in case it was read before
        file.stream.seek(0)
        print(f"Uploading file: {file.filename}, Content-Type: {file.mimetype}, Size: {request.content_length} bytes")
        
        # Optional: Add file size validation
        MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit
        file.stream.seek(0, 2)  # Seek to end to get size
        file_size = file.stream.tell()
        file.stream.seek(0)  # Reset to beginning
        
        if file_size > MAX_FILE_SIZE:
            return jsonify(error=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"), 400

        # Prepare file for upload - ensure proper stream handling
        files = {"file": (file.filename, file.stream, file.mimetype)}
        headers = _pinata_headers()
        
        db = db_session()
        try:
            print(f"Sending file to Pinata: {file.filename} ({file_size} bytes)")
            resp = requests.post(Config.PINATA_PIN_FILE_URL, files=files, headers=headers, timeout=180)
            
            if resp.status_code not in (200, 201):
                db.rollback()
                print(f"Pinata upload failed with status {resp.status_code}: {resp.text}")
                return jsonify(error="pinata error", status_code=resp.status_code, body=resp.text), 502

            data = resp.json()
            cid = data.get("IpfsHash") or data.get("ipfsHash")
            if not cid:
                db.rollback()
                print(f"No CID in Pinata response: {data}")
                return jsonify(error="no IpfsHash in pinata response", response=data), 502

            up = Upload(
                cid=cid, 
                filename=file.filename, 
                content_type=file.mimetype, 
                user_id=u.id, 
                pinata_response=json.dumps(data)
            )
            db.add(up)
            db.commit()
            db.refresh(up)
            
            # PRINT STATEMENTS AFTER SUCCESSFUL UPLOAD
            print(f"✅ FILE UPLOAD SUCCESSFUL:")
            print(f"   - Filename: {file.filename}")
            print(f"   - CID: {cid}")
            print(f"   - Upload ID: {up.id}")
            print(f"   - User ID: {u.id}")
            print(f"   - Content Type: {file.mimetype}")
            print(f"   - File Size: {file_size} bytes")
            print(f"   - Gateway URL: {Config.PINATA_GATEWAY}/{cid}")
            print(f"   - Database Record ID: {up.id}")
            
            return jsonify(
                cid=cid, 
                gateway_url=f"{Config.PINATA_GATEWAY}/{cid}", 
                id=up.id,
                filename=file.filename,
                message="File uploaded successfully"
            )

        except requests.RequestException as e:
            db.rollback()
            print(f"❌ Pinata request failed: {str(e)}")
            return jsonify(error="pinata request failed", detail=str(e)), 502
        except Exception as e:
            db.rollback()
            print(f"❌ Upload failed with exception: {str(e)}")
            return jsonify(error="upload failed", detail=str(e)), 500
        finally:
            db.close()

    @app.route("/my_uploads")
    def my_uploads():
        u = current_user()
        if not u:
            return jsonify(error="authentication required"), 401
            
        db = db_session()
        try:
            rows = db.query(Upload).filter_by(user_id=u.id).order_by(Upload.uploaded_at.desc()).all()
            files = [{
                "id": r.id, 
                "cid": r.cid, 
                "filename": r.filename, 
                "content_type": r.content_type, 
                "uploaded_at": r.uploaded_at.isoformat()
            } for r in rows]
            
            print(f"📁 User {u.id} fetched {len(files)} uploads")
            return jsonify(files=files)
        except Exception as e:
            print(f"❌ Failed to fetch uploads for user {u.id}: {str(e)}")
            return jsonify(error="failed to fetch uploads", detail=str(e)), 500
        finally:
            db.close()

    @app.route("/preview_file/<int:upload_id>")
    def preview_file(upload_id):
        """Serve file content directly for preview"""
        u = current_user()
        if not u:
            return jsonify(error="authentication required"), 401
            
        db = db_session()
        try:
            upload = db.query(Upload).filter_by(id=upload_id, user_id=u.id).first()
            if not upload:
                print(f"❌ Preview file not found: upload_id={upload_id}, user_id={u.id}")
                return jsonify(error="file not found"), 404

            # Fetch file from IPFS via Pinata gateway
            gateway_url = f"{Config.PINATA_GATEWAY}/{upload.cid}"
            print(f"🔍 Previewing file: {upload.filename} (CID: {upload.cid})")
            response = requests.get(gateway_url, stream=True, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch file from IPFS: {response.status_code}")
                return jsonify(error="failed to fetch file from IPFS"), 502

            # Get the file content
            file_content = response.content
            content_type = upload.content_type or response.headers.get('content-type', 'application/octet-stream')
            
            # Create a file-like object from the content
            file_obj = io.BytesIO(file_content)
            
            print(f"✅ File preview served: {upload.filename} ({len(file_content)} bytes)")
            return send_file(
                file_obj,
                mimetype=content_type,
                as_attachment=False,
                download_name=upload.filename
            )
            
        except requests.RequestException as e:
            print(f"❌ Preview file request failed: {str(e)}")
            return jsonify(error="failed to fetch file", detail=str(e)), 502
        except Exception as e:
            print(f"❌ Preview failed: {str(e)}")
            return jsonify(error="preview failed", detail=str(e)), 500
        finally:
            db.close()

    @app.route("/preview_content/<int:upload_id>")
    def preview_content(upload_id):
        """Get file info and content for preview"""
        u = current_user()
        if not u:
            return jsonify(error="authentication required"), 401
            
        db = db_session()
        try:
            upload = db.query(Upload).filter_by(id=upload_id, user_id=u.id).first()
            if not upload:
                print(f"❌ Preview content not found: upload_id={upload_id}, user_id={u.id}")
                return jsonify(error="file not found"), 404

            # Fetch file from IPFS
            gateway_url = f"{Config.PINATA_GATEWAY}/{upload.cid}"
            print(f"🔍 Fetching preview content: {upload.filename} (CID: {upload.cid})")
            response = requests.get(gateway_url, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ Failed to fetch file from IPFS for preview: {response.status_code}")
                return jsonify(error="failed to fetch file from IPFS"), 502

            content_type = upload.content_type or response.headers.get('content-type', 'application/octet-stream')
            
            # For text-based files, return the actual content
            if (content_type.startswith('text/') or 
                'json' in content_type or 
                'javascript' in content_type or
                'xml' in content_type):
                
                print(f"✅ Text preview served: {upload.filename} ({len(response.text)} chars)")
                return jsonify({
                    "type": "text",
                    "content": response.text,
                    "filename": upload.filename,
                    "content_type": content_type,
                    "cid": upload.cid
                })
            
            # For binary files, return the file URL
            else:
                print(f"✅ Binary preview info served: {upload.filename}")
                return jsonify({
                    "type": "binary",
                    "url": f"/preview_file/{upload_id}",
                    "filename": upload.filename,
                    "content_type": content_type,
                    "cid": upload.cid
                })
                
        except requests.RequestException as e:
            print(f"❌ Preview content request failed: {str(e)}")
            return jsonify(error="failed to fetch file", detail=str(e)), 502
        except Exception as e:
            print(f"❌ Preview content failed: {str(e)}")
            return jsonify(error="preview failed", detail=str(e)), 500
        finally:
            db.close()

    @app.route('/download/<int:upload_id>')
    def download_by_id(upload_id):
        u = current_user()
        if not u:
            return "authentication required", 401
            
        db = db_session()
        try:
            up = db.query(Upload).filter_by(id=upload_id).first()
            if not up:
                print(f"❌ Download not found: upload_id={upload_id}")
                return "not found", 404
            if up.user_id != u.id:
                print(f"❌ Download forbidden: user {u.id} tried to download file owned by {up.user_id}")
                return "forbidden: not owner", 403
                
            print(f"📥 Download initiated: {up.filename} (CID: {up.cid})")
            return _proxy_stream_cid(up.cid, filename=up.filename)
        except Exception as e:
            print(f"❌ Download failed: {str(e)}")
            return f"download failed: {str(e)}", 500
        finally:
            db.close()

    @app.route('/download_by_cid/<cid>')
    def download_by_cid(cid):
        u = current_user()
        if not u:
            return "authentication required", 401
            
        db = db_session()
        try:
            up = db.query(Upload).filter_by(cid=cid, user_id=u.id).first()
            if not up:
                print(f"❌ Download by CID not found: CID={cid}, user_id={u.id}")
                return "not found or not owner", 404
                
            print(f"📥 Download by CID initiated: {up.filename} (CID: {up.cid})")
            return _proxy_stream_cid(cid, filename=up.filename)
        except Exception as e:
            print(f"❌ Download by CID failed: {str(e)}")
            return f"download failed: {str(e)}", 500
        finally:
            db.close()

    @app.route('/delete/<int:upload_id>', methods=['DELETE'])
    def delete_upload(upload_id):
        u = current_user()
        if not u:
            return jsonify(error="authentication required"), 401
            
        db = db_session()
        try:
            up = db.query(Upload).filter_by(id=upload_id, user_id=u.id).first()
            
            if not up:
                print(f"❌ Delete failed - file not found: upload_id={upload_id}, user_id={u.id}")
                return jsonify(error="file not found"), 404
                
            print(f"🗑️ Deleting file: {up.filename} (CID: {up.cid}, ID: {up.id})")
            db.delete(up)
            db.commit()
            
            print(f"✅ File deleted successfully: {up.filename}")
            return jsonify(success=True, message="File removed from your drive")
        except Exception as e:
            db.rollback()
            print(f"❌ Delete failed: {str(e)}")
            return jsonify(error=str(e)), 500
        finally:
            db.close()
        