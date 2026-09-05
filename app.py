import os
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, DateField, FileField, BooleanField, PasswordField, IntegerField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import secrets

# ========================= Configuration =========================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'database.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'resumes')
    UPLOAD_FOLDER_JOBS = os.path.join(BASE_DIR, 'static', 'uploads', 'jobs')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    HR_USERNAME = os.environ.get('HR_USERNAME', 'admin')
    HR_PASSWORD_HASH = os.environ.get('HR_PASSWORD_HASH') or generate_password_hash(
        os.environ.get('HR_PASSWORD', 'RoriHR2026')
    )
    # Mail settings (for notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@rorihotel.com')

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
mail = Mail(app)

# Ensure upload directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER_JOBS'], exist_ok=True)

# ========================= Models =========================

class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    icon = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    jobs = db.relationship('Job', backref='department_ref', lazy=True)

    def __repr__(self):
        return f'<Department {self.name}>'

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    address = db.Column(db.String(200), nullable=True)
    jobs = db.relationship('Job', backref='location_ref', lazy=True)

    def __repr__(self):
        return f'<Location {self.name}>'

class Job(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    short_description = db.Column(db.String(200), nullable=False)
    full_description = db.Column(db.Text, nullable=False)
    responsibilities = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text, nullable=False)
    what_we_offer = db.Column(db.Text, nullable=False)
    employment_type = db.Column(db.String(30), nullable=False, default='Full-time')
    experience_level = db.Column(db.String(30), nullable=True)
    salary_range = db.Column(db.String(100), nullable=True)
    deadline = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_featured = db.Column(db.Boolean, default=False)
    banner_image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    applications = db.relationship('Application', backref='job', lazy=True)

    def responsibilities_list(self):
        return [r.strip() for r in self.responsibilities.split('\n') if r.strip()]

    def requirements_list(self):
        return [r.strip() for r in self.requirements.split('\n') if r.strip()]

    def what_we_offer_list(self):
        return [r.strip() for r in self.what_we_offer.split('\n') if r.strip()]

    @property
    def department_name(self):
        return self.department_ref.name if self.department_ref else None

    @property
    def location_name(self):
        return self.location_ref.name if self.location_ref else None

    @property
    def is_expired(self):
        if self.deadline and self.deadline < datetime.utcnow().date():
            return True
        return False

    def __repr__(self):
        return f'<Job {self.title}>'

class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    education = db.Column(db.String(60), nullable=False)
    years_of_experience = db.Column(db.String(30), nullable=False)
    current_position = db.Column(db.String(120), nullable=True)
    previous_employer = db.Column(db.String(120), nullable=True)
    skills = db.Column(db.String(255), nullable=False)
    languages = db.Column(db.String(255), nullable=False)
    certifications = db.Column(db.String(255), nullable=True)
    availability_date = db.Column(db.Date, nullable=True)
    willing_to_relocate = db.Column(db.String(10), nullable=True)
    expected_salary = db.Column(db.String(50), nullable=True)
    cover_letter = db.Column(db.Text, nullable=False)
    cv_filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(30), default='NEW')
    status_updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(255), nullable=True)          # Comma-separated
    reviewed_by = db.Column(db.String(120), nullable=True)
    shortlisted_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    viewed_at = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Application {self.full_name} for {self.job.title}>'

class TalentPool(db.Model):
    __tablename__ = 'talent_pool'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    phone = db.Column(db.String(30), nullable=False)
    location = db.Column(db.String(120), nullable=False)
    education = db.Column(db.String(60), nullable=False)
    years_of_experience = db.Column(db.String(30), nullable=False)
    skills = db.Column(db.String(255), nullable=False)
    languages = db.Column(db.String(255), nullable=False)
    certifications = db.Column(db.String(255), nullable=True)
    availability_date = db.Column(db.Date, nullable=True)
    willing_to_relocate = db.Column(db.String(10), nullable=True)
    expected_salary = db.Column(db.String(50), nullable=True)
    cover_letter = db.Column(db.Text, nullable=False)
    cv_filename = db.Column(db.String(255), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TalentPool {self.full_name}>'

class Interview(db.Model):
    __tablename__ = 'interviews'
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    interview_type = db.Column(db.String(50), default='In-person')
    interviewer_name = db.Column(db.String(120), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    evaluation = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    decision = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(30), default='Scheduled')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    application = db.relationship('Application', backref='interviews', lazy=True)

    def __repr__(self):
        return f'<Interview for Application {self.application_id}>'

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    recipient = db.Column(db.String(120), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Notification {self.title}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    user_name = db.Column(db.String(120), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    target_type = db.Column(db.String(100), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<AuditLog {self.user_name} - {self.action}>'

# ========================= Forms =========================

class ApplicationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=30)])
    location = StringField('Current Location', validators=[DataRequired(), Length(max=120)])
    education = SelectField('Highest Education Level', choices=[
        ('High School', 'High School Diploma'),
        ('Technical Diploma', 'TVET / Advanced Diploma'),
        ('Bachelor Degree', "Bachelor's Degree"),
        ('Master Degree', "Master's Degree / Doctorate")
    ], validators=[DataRequired()])
    years_of_experience = StringField('Years of Experience', validators=[DataRequired(), Length(max=30)])
    current_position = StringField('Current Position', validators=[Optional(), Length(max=120)])
    previous_employer = StringField('Previous Employer', validators=[Optional(), Length(max=120)])
    skills = StringField('Key Skills (comma separated)', validators=[DataRequired(), Length(max=255)])
    languages = StringField('Languages Spoken', validators=[DataRequired(), Length(max=255)])
    certifications = StringField('Professional Certifications', validators=[Optional(), Length(max=255)])
    availability_date = DateField('Earliest Availability Date', validators=[Optional()], format='%Y-%m-%d')
    willing_to_relocate = SelectField('Willing to Relocate?', choices=[('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    expected_salary = StringField('Expected Monthly Salary (ETB)', validators=[Optional(), Length(max=50)])
    cover_letter = TextAreaField('Cover Letter / Brief Pitch', validators=[DataRequired()])
    cv_file = FileField('Upload CV (PDF, DOC, DOCX)', validators=[DataRequired()])

class TalentPoolForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField('Phone', validators=[DataRequired(), Length(max=30)])
    location = StringField('Current Location', validators=[DataRequired(), Length(max=120)])
    education = SelectField('Highest Education Level', choices=[
        ('High School', 'High School Diploma'),
        ('Technical Diploma', 'TVET / Advanced Diploma'),
        ('Bachelor Degree', "Bachelor's Degree"),
        ('Master Degree', "Master's Degree / Doctorate")
    ], validators=[DataRequired()])
    years_of_experience = StringField('Years of Experience', validators=[DataRequired(), Length(max=30)])
    skills = StringField('Key Skills (comma separated)', validators=[DataRequired(), Length(max=255)])
    languages = StringField('Languages Spoken', validators=[DataRequired(), Length(max=255)])
    certifications = StringField('Professional Certifications', validators=[Optional(), Length(max=255)])
    availability_date = DateField('Earliest Availability Date', validators=[Optional()], format='%Y-%m-%d')
    willing_to_relocate = SelectField('Willing to Relocate?', choices=[('Yes', 'Yes'), ('No', 'No')], validators=[DataRequired()])
    expected_salary = StringField('Expected Monthly Salary (ETB)', validators=[Optional(), Length(max=50)])
    cover_letter = TextAreaField('Cover Letter / Brief Pitch', validators=[DataRequired()])
    cv_file = FileField('Upload CV (PDF, DOC, DOCX)', validators=[DataRequired()])

class JobForm(FlaskForm):
    title = StringField('Job Title', validators=[DataRequired(), Length(max=120)])
    department_id = SelectField('Department', coerce=int, validators=[Optional()])
    location_id = SelectField('Location', coerce=int, validators=[Optional()])
    short_description = StringField('Short Description', validators=[DataRequired(), Length(max=200)])
    full_description = TextAreaField('Full Description', validators=[DataRequired()])
    responsibilities = TextAreaField('Responsibilities (one per line)', validators=[DataRequired()])
    requirements = TextAreaField('Requirements (one per line)', validators=[DataRequired()])
    what_we_offer = TextAreaField('What We Offer (one per line)', validators=[DataRequired()])
    employment_type = SelectField('Employment Type', choices=[
        ('Full-time', 'Full-time'),
        ('Part-time', 'Part-time'),
        ('Contract', 'Contract')
    ], validators=[DataRequired()])
    experience_level = StringField('Experience Level', validators=[Optional(), Length(max=30)])
    salary_range = StringField('Salary Range', validators=[Optional(), Length(max=100)])
    deadline = DateField('Application Deadline', validators=[Optional()], format='%Y-%m-%d')
    is_active = BooleanField('Active', default=True)
    is_featured = BooleanField('Featured', default=False)

class AdminLoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class InterviewForm(FlaskForm):
    application_id = SelectField('Candidate', coerce=int, validators=[DataRequired()])
    scheduled_at = StringField('Scheduled Date/Time', validators=[DataRequired()])  # Expect ISO format
    duration_minutes = IntegerField('Duration (minutes)', default=30, validators=[NumberRange(min=5, max=120)])
    interview_type = SelectField('Type', choices=[
        ('In-person', 'In-person'),
        ('Virtual', 'Virtual'),
        ('Phone', 'Phone')
    ], default='In-person')
    interviewer_name = StringField('Interviewer Name', validators=[Optional(), Length(max=120)])
    location = StringField('Location/Meeting Link', validators=[Optional(), Length(max=200)])
    notes = TextAreaField('Notes', validators=[Optional()])

# ========================= Helper Functions =========================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def allowed_image_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_IMAGE_EXTENSIONS']

def save_uploaded_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        filename = f"{name}_{timestamp}{ext}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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
        file_path = os.path.join(app.config['UPLOAD_FOLDER_JOBS'], filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        return filename
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in as admin to access this page.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def log_audit(action, description=None, target_type=None, target_id=None):
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
    if not app.config['MAIL_USERNAME']:
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
    similar = Job.query.filter(
        Job.is_active == True,
        Job.id != job.id,
        db.or_(
            Job.department_id == job.department_id,
            Job.employment_type == job.employment_type
        )
    ).limit(limit).all()
    return similar

# ========================= Context Processors =========================

@app.context_processor
def inject_now():
    return {'now': datetime.utcnow}

@app.context_processor
def inject_departments_and_locations():
    depts = Department.query.all()
    locs = Location.query.all()
    return dict(all_departments=depts, all_locations=locs)

# ========================= Public Routes =========================

@app.route('/')
def home():
    featured_jobs = Job.query.filter_by(is_active=True, is_featured=True).order_by(Job.created_at.desc()).limit(6).all()
    latest_jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).limit(3).all()
    departments = Department.query.all()
    return render_template('careers/home.html',
                           featured_jobs=featured_jobs,
                           latest_jobs=latest_jobs,
                           departments=departments)

@app.route('/jobs')
def jobs():
    department_id = request.args.get('department', type=int)
    location_id = request.args.get('location', type=int)
    type_filter = request.args.get('type')
    experience_filter = request.args.get('experience')
    search_query = request.args.get('q')

    query = Job.query.filter_by(is_active=True)
    if department_id:
        query = query.filter_by(department_id=department_id)
    if location_id:
        query = query.filter_by(location_id=location_id)
    if type_filter:
        query = query.filter_by(employment_type=type_filter)
    if experience_filter:
        query = query.filter_by(experience_level=experience_filter)
    if search_query:
        query = query.filter(Job.title.contains(search_query) | Job.short_description.contains(search_query))
    jobs_list = query.order_by(Job.created_at.desc()).all()
    departments = Department.query.all()
    locations = Location.query.all()
    return render_template('careers/jobs.html', jobs=jobs_list, departments=departments, locations=locations)

@app.route('/job/<int:job_id>')
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    similar_jobs = get_similar_jobs(job)
    return render_template('careers/job_detail.html', job=job, similar_jobs=similar_jobs)

@app.route('/departments')
def departments():
    depts = Department.query.all()
    return render_template('careers/departments.html', departments=depts)

@app.route('/department/<int:dept_id>')
def department_detail(dept_id):
    dept = Department.query.get_or_404(dept_id)
    jobs = Job.query.filter_by(department_id=dept_id, is_active=True).all()
    return render_template('careers/department_detail.html', department=dept, jobs=jobs)

@app.route('/locations')
def locations():
    locs = Location.query.all()
    return render_template('careers/locations.html', locations=locs)

@app.route('/about-careers')
def about_careers():
    return render_template('careers/about_careers.html')

@app.route('/application/lookup', methods=['GET'])
def application_lookup():
    applicant_id = request.args.get('applicant_id')
    if not applicant_id:
        flash('Please enter your application ID.', 'warning')
        return redirect(url_for('home'))
    try:
        app_id = int(applicant_id)
        application = Application.query.get_or_404(app_id)
        return redirect(url_for('application_status', app_id=application.id))
    except ValueError:
        flash('Invalid application ID format. Please enter a number.', 'danger')
        return redirect(url_for('home'))

@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
def apply(job_id):
    job = Job.query.get_or_404(job_id)
    form = ApplicationForm()
    if form.validate_on_submit():
        cv_filename = save_uploaded_file(form.cv_file.data)
        if not cv_filename:
            flash('Invalid file format. Please upload PDF, DOC, or DOCX.', 'danger')
            return render_template('application/apply.html', form=form, job=job)

        application = Application(
            job_id=job.id,
            full_name=form.full_name.data,
            email=form.email.data,
            phone=form.phone.data,
            location=form.location.data,
            education=form.education.data,
            years_of_experience=form.years_of_experience.data,
            current_position=form.current_position.data,
            previous_employer=form.previous_employer.data,
            skills=form.skills.data,
            languages=form.languages.data,
            certifications=form.certifications.data,
            availability_date=form.availability_date.data,
            willing_to_relocate=form.willing_to_relocate.data,
            expected_salary=form.expected_salary.data,
            cover_letter=form.cover_letter.data,
            cv_filename=cv_filename
        )
        db.session.add(application)
        db.session.commit()

        # Create notification
        notif = Notification(
            title=f'New Application: {application.full_name}',
            message=f'{application.full_name} applied for {job.title}.',
            recipient='admin'
        )
        db.session.add(notif)
        db.session.commit()

        flash('Your application has been submitted successfully!', 'success')
        return redirect(url_for('application_success', app_id=application.id))
    return render_template('application/apply.html', form=form, job=job)

@app.route('/application/success/<int:app_id>')
def application_success(app_id):
    application = Application.query.get_or_404(app_id)
    return render_template('application/success.html', application=application)

@app.route('/application/status/<int:app_id>')
def application_status(app_id):
    application = Application.query.get_or_404(app_id)
    if not application.viewed_at:
        application.viewed_at = datetime.utcnow()
        db.session.commit()
    job = application.job
    return render_template('application/application_status.html', application=application, job=job)

@app.route('/talent-pool', methods=['GET', 'POST'])
def talent_pool():
    form = TalentPoolForm()
    if form.validate_on_submit():
        cv_filename = save_uploaded_file(form.cv_file.data)
        if not cv_filename:
            flash('Invalid file format. Please upload PDF, DOC, or DOCX.', 'danger')
            return render_template('application/talent_pool.html', form=form)

        existing = TalentPool.query.filter_by(email=form.email.data).first()
        if existing:
            flash('You have already joined the talent pool with this email.', 'warning')
            return redirect(url_for('talent_pool'))

        talent = TalentPool(
            full_name=form.full_name.data,
            email=form.email.data,
            phone=form.phone.data,
            location=form.location.data,
            education=form.education.data,
            years_of_experience=form.years_of_experience.data,
            skills=form.skills.data,
            languages=form.languages.data,
            certifications=form.certifications.data,
            availability_date=form.availability_date.data,
            willing_to_relocate=form.willing_to_relocate.data,
            expected_salary=form.expected_salary.data,
            cover_letter=form.cover_letter.data,
            cv_filename=cv_filename
        )
        db.session.add(talent)
        db.session.commit()
        flash('You have successfully joined the Rori Hotel Talent Pool!', 'success')
        return redirect(url_for('home'))
    return render_template('application/talent_pool.html', form=form)

# ========================= Admin Auth =========================

@app.route('/auth/login', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    form = AdminLoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        if username == app.config['HR_USERNAME'] and check_password_hash(app.config['HR_PASSWORD_HASH'], password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['admin_id'] = 1  # For audit log; set to actual ID if you have a User model
            flash('Logged in successfully.', 'success')
            log_audit('Login', f'Admin {username} logged in.')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials.', 'danger')
    return render_template('auth/login.html', form=form)

@app.route('/auth/logout')
def admin_logout():
    username = session.get('admin_username', 'Unknown')
    log_audit('Logout', f'Admin {username} logged out.')
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    session.pop('admin_id', None)
    flash('Logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/auth/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        flash('If an account exists with that email, we will send a reset link.', 'info')
        return redirect(url_for('admin_login'))
    return render_template('auth/forgot_password.html')

# ========================= Admin Dashboard =========================

@app.route('/admin')
@admin_required
def admin_dashboard():
    total_jobs = Job.query.count()
    active_jobs = Job.query.filter_by(is_active=True).count()
    total_applications = Application.query.count()
    total_interviews = Interview.query.count()
    recent_applications = Application.query.order_by(Application.submitted_at.desc()).limit(10).all()
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(5).all()
    status_counts = {}
    for status in ['NEW', 'UNDER REVIEW', 'SHORTLISTED', 'INTERVIEW', 'SELECTED', 'HIRED', 'REJECTED']:
        status_counts[status] = Application.query.filter_by(status=status).count()
    return render_template('admin/dashboard.html',
                           total_jobs=total_jobs,
                           active_jobs=active_jobs,
                           total_applications=total_applications,
                           total_interviews=total_interviews,
                           recent_applications=recent_applications,
                           notifications=notifications,
                           status_counts=status_counts)

@app.route('/admin/candidates')
@admin_required
def admin_candidates():
    query = Application.query
    search = request.args.get('search')
    if search:
        query = query.filter(
            db.or_(
                Application.full_name.contains(search),
                Application.email.contains(search)
            )
        )
    status_filter = request.args.get('status')
    if status_filter and status_filter != 'ALL':
        query = query.filter_by(status=status_filter)
    tag_filter = request.args.get('tag')
    if tag_filter:
        query = query.filter(Application.tags.contains(tag_filter))
    dept_filter = request.args.get('department')
    if dept_filter:
        query = query.join(Job).filter(Job.department_id == dept_filter)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        query = query.filter(Application.submitted_at >= date_from)
    if date_to:
        query = query.filter(Application.submitted_at <= date_to + ' 23:59:59')

    applications = query.order_by(Application.submitted_at.desc()).all()

    all_tags = set()
    for app in Application.query.all():
        if app.tags:
            for tag in app.tags.split(','):
                all_tags.add(tag.strip())
    departments = Department.query.all()
    statuses = ['NEW', 'UNDER REVIEW', 'SHORTLISTED', 'INTERVIEW', 'SELECTED', 'HIRED', 'REJECTED']
    return render_template('admin/candidates.html',
                           applications=applications,
                           all_tags=sorted(all_tags),
                           departments=departments,
                           statuses=statuses)

@app.route('/admin/candidate/<int:app_id>')
@admin_required
def admin_candidate_detail(app_id):
    application = Application.query.get_or_404(app_id)
    interviews = Interview.query.filter_by(application_id=app_id).all()
    return render_template('admin/candidate_detail.html', application=application, interviews=interviews)

@app.route('/admin/application/<int:app_id>/action', methods=['POST'])
@admin_required
def admin_application_action():
    app_id = request.form.get('app_id', type=int)
    action = request.form.get('action')
    notes = request.form.get('notes', '')
    application = Application.query.get_or_404(app_id)
    old_status = application.status
    new_status = old_status

    if action == 'shortlist':
        new_status = 'SHORTLISTED'
        application.shortlisted_at = datetime.utcnow()
    elif action == 'reject':
        new_status = 'REJECTED'
        application.rejected_at = datetime.utcnow()
    elif action == 'interview':
        # Redirect to interview scheduling with pre-selected application
        flash('Please schedule the interview.', 'info')
        return redirect(url_for('admin_interview_new', application_id=app_id))
    elif action == 'select':
        new_status = 'SELECTED'
    elif action == 'hire':
        new_status = 'HIRED'
    elif action == 'update_notes':
        application.notes = notes
        db.session.commit()
        log_audit('Updated Notes', f'Updated notes for {application.full_name}', 'Application', app_id)
        flash('Notes updated.', 'success')
        return redirect(request.referrer)
    else:
        flash('Unknown action.', 'danger')
        return redirect(request.referrer)

    application.status = new_status
    application.status_updated_at = datetime.utcnow()
    if notes and action != 'update_notes':
        application.notes = (application.notes or '') + f'\n[{datetime.utcnow().strftime("%Y-%m-%d")}] {notes}'
    application.reviewed_by = session.get('admin_username')
    db.session.commit()

    log_audit(f'Status Update: {new_status}',
              f'Changed {application.full_name} from {old_status} to {new_status}',
              'Application', app_id)
    send_application_status_email(application, old_status, new_status, notes)

    flash(f'Status of {application.full_name} updated to {new_status}.', 'success')
    return redirect(request.referrer or url_for('admin_candidates'))

@app.route('/admin/application/<int:app_id>/tags', methods=['POST'])
@admin_required
def admin_update_tags(app_id):
    application = Application.query.get_or_404(app_id)
    tags = request.form.get('tags', '').strip()
    clean_tags = ','.join([t.strip() for t in tags.split(',') if t.strip()])
    application.tags = clean_tags if clean_tags else None
    db.session.commit()
    log_audit('Updated Tags', f'Tags for {application.full_name}: {clean_tags}', 'Application', app_id)
    flash('Tags updated.', 'success')
    return redirect(request.referrer)

@app.route('/admin/candidate/<int:app_id>/cv/download')
@admin_required
def admin_cv_download(app_id):
    application = Application.query.get_or_404(app_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], application.cv_filename, as_attachment=True)

@app.route('/admin/candidate/<int:app_id>/cv/preview')
@admin_required
def admin_cv_preview(app_id):
    application = Application.query.get_or_404(app_id)
    return send_from_directory(app.config['UPLOAD_FOLDER'], application.cv_filename, as_attachment=False)

@app.route('/admin/jobs')
@admin_required
def admin_jobs():
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('admin/jobs.html', jobs=jobs)

@app.route('/admin/job/new', methods=['GET', 'POST'])
@admin_required
def admin_job_new():
    form = JobForm()
    form.department_id.choices = [(d.id, d.name) for d in Department.query.all()]
    form.department_id.choices.insert(0, (0, 'None'))
    form.location_id.choices = [(l.id, l.name) for l in Location.query.all()]
    form.location_id.choices.insert(0, (0, 'None'))

    if form.validate_on_submit():
        banner_image = None
        if 'banner_image' in request.files:
            file = request.files['banner_image']
            if file and file.filename != '':
                banner_image = save_job_image(file)

        job = Job(
            title=form.title.data,
            department_id=form.department_id.data if form.department_id.data != 0 else None,
            location_id=form.location_id.data if form.location_id.data != 0 else None,
            short_description=form.short_description.data,
            full_description=form.full_description.data,
            responsibilities=form.responsibilities.data,
            requirements=form.requirements.data,
            what_we_offer=form.what_we_offer.data,
            employment_type=form.employment_type.data,
            experience_level=form.experience_level.data,
            salary_range=form.salary_range.data,
            deadline=form.deadline.data,
            is_active=form.is_active.data,
            is_featured=form.is_featured.data,
            banner_image=banner_image
        )
        db.session.add(job)
        db.session.commit()
        log_audit('Created Job', f'Created job: {job.title}', 'Job', job.id)
        flash('Job created successfully!', 'success')
        return redirect(url_for('admin_jobs'))
    return render_template('admin/job_form.html', form=form, is_new=True)

@app.route('/admin/job/<int:job_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_job_edit(job_id):
    job = Job.query.get_or_404(job_id)
    form = JobForm(obj=job)
    form.department_id.choices = [(d.id, d.name) for d in Department.query.all()]
    form.department_id.choices.insert(0, (0, 'None'))
    form.location_id.choices = [(l.id, l.name) for l in Location.query.all()]
    form.location_id.choices.insert(0, (0, 'None'))

    if form.validate_on_submit():
        if 'banner_image' in request.files:
            file = request.files['banner_image']
            if file and file.filename != '':
                if job.banner_image:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER_JOBS'], job.banner_image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                job.banner_image = save_job_image(file)

        job.title = form.title.data
        job.department_id = form.department_id.data if form.department_id.data != 0 else None
        job.location_id = form.location_id.data if form.location_id.data != 0 else None
        job.short_description = form.short_description.data
        job.full_description = form.full_description.data
        job.responsibilities = form.responsibilities.data
        job.requirements = form.requirements.data
        job.what_we_offer = form.what_we_offer.data
        job.employment_type = form.employment_type.data
        job.experience_level = form.experience_level.data
        job.salary_range = form.salary_range.data
        job.deadline = form.deadline.data
        job.is_active = form.is_active.data
        job.is_featured = form.is_featured.data
        job.updated_at = datetime.utcnow()
        db.session.commit()
        log_audit('Updated Job', f'Updated job: {job.title}', 'Job', job.id)
        flash('Job updated successfully!', 'success')
        return redirect(url_for('admin_jobs'))
    return render_template('admin/job_form.html', form=form, job=job, is_new=False)

@app.route('/admin/job/<int:job_id>/toggle', methods=['POST'])
@admin_required
def admin_job_toggle(job_id):
    job = Job.query.get_or_404(job_id)
    job.is_active = not job.is_active
    db.session.commit()
    log_audit('Toggled Job', f'Toggled active status for {job.title}', 'Job', job_id)
    flash(f"Job {'activated' if job.is_active else 'deactivated'}.", 'success')
    return redirect(url_for('admin_jobs'))

@app.route('/admin/interviews')
@admin_required
def admin_interviews():
    interviews = Interview.query.order_by(Interview.scheduled_at.desc()).all()
    return render_template('admin/interviews.html', interviews=interviews)

@app.route('/admin/interview/new', methods=['GET', 'POST'])
@admin_required
def admin_interview_new():
    form = InterviewForm()
    # Pre-fill application_id if provided
    pre_app_id = request.args.get('application_id', type=int)
    if pre_app_id:
        form.application_id.data = pre_app_id
    # Populate candidates (shortlisted or interview status)
    candidates = Application.query.filter(
        db.or_(Application.status == 'SHORTLISTED', Application.status == 'INTERVIEW')
    ).all()
    form.application_id.choices = [(a.id, f'{a.full_name} - {a.job.title}') for a in candidates]

    if form.validate_on_submit():
        try:
            scheduled_at = datetime.strptime(form.scheduled_at.data, '%Y-%m-%dT%H:%M')
        except ValueError:
            scheduled_at = datetime.utcnow()
        interview = Interview(
            application_id=form.application_id.data,
            scheduled_at=scheduled_at,
            duration_minutes=form.duration_minutes.data,
            interview_type=form.interview_type.data,
            interviewer_name=form.interviewer_name.data,
            location=form.location.data,
            notes=form.notes.data
        )
        db.session.add(interview)
        db.session.commit()

        # Update application status to INTERVIEW if not already
        app = Application.query.get(form.application_id.data)
        if app and app.status != 'INTERVIEW':
            old_status = app.status
            app.status = 'INTERVIEW'
            app.status_updated_at = datetime.utcnow()
            db.session.commit()
            send_application_status_email(app, old_status, 'INTERVIEW', f'Interview scheduled for {scheduled_at.strftime("%Y-%m-%d %H:%M")}')

        log_audit('Scheduled Interview', f'Scheduled interview for {app.full_name if app else "candidate"}', 'Interview', interview.id)
        flash('Interview scheduled successfully.', 'success')
        return redirect(url_for('admin_interviews'))
    return render_template('admin/interview_form.html', form=form)

@app.route('/admin/talent-pool')
@admin_required
def admin_talent_pool():
    candidates = TalentPool.query.order_by(TalentPool.submitted_at.desc()).all()
    return render_template('admin/talent_pool.html', candidates=candidates)

@app.route('/admin/reports')
@admin_required
def admin_reports():
    total_apps = Application.query.count()
    status_stats = {}
    for status in ['NEW', 'UNDER REVIEW', 'SHORTLISTED', 'INTERVIEW', 'SELECTED', 'HIRED', 'REJECTED']:
        status_stats[status] = Application.query.filter_by(status=status).count()

    dept_stats = {}
    for dept in Department.query.all():
        count = Application.query.join(Job).filter(Job.department_id == dept.id).count()
        if count > 0:
            dept_stats[dept.name] = count

    monthly_data = {}
    for app in Application.query.all():
        key = app.submitted_at.strftime('%Y-%m')
        monthly_data[key] = monthly_data.get(key, 0) + 1

    avg_response_time = 0
    reviewed_apps = Application.query.filter(Application.status_updated_at.isnot(None)).all()
    if reviewed_apps:
        total_hours = 0
        count = 0
        for app in reviewed_apps:
            if app.status != 'NEW':
                delta = app.status_updated_at - app.submitted_at
                total_hours += delta.total_seconds() / 3600
                count += 1
        if count > 0:
            avg_response_time = round(total_hours / count, 1)

    return render_template('admin/reports.html',
                           status_stats=status_stats,
                           dept_stats=dept_stats,
                           monthly_data=monthly_data,
                           avg_response_time=avg_response_time,
                           total_apps=total_apps)

@app.route('/admin/notifications')
@admin_required
def admin_notifications():
    notifications = Notification.query.order_by(Notification.created_at.desc()).all()
    return render_template('admin/notifications.html', notifications=notifications)

@app.route('/admin/notification/<int:notif_id>/read', methods=['POST'])
@admin_required
def admin_notification_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    notif.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/audit-log')
@admin_required
def admin_audit_log():
    query = AuditLog.query
    action_filter = request.args.get('action')
    if action_filter and action_filter != 'ALL':
        query = query.filter_by(action=action_filter)
    user_filter = request.args.get('user')
    if user_filter and user_filter != 'ALL':
        query = query.filter_by(user_name=user_filter)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLog.created_at <= date_to + ' 23:59:59')
    search = request.args.get('search')
    if search:
        query = query.filter(
            db.or_(
                AuditLog.action.contains(search),
                AuditLog.description.contains(search),
                AuditLog.target_type.contains(search),
                AuditLog.user_name.contains(search)
            )
        )
    page = request.args.get('page', 1, type=int)
    per_page = 20
    pagination = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    logs = pagination.items

    all_actions = db.session.query(AuditLog.action).distinct().all()
    all_actions = [a[0] for a in all_actions]
    all_users = db.session.query(AuditLog.user_name).distinct().all()
    all_users = [u[0] for u in all_users if u[0]]

    return render_template('admin/audit_log.html',
                           logs=logs,
                           pagination=pagination,
                           all_actions=all_actions,
                           all_users=all_users,
                           action_filter=action_filter,
                           user_filter=user_filter,
                           search=search,
                           date_from=date_from,
                           date_to=date_to)

@app.route('/admin/audit-log/clear', methods=['POST'])
@admin_required
def admin_clear_audit_log():
    if session.get('admin_username') != 'admin':
        flash('Only super admin can clear audit logs.', 'danger')
        return redirect(url_for('admin_audit_log'))
    try:
        num_deleted = AuditLog.query.delete()
        db.session.commit()
        log_audit('Cleared Audit Log', f'Deleted {num_deleted} audit log entries')
        flash(f'Successfully cleared {num_deleted} audit log entries.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing logs: {e}', 'danger')
    return redirect(url_for('admin_audit_log'))

@app.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def admin_settings():
    if request.method == 'POST':
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('admin_settings'))
    return render_template('admin/settings.html')

# ========================= Database Initialization (Safe) =========================

def _safe_add_column(table, column_name, column_type):
    inspector = db.inspect(db.engine)
    if table in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns(table)]
        if column_name not in columns:
            try:
                db.engine.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}")
                print(f"✅ Added column '{column_name}' to {table}")
            except Exception as e:
                print(f"⚠️ Could not add column '{column_name}': {e}")

def init_db_safe():
    with app.app_context():
        db.create_all()
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        print(f"📋 Existing tables: {', '.join(existing_tables) if existing_tables else 'None'}")

        # Add missing columns for jobs
        _safe_add_column('jobs', 'is_featured', 'BOOLEAN DEFAULT 0')
        _safe_add_column('jobs', 'banner_image', 'VARCHAR(255)')

        # Add missing columns for applications
        _safe_add_column('applications', 'tags', 'VARCHAR(255)')
        _safe_add_column('applications', 'reviewed_by', 'VARCHAR(120)')
        _safe_add_column('applications', 'shortlisted_at', 'DATETIME')
        _safe_add_column('applications', 'rejected_at', 'DATETIME')
        _safe_add_column('applications', 'viewed_at', 'DATETIME')
        _safe_add_column('applications', 'notes', 'TEXT')

        # Add missing columns for interviews
        _safe_add_column('interviews', 'evaluation', 'TEXT')
        _safe_add_column('interviews', 'rating', 'INTEGER')
        _safe_add_column('interviews', 'decision', 'VARCHAR(30)')

        print("✅ Database schema verified/updated safely.")

        # Seed initial data if empty
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
            print('Departments seeded.')

        if Location.query.count() == 0:
            db.session.add(Location(name='Hawassa', address='Hawassa, Sidama Region, Ethiopia'))
            db.session.commit()
            print('Locations seeded.')

        if Job.query.count() == 0:
            # Get department ids
            dept_eng = Department.query.filter_by(name='Engineering').first()
            dept_fo = Department.query.filter_by(name='Front Office').first()
            dept_fin = Department.query.filter_by(name='Finance').first()
            loc_hawassa = Location.query.filter_by(name='Hawassa').first()
            sample_jobs = [
                Job(
                    title='Engineering Head',
                    department_id=dept_eng.id if dept_eng else None,
                    location_id=loc_hawassa.id if loc_hawassa else None,
                    short_description='Lead facility management, MEP systems, and maintenance operations.',
                    full_description='Rori Hotel is seeking an experienced and visionary Engineering Head to lead our facility management and technical operations in Hawassa.',
                    responsibilities='Direct and manage overall hotel engineering maintenance and facility operations.\nDevelop and execute comprehensive Preventive Maintenance Plans (PMP) for all equipment.\nLead, mentor, and evaluate the engineering and maintenance technical team.\nEnsure strict compliance with national safety, occupational health, and fire codes.\nManage departmental budgets, spare parts inventory, and contractor service contracts.\nImplement energy efficiency, water conservation, and sustainability initiatives.',
                    requirements='BSc Degree in Electrical, Mechanical, Civil Engineering, or equivalent technical discipline.\nMinimum 5+ years of progressive engineering leadership experience in luxury hotels or large commercial facilities.\nDeep expertise in HVAC, heavy generators, BMS, plumbing, electrical distribution, and fire suppression systems.\nFluent in Amharic (Native) and strong working proficiency in English (Written and Verbal).',
                    what_we_offer='Career Development: Leadership growth opportunities within a premier hospitality brand.\nTraining: Specialized technical certifications and hospitality management training.\nEmployee Benefits: Competitive executive salary package, duty meals, and health coverage.',
                    employment_type='Full-time',
                    experience_level='3+ Years',
                    salary_range='50,000 - 70,000 ETB',
                    deadline=date(2026, 9, 30),
                    is_active=True,
                    is_featured=True
                ),
                Job(
                    title='Front Office Supervisor',
                    department_id=dept_fo.id if dept_fo else None,
                    location_id=loc_hawassa.id if loc_hawassa else None,
                    short_description='Oversee reception operations and ensure luxury guest reception services.',
                    full_description='We are looking for a Front Office Supervisor to manage the daily operations of our front desk, ensuring exceptional guest experiences.',
                    responsibilities='Supervise front office staff and daily operations.\nEnsure smooth check-in/check-out processes.\nHandle guest complaints and special requests.\nTrain and evaluate front office team members.\nMaintain high standards of service and professionalism.',
                    requirements='Diploma or Bachelor\'s degree in Hospitality Management or related field.\nMinimum 2 years of front office experience in a luxury hotel.\nStrong leadership and communication skills.\nProficiency in Opera PMS is a plus.',
                    what_we_offer='Competitive salary and benefits.\nCareer growth opportunities.\nStaff meals and uniforms.\nTraining and development programs.',
                    employment_type='Full-time',
                    experience_level='2+ Years',
                    salary_range='30,000 - 45,000 ETB',
                    deadline=date(2026, 10, 15),
                    is_active=True,
                    is_featured=True
                ),
                Job(
                    title='Senior Accountant',
                    department_id=dept_fin.id if dept_fin else None,
                    location_id=loc_hawassa.id if loc_hawassa else None,
                    short_description='Manage daily financial reporting, auditing, and ledger operations.',
                    full_description='We are seeking a Senior Accountant to handle the financial operations of the hotel, including reporting, auditing, and compliance.',
                    responsibilities='Prepare monthly financial statements and reports.\nManage accounts payable and receivable.\nConduct internal audits and ensure compliance with regulations.\nAssist in budget preparation and variance analysis.\nSupervise accounting staff.',
                    requirements='Bachelor\'s degree in Accounting or Finance.\nMinimum 3 years of experience in accounting, preferably in hospitality.\nStrong knowledge of IFRS and tax regulations.\nProficiency in accounting software (e.g., QuickBooks, SunSystems).',
                    what_we_offer='Competitive salary package.\nOpportunities for professional development.\nHealth insurance and other benefits.',
                    employment_type='Full-time',
                    experience_level='3+ Years',
                    salary_range='40,000 - 60,000 ETB',
                    deadline=date(2026, 10, 10),
                    is_active=True,
                    is_featured=False
                )
            ]
            db.session.add_all(sample_jobs)
            db.session.commit()
            print('Sample jobs seeded.')

# ========================= CLI Commands =========================

@app.cli.command('init-db-safe')
def init_db_safe_command():
    """Initialize database safely without dropping existing data."""
    print("🔍 Checking database...")
    init_db_safe()
    print("✅ Database initialization complete.")

# ========================= Run Application =========================

if __name__ == '__main__':
    with app.app_context():
        init_db_safe()
    app.run(debug=True, host='0.0.0.0', port=5000)
