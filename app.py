import os
import secrets
import traceback
import jinja2

from datetime import datetime, timedelta
from functools import wraps
from threading import Thread

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    send_from_directory,
    abort
)

from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm

from wtforms import (
    StringField,
    TextAreaField,
    SelectField,
    DateField,
    FileField,
    BooleanField,
    PasswordField,
    IntegerField
)

from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    Optional,
    NumberRange,
    EqualTo
)

from werkzeug.utils import secure_filename
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from flask_mail import Mail, Message
from sqlalchemy import inspect, text

# ============================================================
# CLOUDINARY
# ============================================================

try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.utils
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production-rori-2026")
    
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "instance", "database.db")
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300
    }

    # LOCAL FILE UPLOADS
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "resumes")
    UPLOAD_FOLDER_JOBS = os.path.join(BASE_DIR, "static", "uploads", "jobs")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # CLOUDINARY
    CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL")
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET")
    CLOUDINARY_CV_FOLDER = os.environ.get("CLOUDINARY_CV_FOLDER", "rori-hotel-cv")

    # HR LOGIN
    HR_USERNAME = os.environ.get("HR_USERNAME") or os.environ.get("ADMIN_USERNAME") or "admin"
    HR_PASSWORD_HASH = os.environ.get("HR_PASSWORD_HASH")
    if not HR_PASSWORD_HASH:
        raw_password = os.environ.get("HR_PASSWORD") or os.environ.get("ADMIN_PASSWORD") or "RoriHR2026"
        HR_PASSWORD_HASH = generate_password_hash(raw_password)

    # MAIL
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ["true", "1", "on"]
    MAIL_USE_SSL = os.environ.get("MAIL_USE_SSL", "false").lower() in ["true", "1", "on"]
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@rorihotel.com")

# ============================================================
# APPLICATION INITIALIZATION
# ============================================================

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)
mail = Mail(app)

# ============================================================
# CLOUDINARY CONFIGURATION
# ============================================================

if CLOUDINARY_AVAILABLE:
    if app.config.get("CLOUDINARY_URL"):
        cloudinary.config(cloudinary_url=app.config["CLOUDINARY_URL"], secure=True)
        print("[CLOUDINARY] Configured via CLOUDINARY_URL environment variable.")
    elif (
        app.config.get("CLOUDINARY_CLOUD_NAME")
        and app.config.get("CLOUDINARY_API_KEY")
        and app.config.get("CLOUDINARY_API_SECRET")
    ):
        cloudinary.config(
            cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
            api_key=app.config["CLOUDINARY_API_KEY"],
            api_secret=app.config["CLOUDINARY_API_SECRET"],
            secure=True
        )
        print("[CLOUDINARY] Configuration loaded successfully via keys.")
    else:
        print("[CLOUDINARY] WARNING: Cloudinary credentials not found. Using local storage fallback.")

# ============================================================
# TEMPLATE LOADER
# ============================================================

template_dirs = [
    os.path.join(app.root_path, "templates"),
    os.path.join(app.root_path, "templates", "careers"),
    os.path.join(app.root_path, "templates", "application"),
    os.path.join(app.root_path, "templates", "auth"),
    os.path.join(app.root_path, "templates", "admin"),
    os.path.join(app.root_path, "templates", "hr")
]

app.jinja_loader = jinja2.FileSystemLoader(template_dirs)

# ============================================================
# DIRECTORIES
# ============================================================

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["UPLOAD_FOLDER_JOBS"], exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

# ============================================================
# MODELS
# ============================================================

class AdminUser(db.Model):
    __tablename__ = "admin_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<AdminUser {self.username}>"

class Department(db.Model):
    __tablename__ = "departments"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    icon = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    jobs = db.relationship("Job", backref="department_ref", lazy=True)

    def __repr__(self):
        return f"<Department {self.name}>"

class Location(db.Model):
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    address = db.Column(db.String(200), nullable=True)
    jobs = db.relationship("Job", backref="location_ref", lazy=True)

    def __repr__(self):
        return f"<Location {self.name}>"

class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=True)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=True)
    short_description = db.Column(db.String(200), nullable=False)
    full_description = db.Column(db.Text, nullable=False)
    responsibilities = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text, nullable=False)
    what_we_offer = db.Column(db.Text, nullable=False)
    employment_type = db.Column(db.String(30), nullable=False, default="Full-time")
    experience_level = db.Column(db.String(30), nullable=True)
    salary_range = db.Column(db.String(100), nullable=True)
    deadline = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    banner_image = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    applications = db.relationship("Application", backref="job", lazy=True)

    @property
    def department(self):
        return self.department_ref

    @property
    def location(self):
        return self.location_ref

    def responsibilities_list(self):
        return [item.strip() for item in (self.responsibilities or "").splitlines() if item.strip()]

    def requirements_list(self):
        return [item.strip() for item in (self.requirements or "").splitlines() if item.strip()]

    def what_we_offer_list(self):
        return [item.strip() for item in (self.what_we_offer or "").splitlines() if item.strip()]

    @property
    def department_name(self):
        return self.department_ref.name if self.department_ref else "Not specified"

    @property
    def location_name(self):
        return self.location_ref.name if self.location_ref else "Hawassa"

    @property
    def is_expired(self):
        if not self.deadline:
            return False
        return self.deadline < datetime.utcnow().date()

    def __repr__(self):
        return f"<Job {self.title}>"

class Application(db.Model):
    __tablename__ = "applications"
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False)
    reference_no = db.Column(db.String(20), unique=True, nullable=True)
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
    status = db.Column(db.String(30), default="NEW", nullable=False)
    status_updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    tags = db.Column(db.String(255), nullable=True)
    reviewed_by = db.Column(db.String(120), nullable=True)
    shortlisted_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    viewed_at = db.Column(db.DateTime, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Application {self.full_name}>"

class TalentPool(db.Model):
    __tablename__ = "talent_pool"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
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
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class Interview(db.Model):
    __tablename__ = "interviews"
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=30)
    interview_type = db.Column(db.String(50), default="In-person")
    interviewer_name = db.Column(db.String(120), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    evaluation = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    decision = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(30), default="Scheduled")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    application = db.relationship("Application", backref="interviews", lazy=True)

class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    recipient = db.Column(db.String(120), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AuditLog(db.Model):
    __tablename__ = "audit_logs"
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

# ============================================================
# FORMS
# ============================================================

class ApplicationForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    phone = StringField("Phone", validators=[DataRequired(), Length(max=30)])
    location = StringField("Current Location", validators=[DataRequired(), Length(max=120)])
    education = SelectField(
        "Highest Education Level",
        choices=[
            ("High School", "High School Diploma"),
            ("Technical Diploma", "TVET / Advanced Diploma"),
            ("Bachelor Degree", "Bachelor's Degree"),
            ("Master Degree", "Master's Degree / Doctorate")
        ],
        validators=[DataRequired()]
    )
    years_of_experience = StringField("Years of Experience", validators=[DataRequired(), Length(max=30)])
    current_position = StringField("Current Position", validators=[Optional(), Length(max=120)])
    previous_employer = StringField("Previous Employer", validators=[Optional(), Length(max=120)])
    skills = StringField("Key Skills", validators=[DataRequired(), Length(max=255)])
    languages = StringField("Languages Spoken", validators=[DataRequired(), Length(max=255)])
    certifications = StringField("Professional Certifications", validators=[Optional(), Length(max=255)])
    availability_date = DateField("Earliest Availability Date", validators=[Optional()], format="%Y-%m-%d")
    willing_to_relocate = SelectField("Willing to Relocate?", choices=[("Yes", "Yes"), ("No", "No")], validators=[DataRequired()])
    expected_salary = StringField("Expected Monthly Salary", validators=[Optional(), Length(max=50)])
    cover_letter = TextAreaField("Cover Letter", validators=[DataRequired(), Length(max=5000)])
    cv_file = FileField("Upload CV", validators=[DataRequired()])

class TalentPoolForm(ApplicationForm):
    pass

class JobForm(FlaskForm):
    title = StringField("Job Title", validators=[DataRequired(), Length(max=120)])
    department_id = SelectField("Department", coerce=int, validators=[Optional()])
    location_id = SelectField("Location", coerce=int, validators=[Optional()])
    short_description = StringField("Short Description", validators=[DataRequired(), Length(max=200)])
    full_description = TextAreaField("Full Description", validators=[DataRequired()])
    responsibilities = TextAreaField("Responsibilities", validators=[DataRequired()])
    requirements = TextAreaField("Requirements", validators=[DataRequired()])
    what_we_offer = TextAreaField("What We Offer", validators=[DataRequired()])
    employment_type = SelectField(
        "Employment Type",
        choices=[("Full-time", "Full-time"), ("Part-time", "Part-time"), ("Contract", "Contract")],
        validators=[DataRequired()]
    )
    experience_level = StringField("Experience Level", validators=[Optional(), Length(max=30)])
    salary_range = StringField("Salary Range", validators=[Optional(), Length(max=100)])
    deadline = DateField("Application Deadline", validators=[Optional()], format="%Y-%m-%d")
    is_active = BooleanField("Active", default=True)
    is_featured = BooleanField("Featured", default=False)

class AdminLoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Current Password", validators=[DataRequired()])
    new_password = PasswordField("New Password", validators=[DataRequired(), Length(min=6, message="Password must be at least 6 characters")])
    confirm_password = PasswordField("Confirm New Password", validators=[DataRequired(), EqualTo("new_password", message="Passwords must match")])

class InterviewForm(FlaskForm):
    application_id = SelectField("Candidate", coerce=int, validators=[DataRequired()])
    scheduled_at = StringField("Scheduled Date/Time", validators=[DataRequired()])
    duration_minutes = IntegerField("Duration", default=30, validators=[NumberRange(min=5, max=120)])
    interview_type = SelectField(
        "Type",
        choices=[("In-person", "In-person"), ("Virtual", "Virtual"), ("Phone", "Phone")],
        default="In-person"
    )
    interviewer_name = StringField("Interviewer Name", validators=[Optional(), Length(max=120)])
    location = StringField("Location / Meeting Link", validators=[Optional(), Length(max=200)])
    notes = TextAreaField("Notes", validators=[Optional()])

# ============================================================
# FILE HELPERS
# ============================================================

def allowed_file(filename):
    return bool(
        filename
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )

def allowed_image_file(filename):
    return bool(
        filename
        and "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_IMAGE_EXTENSIONS"]
    )

# ============================================================
# CLOUDINARY HELPERS
# ============================================================

def cloudinary_ready():
    if not CLOUDINARY_AVAILABLE:
        return False
    return bool(
        app.config.get("CLOUDINARY_URL")
        or (
            app.config.get("CLOUDINARY_CLOUD_NAME")
            and app.config.get("CLOUDINARY_API_KEY")
            and app.config.get("CLOUDINARY_API_SECRET")
        )
    )

def is_cloudinary_cv(filename):
    return bool(filename and filename.startswith("cloudinary:"))

def parse_cloudinary_cv(filename):
    if not is_cloudinary_cv(filename):
        return None, None
    value = filename[len("cloudinary:"):]
    if "|" not in value:
        return None, None
    public_id, extension = value.rsplit("|", 1)
    public_id = public_id.strip()
    extension = extension.strip().lower()
    if not public_id or extension not in app.config["ALLOWED_EXTENSIONS"]:
        return None, None
    return public_id, extension

def save_uploaded_file(file):
    if not file or not file.filename:
        return None
    if not allowed_file(file.filename):
        return None

    original = secure_filename(file.filename)
    if not original:
        return None

    name, ext = os.path.splitext(original)
    extension = ext.lower().lstrip(".")
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    safe_name = secure_filename(name) or "cv"
    unique_name = f"{safe_name}_{timestamp}"

    # CLOUDINARY UPLOAD
    if cloudinary_ready():
        try:
            file.seek(0)
            upload_result = cloudinary.uploader.upload(
                file,
                resource_type="raw",
                type="upload",
                folder=app.config["CLOUDINARY_CV_FOLDER"],
                public_id=unique_name,
                overwrite=False
            )
            public_id = upload_result.get("public_id")
            if public_id:
                stored_reference = f"cloudinary:{public_id}|{extension}"
                print("[CLOUDINARY] CV uploaded successfully:", public_id)
                return stored_reference
        except Exception as e:
            print("[CLOUDINARY] CV upload failed, falling back to local storage:", e)
            traceback.print_exc()

    # LOCAL FALLBACK
    filename = f"{unique_name}.{extension}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    try:
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file.seek(0)
        file.save(path)
        if os.path.isfile(path):
            print("[LOCAL] CV saved successfully:", path)
            return filename
    except Exception:
        traceback.print_exc()

    return None

def delete_uploaded_file(filename):
    if not filename:
        return

    if is_cloudinary_cv(filename):
        public_id, extension = parse_cloudinary_cv(filename)
        if public_id and cloudinary_ready():
            try:
                cloudinary.uploader.destroy(public_id, resource_type="raw")
                print("[CLOUDINARY] CV deleted:", public_id)
            except Exception:
                traceback.print_exc()
        return

    try:
        safe_filename = secure_filename(os.path.basename(filename))
        if not safe_filename:
            return
        upload_directories = [
            app.config.get("UPLOAD_FOLDER"),
            os.path.join(BASE_DIR, "uploads", "resumes"),
            os.path.join(BASE_DIR, "uploads"),
            os.path.join(app.root_path, "static", "uploads", "resumes"),
            os.path.join(app.root_path, "static", "uploads")
        ]
        for directory in upload_directories:
            if not directory:
                continue
            path = os.path.join(directory, safe_filename)
            if os.path.isfile(path):
                os.remove(path)
                print("[LOCAL] CV deleted:", path)
                break
    except Exception:
        traceback.print_exc()

def generate_cloudinary_cv_url(filename):
    public_id, extension = parse_cloudinary_cv(filename)
    if not public_id or not cloudinary_ready():
        return None
    try:
        url, _ = cloudinary.utils.cloudinary_url(public_id, resource_type="raw", secure=True)
        return url
    except Exception:
        traceback.print_exc()
        return None

# ============================================================
# JOB IMAGE
# ============================================================

def save_job_image(file):
    if not file or not file.filename:
        return None
    if not allowed_image_file(file.filename):
        return None
    original = secure_filename(file.filename)
    if not original:
        return None
    name, ext = os.path.splitext(original)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    filename = f"{name}_{timestamp}{ext.lower()}"
    path = os.path.join(app.config["UPLOAD_FOLDER_JOBS"], filename)
    try:
        os.makedirs(app.config["UPLOAD_FOLDER_JOBS"], exist_ok=True)
        file.seek(0)
        file.save(path)
        if os.path.isfile(path):
            return filename
    except Exception:
        traceback.print_exc()
    return None

def delete_job_image(filename):
    if not filename:
        return
    try:
        safe_filename = secure_filename(os.path.basename(filename))
        if safe_filename:
            path = os.path.join(app.config["UPLOAD_FOLDER_JOBS"], safe_filename)
            if os.path.isfile(path):
                os.remove(path)
    except Exception:
        traceback.print_exc()

# ============================================================
# ADMIN SECURITY
# ============================================================

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            flash("እባክዎን አስቀድመው Login ያድርጉ።", "warning")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ============================================================
# AUDIT
# ============================================================

def log_audit(action, description=None, target_type=None, target_id=None):
    try:
        audit = AuditLog(
            user_id=session.get("admin_id"),
            user_name=session.get("admin_username", "system"),
            action=action,
            description=description,
            target_type=target_type,
            target_id=target_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent")
        )
        db.session.add(audit)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"AUDIT ERROR: {e}")

# ============================================================
# EMAIL
# ============================================================

def send_async_email(message):
    try:
        with app.app_context():
            mail.send(message)
    except Exception as e:
        print(f"EMAIL ERROR: {e}")

def send_application_status_email(application, old_status, new_status, notes=""):
    if not app.config.get("MAIL_USERNAME") or not application.email:
        return
    status_messages = {
        "UNDER REVIEW": "Your application is currently under review by our HR team.",
        "SHORTLISTED": "Congratulations! Your application has been shortlisted for the next stage.",
        "INTERVIEW": "Your application has progressed to the interview stage.",
        "SELECTED": "Congratulations! You have been selected for the position.",
        "HIRED": "Congratulations! You have been hired by Rori Hotel.",
        "REJECTED": "We regret to inform you that your application was not successful."
    }
    try:
        reference = application.reference_no or f"APP-{application.id}"
        position = application.job.title if application.job else "Rori Hotel Position"
        status_message = status_messages.get(new_status, "Your application status has been updated.")
        notes_html = ""
        if notes:
            safe_notes = notes.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            notes_html = f"<p><strong>HR Note:</strong><br>{safe_notes}</p>"

        message = Message(
            subject=f"Rori Hotel - Application Status {reference}",
            sender=app.config["MAIL_DEFAULT_SENDER"],
            recipients=[application.email]
        )
        message.html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>Rori Hotel Careers</title></head>
        <body style="margin:0; padding:0; background:#f4f5f7; font-family:Arial,sans-serif;">
            <div style="max-width:600px; margin:30px auto; background:#fff; padding:30px; border-radius:12px;">
                <h1>Rori Hotel</h1>
                <p>Human Resources Department</p>
                <hr>
                <p>Dear <strong>{application.full_name}</strong>,</p>
                <p>{status_message}</p>
                <p><strong>Position:</strong> {position}</p>
                <p><strong>Status:</strong> {new_status}</p>
                <p><strong>Reference:</strong> {reference}</p>
                {notes_html}
                <hr>
                <p style="font-size:13px; color:#777;">Please keep your reference number for future application tracking.</p>
                <p style="font-size:12px; color:#999;">© 2026 Rori Hotel. All rights reserved.</p>
            </div>
        </body>
        </html>
        """
        Thread(target=send_async_email, args=(message,), daemon=True).start()
    except Exception as e:
        print(f"EMAIL DISPATCH ERROR: {e}")

# ============================================================
# SIMILAR JOBS
# ============================================================

def get_similar_jobs(job, limit=3):
    query = Job.query.filter(Job.is_active.is_(True), Job.id != job.id)
    if job.department_id:
        query = query.filter(db.or_(Job.department_id == job.department_id, Job.employment_type == job.employment_type))
    return query.order_by(Job.created_at.desc()).limit(limit).all()

# ============================================================
# CONTEXT
# ============================================================

@app.context_processor
def inject_globals():
    try:
        return {
            "now": datetime.utcnow,
            "all_departments": Department.query.order_by(Department.name).all(),
            "all_locations": Location.query.order_by(Location.name).all()
        }
    except Exception:
        return {"now": datetime.utcnow, "all_departments": [], "all_locations": []}

# ============================================================
# HOME & PUBLIC ROUTES
# ============================================================

@app.route("/")
def home():
    featured_jobs = Job.query.filter_by(is_active=True, is_featured=True).order_by(Job.created_at.desc()).limit(6).all()
    latest_jobs = Job.query.filter_by(is_active=True).order_by(Job.created_at.desc()).limit(6).all()
    return render_template("home.html", featured_jobs=featured_jobs, latest_jobs=latest_jobs, departments=Department.query.order_by(Department.name).all())

@app.route("/jobs")
def jobs():
    department_id = request.args.get("department", type=int)
    location_id = request.args.get("location", type=int)
    type_filter = request.args.get("type", "").strip()
    experience_filter = request.args.get("experience", "").strip()
    search_query = request.args.get("q", "").strip()

    query = Job.query.filter(Job.is_active.is_(True))
    if department_id:
        query = query.filter(Job.department_id == department_id)
    if location_id:
        query = query.filter(Job.location_id == location_id)
    if type_filter:
        query = query.filter(Job.employment_type == type_filter)
    if experience_filter:
        query = query.filter(Job.experience_level == experience_filter)
    if search_query:
        search = f"%{search_query}%"
        query = query.filter(db.or_(Job.title.ilike(search), Job.short_description.ilike(search), Job.full_description.ilike(search)))

    jobs_list = query.order_by(Job.created_at.desc()).all()
    return render_template("jobs.html", jobs=jobs_list, departments=Department.query.all(), locations=Location.query.all())

@app.route("/job/<int:job_id>")
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    return render_template("job_detail.html", job=job, similar_jobs=get_similar_jobs(job))

@app.route("/departments")
def departments():
    return render_template("departments.html", departments=Department.query.all())

@app.route("/department/<int:dept_id>")
def department_detail(dept_id):
    department = Department.query.get_or_404(dept_id)
    jobs_list = Job.query.filter_by(department_id=dept_id, is_active=True).order_by(Job.created_at.desc()).all()
    return render_template("department_detail.html", department=department, jobs=jobs_list)

@app.route("/locations")
def locations():
    return render_template("locations.html", locations=Location.query.all())

@app.route("/about-careers")
def about_careers():
    return render_template("about_careers.html")

@app.route("/track-status", methods=["GET", "POST"])
@app.route("/application/lookup", methods=["GET", "POST"])
def track_status():
    application = None
    searched = False
    if request.method == "POST":
        searched = True
        reference_no = request.form.get("reference_no", "").strip().upper()
        if reference_no:
            application = Application.query.filter_by(reference_no=reference_no).first()
    return render_template("track_status.html", application=application, searched=searched)

# ============================================================
# APPLY
# ============================================================

@app.route("/apply/<int:job_id>", methods=["GET", "POST"])
def apply(job_id):
    job = Job.query.get_or_404(job_id)
    if not job.is_active:
        flash("This position is no longer accepting applications.", "warning")
        return redirect(url_for("job_detail", job_id=job.id))
    if job.is_expired:
        flash("The application deadline has passed.", "warning")
        return redirect(url_for("job_detail", job_id=job.id))

    form = ApplicationForm()
    if form.validate_on_submit():
        cv_filename = save_uploaded_file(form.cv_file.data)
        if not cv_filename:
            flash("CV upload failed. Please upload PDF, DOC, or DOCX file.", "danger")
            return render_template("apply.html", form=form, job=job)

        reference_no = None
        for _ in range(20):
            candidate_reference = "RH-" + secrets.token_hex(4).upper()
            if not Application.query.filter_by(reference_no=candidate_reference).first():
                reference_no = candidate_reference
                break

        if not reference_no:
            delete_uploaded_file(cv_filename)
            flash("Could not generate application reference number.", "danger")
            return render_template("apply.html", form=form, job=job)

        application = Application(
            job_id=job.id,
            reference_no=reference_no,
            full_name=form.full_name.data.strip(),
            email=form.email.data.strip().lower(),
            phone=form.phone.data.strip(),
            location=form.location.data.strip(),
            education=form.education.data,
            years_of_experience=form.years_of_experience.data.strip(),
            current_position=form.current_position.data.strip() if form.current_position.data else None,
            previous_employer=form.previous_employer.data.strip() if form.previous_employer.data else None,
            skills=form.skills.data.strip(),
            languages=form.languages.data.strip(),
            certifications=form.certifications.data.strip() if form.certifications.data else None,
            availability_date=form.availability_date.data,
            willing_to_relocate=form.willing_to_relocate.data,
            expected_salary=form.expected_salary.data.strip() if form.expected_salary.data else None,
            cover_letter=form.cover_letter.data.strip(),
            cv_filename=cv_filename,
            status="NEW",
            status_updated_at=datetime.utcnow(),
            submitted_at=datetime.utcnow()
        )

        try:
            db.session.add(application)
            db.session.flush()
            notification = Notification(
                title="New Application",
                message=f"{application.full_name} applied for {job.title}. Reference: {reference_no}",
                recipient="admin",
                is_read=False
            )
            db.session.add(notification)
            db.session.commit()
        except Exception:
            db.session.rollback()
            delete_uploaded_file(cv_filename)
            traceback.print_exc()
            flash("Application could not be submitted. Please try again.", "danger")
            return render_template("apply.html", form=form, job=job)

        log_audit("New Application", f"{application.full_name} applied for {job.title}", "Application", application.id)
        flash("Your application has been submitted successfully!", "success")
        return redirect(url_for("application_success", app_id=application.id))

    return render_template("apply.html", form=form, job=job)

@app.route("/application/success/<int:app_id>")
def application_success(app_id):
    application = Application.query.get_or_404(app_id)
    return render_template("success.html", application=application, job=application.job)

@app.route("/application/status/<int:app_id>")
def application_status(app_id):
    application = Application.query.get_or_404(app_id)
    if not application.viewed_at:
        application.viewed_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    return render_template("application_status.html", application=application, job=application.job)

@app.route("/talent-pool", methods=["GET", "POST"])
def talent_pool():
    form = TalentPoolForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        if TalentPool.query.filter(db.func.lower(TalentPool.email) == email).first():
            flash("You have already joined the Rori Hotel Talent Pool with this email.", "warning")
            return redirect(url_for("talent_pool"))

        cv_filename = save_uploaded_file(form.cv_file.data)
        if not cv_filename:
            flash("Invalid CV. Please upload PDF, DOC, or DOCX.", "danger")
            return render_template("talent_pool.html", form=form)

        talent = TalentPool(
            full_name=form.full_name.data.strip(),
            email=email,
            phone=form.phone.data.strip(),
            location=form.location.data.strip(),
            education=form.education.data,
            years_of_experience=form.years_of_experience.data.strip(),
            skills=form.skills.data.strip(),
            languages=form.languages.data.strip(),
            certifications=form.certifications.data.strip() if form.certifications.data else None,
            availability_date=form.availability_date.data,
            willing_to_relocate=form.willing_to_relocate.data,
            expected_salary=form.expected_salary.data.strip() if form.expected_salary.data else None,
            cover_letter=form.cover_letter.data.strip(),
            cv_filename=cv_filename
        )

        try:
            db.session.add(talent)
            db.session.commit()
        except Exception:
            db.session.rollback()
            delete_uploaded_file(cv_filename)
            traceback.print_exc()
            flash("Could not join the talent pool.", "danger")
            return render_template("talent_pool.html", form=form)

        flash("You have successfully joined the Rori Hotel Talent Pool!", "success")
        return redirect(url_for("home"))

    return render_template("talent_pool.html", form=form)

# ============================================================
# ADMIN & HR ROUTES
# ============================================================

@app.route("/admin/login", methods=["GET", "POST"])
@app.route("/hr/login", methods=["GET", "POST"])
@app.route("/auth/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    form = AdminLoginForm()
    if request.method == "POST":
        username = request.form.get("username", "").strip() or (form.username.data or "").strip()
        password = request.form.get("password", "") or (form.password.data or "")

        if not username or not password:
            flash("እባክዎን Username እና Password ይሙሉ!", "warning")
            return render_template("login.html", form=form)

        try:
            admin_user = AdminUser.query.filter_by(username=username).first()
            if admin_user and check_password_hash(admin_user.password_hash, password):
                session.clear()
                session["admin_logged_in"] = True
                session["admin_username"] = username
                session["admin_id"] = admin_user.id
                log_audit("Login", f"Admin {username} logged in.")
                flash("እንኳን በደህና መጡ!", "success")
                return redirect(url_for("admin_dashboard"))
        except Exception:
            db.session.rollback()
            traceback.print_exc()

        default_username = app.config.get("HR_USERNAME", "admin")
        default_hash = app.config.get("HR_PASSWORD_HASH")

        if username == default_username and default_hash and check_password_hash(default_hash, password):
            admin_id = None
            try:
                new_admin = AdminUser(username=username, password_hash=default_hash)
                db.session.add(new_admin)
                db.session.commit()
                admin_id = new_admin.id
            except Exception:
                db.session.rollback()
                existing = AdminUser.query.filter_by(username=username).first()
                if existing:
                    admin_id = existing.id

            if admin_id is None:
                admin_id = 1

            session.clear()
            session["admin_logged_in"] = True
            session["admin_username"] = username
            session["admin_id"] = admin_id
            log_audit("Login", f"Admin {username} logged in via fallback.")
            flash("እንኳን በደህና መጡ!", "success")
            return redirect(url_for("admin_dashboard"))

        flash("የተሳሳተ Username ወይም Password!", "danger")
        return render_template("login.html", form=form)

    return render_template("login.html", form=form)

@app.route("/admin/change-password", methods=["GET", "POST"])
@app.route("/hr/change-password", methods=["GET", "POST"])
@admin_required
def admin_change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        username = session.get("admin_username")
        admin_user = AdminUser.query.filter_by(username=username).first()
        if admin_user and check_password_hash(admin_user.password_hash, form.current_password.data):
            admin_user.password_hash = generate_password_hash(form.new_password.data)
            try:
                db.session.commit()
                log_audit("Change Password", f"Admin {username} changed their password.")
                flash("የይለፍ ቃልዎ በስኬት ተቀይሯል!", "success")
                return redirect(url_for("admin_dashboard"))
            except Exception:
                db.session.rollback()
                flash("Password update failed.", "danger")
                return render_template("admin/change_password.html", form=form)

        flash("ያስተገቡት Current Password ትክክል አይደለም!", "danger")
    return render_template("admin/change_password.html", form=form)

@app.route("/admin/logout")
@app.route("/hr/logout")
@app.route("/auth/logout")
def admin_logout():
    username = session.get("admin_username", "Unknown")
    if session.get("admin_logged_in"):
        log_audit("Logout", f"Admin {username} logged out.")
        session.clear()
    flash("በስኬት ወጥተዋል።", "info")
    return redirect(url_for("admin_login"))

@app.route("/auth/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        flash("If an account exists with that email, we will send a reset link.", "info")
        return redirect(url_for("admin_login"))
    return render_template("forgot_password.html")

@app.route("/admin")
@app.route("/admin/dashboard")
@app.route("/hr")
@app.route("/hr/dashboard")
@admin_required
def admin_dashboard():
    total_jobs = Job.query.count()
    active_jobs = Job.query.filter_by(is_active=True).count()
    total_applications = Application.query.count()
    total_interviews = Interview.query.count()
    recent_applications = Application.query.order_by(Application.submitted_at.desc()).limit(10).all()
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(10).all()

    statuses = ["NEW", "UNDER REVIEW", "SHORTLISTED", "INTERVIEW", "SELECTED", "HIRED", "REJECTED"]
    status_counts = {status: Application.query.filter_by(status=status).count() for status in statuses}

    return render_template(
        "admin/dashboard.html",
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        total_applications=total_applications,
        total_interviews=total_interviews,
        recent_applications=recent_applications,
        notifications=notifications,
        status_counts=status_counts,
        applications=recent_applications
    )

@app.route("/admin/candidates")
@app.route("/hr/candidates")
@admin_required
def admin_candidates():
    query = Application.query
    search = request.args.get("search", "").strip()
    if search:
        search_value = f"%{search}%"
        query = query.filter(
            db.or_(
                Application.full_name.ilike(search_value),
                Application.email.ilike(search_value),
                Application.reference_no.ilike(search_value)
            )
        )
    status_filter = request.args.get("status", "").strip()
    if status_filter and status_filter != "ALL":
        query = query.filter(Application.status == status_filter)

    applications = query.order_by(Application.submitted_at.desc()).all()
    return render_template("admin/candidates.html", applications=applications, departments=Department.query.all())

@app.route("/admin/candidate/<int:app_id>")
@app.route("/hr/candidate/<int:app_id>")
@admin_required
def admin_candidate_detail(app_id):
    application = Application.query.get_or_404(app_id)
    interviews = Interview.query.filter_by(application_id=app_id).order_by(Interview.scheduled_at.desc()).all()
    if not application.viewed_at:
        application.viewed_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    return render_template("admin/candidate_detail.html", application=application, interviews=interviews)

@app.route("/admin/candidate/<int:app_id>/cv/download")
@app.route("/hr/candidate/<int:app_id>/cv/download")
@admin_required
def download_candidate_cv(app_id):
    application = Application.query.get_or_404(app_id)
    filename = application.cv_filename
    if not filename:
        flash("CV ለዚህ አመልካች አልተገኘም።", "warning")
        return redirect(request.referrer or url_for("admin_candidates"))

    if is_cloudinary_cv(filename):
        download_url = generate_cloudinary_cv_url(filename)
        if download_url:
            log_audit("CV Download", f"HR downloaded CV for {application.full_name}", "Application", application.id)
            return redirect(download_url)
        flash("Cloudinary CV ማግኘት አልተቻለም።", "danger")
        return redirect(request.referrer or url_for("admin_candidates"))

    safe_filename = secure_filename(os.path.basename(filename))
    if not safe_filename:
        flash("የCV ፋይል ስም ትክክል አይደለም።", "danger")
        return redirect(request.referrer or url_for("admin_candidates"))

    upload_directories = [
        app.config.get("UPLOAD_FOLDER"),
        os.path.join(BASE_DIR, "uploads", "resumes"),
        os.path.join(BASE_DIR, "uploads"),
        os.path.join(app.root_path, "static", "uploads", "resumes"),
        os.path.join(app.root_path, "static", "uploads")
    ]
    upload_directories = list(dict.fromkeys(directory for directory in upload_directories if directory))

    for directory in upload_directories:
        file_path = os.path.join(directory, safe_filename)
        if os.path.isfile(file_path):
            log_audit("CV Download", f"HR downloaded local CV for {application.full_name}", "Application", application.id)
            return send_from_directory(directory, safe_filename, as_attachment=False)

    flash("የCV ፋይሉ በserver ላይ አልተገኘም።", "danger")
    return redirect(request.referrer or url_for("admin_candidates"))

@app.route("/admin/application/<int:app_id>/status", methods=["POST"])
@app.route("/hr/application/<int:app_id>/status", methods=["POST"])
@app.route("/admin/application/<int:app_id>/action", methods=["POST"])
@app.route("/hr/application/<int:app_id>/action", methods=["POST"])
@admin_required
def update_application_status(app_id):
    application = Application.query.get_or_404(app_id)
    new_status = request.form.get("status", "").strip().upper() or request.form.get("action", "").strip().upper()
    notes = request.form.get("notes", "").strip()

    allowed_statuses = {"NEW", "UNDER REVIEW", "SHORTLISTED", "INTERVIEW", "SELECTED", "HIRED", "REJECTED"}
    if new_status not in allowed_statuses:
        flash("Invalid application status.", "danger")
        return redirect(request.referrer or url_for("admin_dashboard"))

    old_status = application.status
    application.status = new_status
    application.status_updated_at = datetime.utcnow()
    application.reviewed_by = session.get("admin_username")

    if new_status == "SHORTLISTED":
        application.shortlisted_at = datetime.utcnow()
    elif new_status == "REJECTED":
        application.rejected_at = datetime.utcnow()

    if notes:
        application.notes = notes

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        traceback.print_exc()
        flash("Status ማዘመን አልተቻለም።", "danger")
        return redirect(request.referrer or url_for("admin_dashboard"))

    try:
        position = application.job.title if application.job else "Rori Hotel Position"
        status_notification = Notification(
            title="Application Status Updated",
            message=f"Your application for {position} is now {new_status}. Reference: {application.reference_no}",
            recipient=application.email,
            is_read=False
        )
        db.session.add(status_notification)
        db.session.commit()
    except Exception:
        db.session.rollback()

    log_audit("Status Update", f"Changed {application.full_name} from {old_status} to {new_status}", "Application", application.id)
    send_application_status_email(application, old_status, new_status, notes)
    flash(f'የአመልካቹ Status ወደ "{new_status}" ተቀይሯል!', "success")
    return redirect(request.referrer or url_for("admin_dashboard"))

@app.route("/admin/jobs")
@app.route("/hr/jobs")
@admin_required
def admin_jobs():
    jobs_list = Job.query.order_by(Job.created_at.desc()).all()
    return render_template("admin/jobs.html", jobs=jobs_list)

def configure_job_form_choices(form):
    departments_list = Department.query.order_by(Department.name).all()
    locations_list = Location.query.order_by(Location.name).all()
    form.department_id.choices = [(0, "None")] + [(dept.id, dept.name) for dept in departments_list]
    form.location_id.choices = [(0, "None")] + [(loc.id, loc.name) for loc in locations_list]

@app.route("/admin/job/new", methods=["GET", "POST"])
@app.route("/hr/job/new", methods=["GET", "POST"])
@admin_required
def admin_job_new():
    form = JobForm()
    configure_job_form_choices(form)
    if request.method == "POST":
        banner_image = None
        if form.validate_on_submit():
            banner_image = save_job_image(request.files.get("banner_image"))
            dept_id = form.department_id.data
            loc_id = form.location_id.data

            job = Job(
                title=form.title.data.strip(),
                department_id=dept_id if dept_id and dept_id != 0 else None,
                location_id=loc_id if loc_id and loc_id != 0 else None,
                short_description=form.short_description.data.strip(),
                full_description=form.full_description.data.strip(),
                responsibilities=form.responsibilities.data.strip(),
                requirements=form.requirements.data.strip(),
                what_we_offer=form.what_we_offer.data.strip(),
                employment_type=form.employment_type.data,
                experience_level=form.experience_level.data.strip() if form.experience_level.data else None,
                salary_range=form.salary_range.data.strip() if form.salary_range.data else None,
                deadline=form.deadline.data,
                is_active=bool(form.is_active.data),
                is_featured=bool(form.is_featured.data),
                banner_image=banner_image
            )
            try:
                db.session.add(job)
                db.session.commit()
                log_audit("Created Job", f"Created job: {job.title}", "Job", job.id)
                flash("የስራ ማስታወቂያው በስኬት ተለጥፏል!", "success")
                return redirect(url_for("admin_jobs"))
            except Exception:
                db.session.rollback()
                if banner_image:
                    delete_job_image(banner_image)
                traceback.print_exc()
                flash("የስራ ማስታወቂያውን መፍጠር አልተቻለም።", "danger")
        else:
            flash("እባክዎን የተጠየቁትን የስራ መረጃዎች በትክክል ይሙሉ።", "warning")

    return render_template("admin/job_form.html", form=form, is_new=True)

@app.route("/admin/job/<int:job_id>/edit", methods=["GET", "POST"])
@app.route("/hr/job/<int:job_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_job_edit(job_id):
    job = Job.query.get_or_404(job_id)
    form = JobForm()
    configure_job_form_choices(form)

    if request.method == "GET":
        form.title.data = job.title
        form.department_id.data = job.department_id or 0
        form.location_id.data = job.location_id or 0
        form.short_description.data = job.short_description
        form.full_description.data = job.full_description
        form.responsibilities.data = job.responsibilities
        form.requirements.data = job.requirements
        form.what_we_offer.data = job.what_we_offer
        form.employment_type.data = job.employment_type
        form.experience_level.data = job.experience_level
        form.salary_range.data = job.salary_range
        form.deadline.data = job.deadline
        form.is_active.data = job.is_active
        form.is_featured.data = job.is_featured

    if request.method == "POST":
        if form.validate_on_submit():
            old_banner = job.banner_image
            new_banner = save_job_image(request.files.get("banner_image"))

            job.title = form.title.data.strip()
            job.department_id = form.department_id.data if form.department_id.data and form.department_id.data != 0 else None
            job.location_id = form.location_id.data if form.location_id.data and form.location_id.data != 0 else None
            job.short_description = form.short_description.data.strip()
            job.full_description = form.full_description.data.strip()
            job.responsibilities = form.responsibilities.data.strip()
            job.requirements = form.requirements.data.strip()
            job.what_we_offer = form.what_we_offer.data.strip()
            job.employment_type = form.employment_type.data
            job.experience_level = form.experience_level.data.strip() if form.experience_level.data else None
            job.salary_range = form.salary_range.data.strip() if form.salary_range.data else None
            job.deadline = form.deadline.data
            job.is_active = bool(form.is_active.data)
            job.is_featured = bool(form.is_featured.data)

            if new_banner:
                job.banner_image = new_banner

            try:
                db.session.commit()
                if new_banner and old_banner and old_banner != new_banner:
                    delete_job_image(old_banner)
                log_audit("Updated Job", f"Updated job: {job.title}", "Job", job.id)
                flash("የስራ ማስታወቂያው ተስተካክሏል!", "success")
                return redirect(url_for("admin_jobs"))
            except Exception:
                db.session.rollback()
                if new_banner:
                    delete_job_image(new_banner)
                traceback.print_exc()
                flash("የስራ ማስታወቂያውን ማስተካከል አልተቻለም።", "danger")

    return render_template("admin/job_form.html", form=form, is_new=False, job=job)

@app.route("/admin/job/<int:job_id>/toggle", methods=["GET", "POST"])
@app.route("/hr/job/<int:job_id>/toggle", methods=["GET", "POST"])
@admin_required
def admin_job_toggle(job_id):
    job = Job.query.get_or_404(job_id)
    job.is_active = not job.is_active
    try:
        db.session.commit()
        log_audit("Toggled Job", f"{job.title} active status changed to {job.is_active}", "Job", job.id)
        flash("Job activated." if job.is_active else "Job deactivated.", "success")
    except Exception:
        db.session.rollback()
        traceback.print_exc()
        flash("Could not update job.", "danger")

    return redirect(url_for("admin_jobs"))

@app.route("/admin/job/<int:job_id>/delete", methods=["POST", "GET"])
@app.route("/hr/job/<int:job_id>/delete", methods=["POST", "GET"])
@admin_required
def admin_job_delete(job_id):
    job = Job.query.get_or_404(job_id)
    application_count = Application.query.filter_by(job_id=job.id).count()
    if application_count > 0:
        flash(f"ይህ vacancy የተመዘገቡ {application_count} application(s) አሉት። ስለዚህ መሰረዝ አይቻልም። Toggle በማድረግ ዝጋው።", "warning")
        return redirect(url_for("admin_jobs"))

    try:
        old_banner = job.banner_image
        db.session.delete(job)
        db.session.commit()
        if old_banner:
            delete_job_image(old_banner)
        log_audit("Deleted Job", f"Deleted job: {job.title}", "Job", job_id)
        flash("የስራ ማስታወቂያው በስኬት ተሰርዟል!", "success")
    except Exception:
        db.session.rollback()
        traceback.print_exc()
        flash("ማስታወቂያውን ለማጥፋት ችግር አጋጥሟል!", "danger")

    return redirect(url_for("admin_jobs"))

@app.route("/admin/interviews")
@app.route("/hr/interviews")
@admin_required
def admin_interviews():
    interviews = Interview.query.order_by(Interview.scheduled_at.desc()).all()
    return render_template("admin/interviews.html", interviews=interviews)

@app.route("/admin/talent-pool")
@app.route("/hr/talent-pool")
@admin_required
def admin_talent_pool():
    candidates = TalentPool.query.order_by(TalentPool.submitted_at.desc()).all()
    return render_template("admin/talent_pool.html", candidates=candidates)

@app.route("/admin/audit-log")
@app.route("/hr/audit-log")
@admin_required
def admin_audit_log():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/audit_log.html", logs=logs)

# ============================================================
# DATABASE MIGRATION & SEEDING
# ============================================================

def safe_add_column(table_name, column_name, column_type):
    try:
        inspector = inspect(db.engine)
        if table_name not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if column_name in columns:
            return

        type_str = str(column_type).upper()
        default_clause = ""
        if "DATETIME" in type_str or "TIMESTAMP" in type_str:
            default_clause = " DEFAULT CURRENT_TIMESTAMP"
        elif "BOOLEAN" in type_str:
            default_clause = " DEFAULT FALSE"
        elif "INTEGER" in type_str:
            default_clause = " DEFAULT 0"
        elif "VARCHAR" in type_str or "TEXT" in type_str:
            default_clause = " DEFAULT ''"

        with db.engine.begin() as connection:
            connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}{default_clause}'))
        print(f"[DB AUTO-MIGRATION] Added missing column: {table_name}.{column_name}")
    except Exception as e:
        print(f"[DB WARNING] Could not add column {table_name}.{column_name}: {e}")

def migrate_existing_database():
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    db.create_all()

    models = [AdminUser, Department, Location, Job, Application, TalentPool, Interview, Notification, AuditLog]
    for model in models:
        table_name = model.__tablename__
        if table_name not in existing_tables:
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column in model.__table__.columns:
            if column.name in existing_columns or column.primary_key:
                continue
            try:
                dialect = db.engine.dialect
                column_type = column.type.compile(dialect=dialect)
            except Exception:
                column_type = "TEXT"
            safe_add_column(table_name, column.name, column_type)

def seed_default_data():
    admin = AdminUser.query.filter_by(username=app.config["HR_USERNAME"]).first()
    if not admin:
        db.session.add(AdminUser(username=app.config["HR_USERNAME"], password_hash=app.config["HR_PASSWORD_HASH"]))

    departments = [
        "Front Office", "Housekeeping", "Food & Beverage", "Kitchen",
        "Engineering", "Finance", "Human Resources", "IT",
        "Security", "Spa & Wellness", "Sales & Marketing"
    ]
    for name in departments:
        if not Department.query.filter_by(name=name).first():
            db.session.add(Department(name=name))

    if not Location.query.filter_by(name="Hawassa").first():
        db.session.add(Location(name="Hawassa", address="Hawassa, Sidama Region, Ethiopia"))

    db.session.commit()

def init_db_safe():
    with app.app_context():
        try:
            db.create_all()
            migrate_existing_database()
            seed_default_data()
            print("======================================")
            print("DATABASE INITIALIZATION SUCCESS")
            print("======================================")
        except Exception:
            db.session.rollback()
            print("======================================")
            print("DATABASE INITIALIZATION ERROR")
            print("======================================")
            traceback.print_exc()

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):
    return render_template("404.html"), 404

@app.errorhandler(413)
def file_too_large(error):
    flash("File is too large. Maximum size is 10 MB.", "danger")
    return redirect(request.referrer or url_for("home"))

@app.errorhandler(500)
def internal_server_error(error):
    try:
        db.session.rollback()
    except Exception:
        pass
    print("======================================")
    print("INTERNAL SERVER ERROR")
    traceback.print_exc()
    print("======================================")
    return render_template("500.html"), 500

# ============================================================
# STARTUP & MAIN
# ============================================================

try:
    init_db_safe()
except Exception:
    traceback.print_exc()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
