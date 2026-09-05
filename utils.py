import os
from datetime import datetime
from flask import current_app, request, session
from werkzeug.utils import secure_filename
from flask_mail import Message

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_IMAGE_EXTENSIONS']

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        filename = f"{name}_{timestamp}{ext}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        return filename
    return None

def save_job_image(file):
    if file and file.filename != '' and allowed_image_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        filename = f"{name}_{timestamp}{ext}"
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER_JOBS'], filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        return filename
    return None

def log_audit(action, description=None, target_type=None, target_id=None):
    from app import AuditLog, db  # Import here to avoid circular import
    log = AuditLog(
        user_id=session.get('admin_id'),
        user_name=session.get('admin_username', 'system'),
        action=action,
        description=description,
        target_type=target_type,
        target_id=target_id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    db.session.add(log)
    db.session.commit()
    return log

def send_application_status_email(application, old_status, new_status, notes=""):
    from app import mail, url_for  # Avoid circular import
    if not current_app.config['MAIL_USERNAME']:
        return
    messages = {
        'SHORTLISTED': 'Congratulations! You have been shortlisted for an interview.',
        'INTERVIEW': 'An interview has been scheduled for you.',
        'SELECTED': 'Congratulations! You have been selected for the position.',
        'HIRED': 'Congratulations! You have been hired.',
        'REJECTED': 'We regret to inform you that your application was not successful.'
    }
    try:
        msg = Message(
            subject=f'Rori Hotel - Application Status: {new_status}',
            recipients=[application.email]
        )
        msg.html = f"""
        <div style="font-family: 'Cormorant Garamond', serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #C5A059;">
            <h2 style="color: #0B132B;">Rori Hotel</h2>
            <div style="background: #F8F9FA; padding: 20px; border-radius: 12px;">
                <p>Dear <strong>{application.full_name}</strong>,</p>
                <p>{messages.get(new_status, 'Your application status has been updated.')}</p>
                <p><strong>Position:</strong> {application.job.title}</p>
                <p><strong>Status:</strong> {new_status}</p>
                {f'<p><strong>Note:</strong> {notes}</p>' if notes else ''}
                <a href="{url_for('application_status', app_id=application.id, _external=True)}" 
                   style="background: #C5A059; color: white; padding: 10px 25px; text-decoration: none; border-radius: 30px; display: inline-block;">
                   Track Application
                </a>
            </div>
            <p style="color: #6C757D; font-size: 12px;">© 2026 Rori Hotel. All rights reserved.</p>
        </div>
        """
        mail.send(msg)
    except Exception as e:
        print(f"Email failed: {e}")

def get_similar_jobs(job, limit=3):
    from app import Job, db
    similar = Job.query.filter(
        Job.is_active == True,
        Job.id != job.id,
        db.or_(
            Job.department_id == job.department_id,
            Job.employment_type == job.employment_type
        )
    ).limit(limit).all()
    return similar
