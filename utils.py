import os
import uuid
from datetime import datetime
from flask import current_app, request, session
from werkzeug.utils import secure_filename
from flask_mail import Message


def allowed_file(filename: str) -> bool:
    """ለአመልካቾች CV እና ሰነዶች የተፈቀዱ የፋይል አይነቶችን ያረጋግጣል።"""
    return (
        '.' in filename and 
        filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_EXTENSIONS', {'pdf', 'doc', 'docx'})
    )


def allowed_image_file(filename: str) -> bool:
    """ለሥራ ማስታወቂያዎች የተፈቀዱ የምስል አይነቶችን ያረጋግጣል።"""
    return (
        '.' in filename and 
        filename.rsplit('.', 1)[1].lower() in current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', {'jpg', 'jpeg', 'png', 'webp'})
    )


def save_uploaded_file(file) -> str | None:
    """የአመልካቾችን CV/ሰነዶች ደህንነቱ በተጠበቀ ስም ያስቀምጣል።"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        
        # Unique Filename (Timestamp + UUID Short Hex)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_id = uuid.uuid4().hex[:6]
        filename = f"{name}_{timestamp}_{unique_id}{ext}"
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        return filename
    return None


def save_job_image(file) -> str | None:
    """የሥራ ማስታወቂያ ምስሎችን ደህንነቱ በተጠበቀ ሁኔታ ያስቀምጣል።"""
    if file and file.filename != '' and allowed_image_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_id = uuid.uuid4().hex[:6]
        filename = f"{name}_{timestamp}_{unique_id}{ext}"
        
        upload_folder = current_app.config['UPLOAD_FOLDER_JOBS']
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        return filename
    return None


def log_audit(action: str, description: str = None, target_type: str = None, target_id: int = None):
    """የአድሚን እና የሲስተም ክንውኖችን ኦዲት ሎግ ላይ ይመዘግባል።"""
    from app import AuditLog, db  # Circular import ለመከላከል
    
    # Real IP extraction (Proxy Support)
    ip_addr = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_addr and ',' in ip_addr:
        ip_addr = ip_addr.split(',')[0].strip()

    log = AuditLog(
        user_id=session.get('admin_id'),
        user_name=session.get('admin_username', 'System'),
        action=action,
        description=description,
        target_type=target_type,
        target_id=target_id,
        ip_address=ip_addr,
        user_agent=request.headers.get('User-Agent')
    )
    db.session.add(log)
    db.session.commit()
    return log


def send_application_status_email(application, old_status: str, new_status: str, notes: str = ""):
    """የአመልካቹን የሥራ ማመልከቻ ደረጃ ለውጥ በሚያምር Luxury Gold/Navy HTML ኢሜይል ይልካል።"""
    from app import mail, url_for  # Circular import ለመከላከል
    
    if not current_app.config.get('MAIL_USERNAME'):
        current_app.logger.warning("Mail username is not configured. Email not sent.")
        return

    messages = {
        'SHORTLISTED': 'Congratulations! Your profile has been shortlisted for an upcoming interview process.',
        'INTERVIEW': 'An interview session has been scheduled for your application.',
        'SELECTED': 'Congratulations! You have been selected for the position.',
        'HIRED': 'Welcome to the team! Your hiring process is complete.',
        'REJECTED': 'Thank you for your application. After careful consideration, we will not be moving forward at this time.'
    }
    
    status_message = messages.get(new_status, 'Your application status has been updated.')
    tracking_url = url_for('application_status', app_id=application.id, _external=True)

    try:
        msg = Message(
            subject=f'Rori Hotel Careers - Application Update: {new_status}',
            recipients=[application.email]
        )
        
        # Luxury Dark/Gold Email Template
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #0B132B; margin: 0; padding: 20px; color: #FFFFFF; }}
                .email-container {{ max-width: 600px; margin: 0 auto; background: #111C38; border: 1px solid #C5A059; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
                .header {{ background: #0B132B; padding: 30px 20px; text-align: center; border-bottom: 2px solid #C5A059; }}
                .header h1 {{ margin: 0; font-family: Georgia, serif; color: #C5A059; font-size: 26px; letter-spacing: 2px; text-transform: uppercase; }}
                .header p {{ margin: 5px 0 0 0; color: #8A99AD; font-size: 12px; letter-spacing: 1px; text-transform: uppercase; }}
                .content {{ padding: 35px 30px; line-height: 1.6; color: #E2E8F0; }}
                .status-badge {{ display: inline-block; background: rgba(197, 160, 89, 0.15); color: #C5A059; border: 1px solid #C5A059; padding: 6px 16px; border-radius: 50px; font-weight: bold; font-size: 13px; margin-bottom: 20px; }}
                .btn-track {{ display: inline-block; background: #C5A059; color: #0B132B !important; text-decoration: none; padding: 12px 28px; border-radius: 50px; font-weight: bold; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; margin-top: 25px; }}
                .note-box {{ background: rgba(255, 255, 255, 0.04); border-left: 3px solid #C5A059; padding: 12px 15px; margin: 20px 0; border-radius: 4px; font-size: 14px; color: #CBD5E1; }}
                .footer {{ background: #080D1F; padding: 20px; text-align: center; font-size: 12px; color: #64748B; border-top: 1px solid rgba(197, 160, 89, 0.2); }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <h1>RORI HOTEL</h1>
                    <p>Hawassa, Ethiopia • Human Resources</p>
                </div>
                <div class="content">
                    <span class="status-badge">{new_status}</span>
                    <p style="font-size: 16px;">Dear <strong>{application.full_name}</strong>,</p>
                    <p>{status_message}</p>
                    
                    <div style="background: rgba(255, 255, 255, 0.02); border: 1px solid rgba(197, 160, 89, 0.3); border-radius: 12px; padding: 15px; margin: 20px 0;">
                        <p style="margin: 3px 0; font-size: 14px;"><strong>Position:</strong> {application.job.title}</p>
                        <p style="margin: 3px 0; font-size: 14px;"><strong>Reference No:</strong> #{getattr(application, 'reference_no', f'RORI-{application.id:04d}')}</p>
                    </div>

                    {f'<div class="note-box"><strong>HR Note:</strong> {notes}</div>' if notes else ''}

                    <div style="text-align: center;">
                        <a href="{tracking_url}" class="btn-track">Track Application Status</a>
                    </div>
                </div>
                <div class="footer">
                    <p>© 2026 Rori Hotel Hawassa. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """
        mail.send(msg)
    except Exception as e:
        current_app.logger.error(f"Failed to send application status email to {application.email}: {e}")


def get_similar_jobs(job, limit: int = 3):
    """ተመሳሳይ የሥራ ዘርፍ ያላቸውን ክፍት የሥራ ቦታዎች ይፈልጋል።"""
    from app import Job, db
    
    return Job.query.filter(
        Job.is_active == True,
        Job.id != job.id,
        db.or_(
            Job.department_id == job.department_id,
            Job.employment_type == job.employment_type
        )
    ).limit(limit).all()
