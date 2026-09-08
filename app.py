import os
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jinja2

# ========================= Configuration =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    
    # Fix Render's postgres:// issue
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'database.db'))
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'resumes')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
    
    # Mail settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587) or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_USERNAME'))

app = Flask(__name__)
app.config.from_object(Config)

# ========================= Custom Jinja Loader =========================
template_dirs = [
    os.path.join(app.root_path, 'templates'),
    os.path.join(app.root_path, 'templates', 'careers'),
    os.path.join(app.root_path, 'templates', 'application'),
    os.path.join(app.root_path, 'templates', 'auth'),
    os.path.join(app.root_path, 'templates', 'admin'),
]
app.jinja_loader = jinja2.FileSystemLoader(template_dirs)

# ========================= Extensions =========================
db = SQLAlchemy(app)
mail = Mail(app)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ========================= Logging =========================
if not app.debug:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    app.logger.addHandler(stream_handler)
    app.logger.setLevel(logging.INFO)

# ========================= Models =========================
class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(50), default='bi-building')
    jobs = db.relationship('Job', backref='department', lazy=True)

class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    job_type = db.Column(db.String(50), default='Full-time')
    location = db.Column(db.String(100), default='Hawassa')
    experience = db.Column(db.String(50), default='1+ Years')
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='OPEN')  # OPEN, CLOSED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    applications = db.relationship('Application', backref='job', lazy=True)

class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    cover_letter = db.Column(db.Text, nullable=True)
    cv_filename = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), default='NEW')  # NEW, REVIEWED, SHORTLISTED, REJECTED
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ========================= Helper Functions =========================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Avoid overwriting by adding timestamp
        name, ext = os.path.splitext(filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        filename = f"{name}_{timestamp}{ext}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return filename
    return None

def send_application_notification(application, job):
    """Send email to HR when a new application is submitted."""
    if not app.config['MAIL_USERNAME']:
        return
    try:
        hr_email = os.environ.get('HR_EMAIL', app.config['MAIL_USERNAME'])
        msg = Message(
            subject=f"New Job Application: {job.title} - {application.full_name}",
            recipients=[hr_email],
            sender=app.config['MAIL_DEFAULT_SENDER']
        )
        msg.body = f"""
New Job Application

Candidate: {application.full_name}
Email: {application.email}
Phone: {application.phone}
Position: {job.title}
Cover Letter: {application.cover_letter or 'N/A'}

Please log in to the admin panel to view the full application and download the CV.
"""
        mail.send(msg)
        app.logger.info(f"Email notification sent for application #{application.id}")
    except Exception as e:
        app.logger.error(f"Email failed: {str(e)}")

# ========================= Admin Auth Decorator =========================
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in as admin to access this page.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ========================= Public Routes =========================
@app.route('/')
def home():
    jobs = Job.query.filter_by(status='OPEN').order_by(Job.created_at.desc()).limit(6).all()
    departments = Department.query.all()
    return render_template('home.html', jobs=jobs, departments=departments)

@app.route('/jobs')
def jobs():
    jobs_list = Job.query.filter_by(status='OPEN').order_by(Job.created_at.desc()).all()
    departments = Department.query.all()
    return render_template('jobs.html', jobs=jobs_list, departments=departments)

@app.route('/job/<int:job_id>')
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    return render_template('job_detail.html', job=job)

@app.route('/departments')
def departments():
    depts = Department.query.all()
    return render_template('departments.html', departments=depts)

@app.route('/locations')
def locations():
    return render_template('locations.html')

@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
def apply(job_id):
    job = Job.query.get_or_404(job_id)
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        cover_letter = request.form.get('cover_letter')
        cv_file = request.files.get('cv_file')

        # Validate required fields
        if not full_name or not email or not phone or not cv_file:
            flash('All fields including CV are required.', 'danger')
            return render_template('apply.html', job=job)

        cv_filename = save_uploaded_file(cv_file)
        if not cv_filename:
            flash('Invalid file format. Please upload PDF, DOC, or DOCX.', 'danger')
            return render_template('apply.html', job=job)

        application = Application(
            job_id=job.id,
            full_name=full_name,
            email=email,
            phone=phone,
            cover_letter=cover_letter,
            cv_filename=cv_filename
        )
        db.session.add(application)
        db.session.commit()

        # Send notification email
        send_application_notification(application, job)

        flash('Your application has been submitted successfully!', 'success')
        return redirect(url_for('jobs'))

    return render_template('apply.html', job=job)

# ========================= Admin Routes =========================
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_user_id'] = user.id
            flash('Logged in successfully.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    total_jobs = Job.query.count()
    total_applications = Application.query.count()
    recent_applications = Application.query.order_by(Application.applied_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
                           total_jobs=total_jobs,
                           total_applications=total_applications,
                           recent_applications=recent_applications)

@app.route('/admin/jobs/new', methods=['GET', 'POST'])
@admin_required
def admin_job_new():
    if request.method == 'POST':
        title = request.form.get('title')
        department_id = request.form.get('department_id')
        job_type = request.form.get('job_type')
        location = request.form.get('location')
        experience = request.form.get('experience')
        description = request.form.get('description')
        status = request.form.get('status', 'OPEN')

        if not title:
            flash('Job title is required.', 'danger')
            return render_template('admin/job_form.html', departments=Department.query.all())

        job = Job(
            title=title,
            department_id=department_id if department_id else None,
            job_type=job_type,
            location=location,
            experience=experience,
            description=description,
            status=status
        )
        db.session.add(job)
        db.session.commit()
        flash('Job posted successfully.', 'success')
        return redirect(url_for('admin_dashboard'))

    departments = Department.query.all()
    return render_template('admin/job_form.html', departments=departments)

@app.route('/admin/jobs/delete/<int:job_id>', methods=['POST'])
@admin_required
def admin_job_delete(job_id):
    job = Job.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    flash('Job deleted.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/candidates')
@admin_required
def admin_candidates():
    applications = Application.query.order_by(Application.applied_at.desc()).all()
    return render_template('admin/candidates.html', applications=applications)

@app.route('/admin/candidates/download/<int:app_id>')
@admin_required
def admin_cv_download(app_id):
    application = Application.query.get_or_404(app_id)
    if not application.cv_filename:
        flash('No CV uploaded for this application.', 'warning')
        return redirect(url_for('admin_candidates'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], application.cv_filename, as_attachment=True)

# ========================= Error Handlers =========================
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    db.session.rollback()
    app.logger.error(f'500 error: {e}')
    return render_template('500.html'), 500

# ========================= Database Initialization & Default Admin =========================
def init_db():
    with app.app_context():
        db.create_all()
        # Create default admin if none exists
        if User.query.count() == 0:
            admin = User(username='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            app.logger.info("Default admin created: admin / admin123")

        # Seed departments if empty
        if Department.query.count() == 0:
            depts = [
                {'name': 'Front Office', 'icon': 'bi-door-open-fill'},
                {'name': 'Housekeeping', 'icon': 'bi-stars'},
                {'name': 'Food & Beverage', 'icon': 'bi-cup-hot-fill'},
                {'name': 'Kitchen', 'icon': 'bi-fire'},
                {'name': 'Engineering', 'icon': 'bi-tools'},
                {'name': 'Finance', 'icon': 'bi-cash-stack'},
                {'name': 'Human Resources', 'icon': 'bi-people-fill'},
                {'name': 'IT', 'icon': 'bi-cpu-fill'},
                {'name': 'Security', 'icon': 'bi-shield-lock-fill'},
                {'name': 'Spa & Wellness', 'icon': 'bi-flower1'},
                {'name': 'Sales & Marketing', 'icon': 'bi-graph-up-arrow'},
                {'name': 'Procurement', 'icon': 'bi-box-seam-fill'},
                {'name': 'Maintenance', 'icon': 'bi-tools'}
            ]
            for d in depts:
                db.session.add(Department(name=d['name'], icon=d['icon']))
            db.session.commit()
            app.logger.info('Departments seeded.')

        # Seed sample job if none
        if Job.query.count() == 0:
            dept = Department.query.first()
            sample = Job(
                title='Front Office Supervisor',
                department_id=dept.id if dept else None,
                job_type='Full-time',
                location='Hawassa',
                experience='2+ Years',
                description='Oversee reception operations and ensure guest satisfaction.',
                status='OPEN'
            )
            db.session.add(sample)
            db.session.commit()
            app.logger.info('Sample job seeded.')

# ========================= Run Application =========================
# Initialize DB on startup (for Render/Gunicorn)
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)