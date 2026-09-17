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

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")


class Config:

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "change-this-secret-key-in-production-rori-2026"
    )

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if DATABASE_URL:

        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace(
                "postgres://",
                "postgresql://",
                1
            )

        SQLALCHEMY_DATABASE_URI = DATABASE_URL

    else:

        SQLALCHEMY_DATABASE_URI = (
            "sqlite:///"
            + os.path.join(
                BASE_DIR,
                "instance",
                "database.db"
            )
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300
    }

    # ========================================================
    # LOCAL FILE UPLOADS
    # ========================================================

    UPLOAD_FOLDER = os.path.join(
        BASE_DIR,
        "uploads",
        "resumes"
    )

    UPLOAD_FOLDER_JOBS = os.path.join(
        BASE_DIR,
        "static",
        "uploads",
        "jobs"
    )

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    ALLOWED_EXTENSIONS = {
        "pdf",
        "doc",
        "docx"
    }

    ALLOWED_IMAGE_EXTENSIONS = {
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp"
    }

    # ========================================================
    # CLOUDINARY
    # ========================================================

    CLOUDINARY_CLOUD_NAME = os.environ.get(
        "CLOUDINARY_CLOUD_NAME"
    )

    CLOUDINARY_API_KEY = os.environ.get(
        "CLOUDINARY_API_KEY"
    )

    CLOUDINARY_API_SECRET = os.environ.get(
        "CLOUDINARY_API_SECRET"
    )

    CLOUDINARY_CV_FOLDER = os.environ.get(
        "CLOUDINARY_CV_FOLDER",
        "rori-hotel-cv"
    )

    # ========================================================
    # HR LOGIN
    # ========================================================

    HR_USERNAME = (
        os.environ.get("HR_USERNAME")
        or os.environ.get("ADMIN_USERNAME")
        or "admin"
    )

    HR_PASSWORD_HASH = os.environ.get(
        "HR_PASSWORD_HASH"
    )

    if not HR_PASSWORD_HASH:

        raw_password = (
            os.environ.get("HR_PASSWORD")
            or os.environ.get("ADMIN_PASSWORD")
            or "RoriHR2026"
        )

        HR_PASSWORD_HASH = generate_password_hash(
            raw_password
        )

    # ========================================================
    # MAIL
    # ========================================================

    MAIL_SERVER = os.environ.get(
        "MAIL_SERVER",
        "smtp.gmail.com"
    )

    MAIL_PORT = int(
        os.environ.get(
            "MAIL_PORT",
            587
        )
    )

    MAIL_USE_TLS = (
        os.environ.get(
            "MAIL_USE_TLS",
            "true"
        ).lower()
        in ["true", "1", "on"]
    )

    MAIL_USE_SSL = (
        os.environ.get(
            "MAIL_USE_SSL",
            "false"
        ).lower()
        in ["true", "1", "on"]
    )

    MAIL_USERNAME = os.environ.get(
        "MAIL_USERNAME"
    )

    MAIL_PASSWORD = os.environ.get(
        "MAIL_PASSWORD"
    )

    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        "noreply@rorihotel.com"
    )


# ============================================================
# APPLICATION INITIALIZATION
# ============================================================

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=os.path.join(BASE_DIR, "static")
)

app.config.from_object(Config)

db = SQLAlchemy(app)
mail = Mail(app)


# ============================================================
# CLOUDINARY CONFIGURATION
# ============================================================

if (
    CLOUDINARY_AVAILABLE
    and app.config.get("CLOUDINARY_CLOUD_NAME")
    and app.config.get("CLOUDINARY_API_KEY")
    and app.config.get("CLOUDINARY_API_SECRET")
):

    cloudinary.config(
        cloud_name=app.config["CLOUDINARY_CLOUD_NAME"],
        api_key=app.config["CLOUDINARY_API_KEY"],
        api_secret=app.config["CLOUDINARY_API_SECRET"],
        secure=True
    )

    print(
        "[CLOUDINARY] Configuration loaded successfully."
    )

else:

    print(
        "[CLOUDINARY] WARNING: Cloudinary is not fully configured."
    )


# ============================================================
# TEMPLATE LOADER  (FIXED)
# ============================================================

template_dirs = [
    TEMPLATES_DIR,
    os.path.join(TEMPLATES_DIR, "careers"),
    os.path.join(TEMPLATES_DIR, "application"),
    os.path.join(TEMPLATES_DIR, "auth"),
    os.path.join(TEMPLATES_DIR, "admin"),
    os.path.join(TEMPLATES_DIR, "hr"),
]

existing_template_dirs = [
    d for d in template_dirs
    if os.path.isdir(d)
]

app.jinja_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader(d)
    for d in existing_template_dirs
])

print("======================================")
print("[TEMPLATES] Search paths:")
for _d in existing_template_dirs:
    print("   -", _d)

_admin_dir = os.path.join(TEMPLATES_DIR, "admin")
if os.path.isdir(_admin_dir):
    print("[TEMPLATES] Contents of templates/admin:")
    try:
        for _f in sorted(os.listdir(_admin_dir)):
            print("   *", _f)
    except Exception:
        pass
else:
    print(
        "[TEMPLATES] WARNING: templates/admin directory "
        "does not exist at:",
        _admin_dir
    )
print("======================================")


# ============================================================
# SAFE RENDER  (TemplateNotFound -> friendly fallback)
# ============================================================

def safe_render(template_name, **context):
    """
    Wraps render_template so that a missing template returns
    a helpful fallback page instead of a 500 error.
    """
    try:
        return render_template(template_name, **context)
    except jinja2.TemplateNotFound:

        print(
            f"[TEMPLATE MISSING] {template_name} "
            f"— returning fallback view."
        )

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Template Missing</title>
            <style>
                body {{
                    font-family: system-ui, sans-serif;
                    background: #0b132b;
                    color: #fff;
                    margin: 0;
                    padding: 60px 20px;
                    text-align: center;
                }}
                .box {{
                    max-width: 560px;
                    margin: 0 auto;
                    background: rgba(255,255,255,0.04);
                    border: 1px solid rgba(197,160,89,0.3);
                    border-radius: 16px;
                    padding: 40px 30px;
                }}
                h1 {{
                    color: #c5a059;
                    margin-top: 0;
                }}
                code {{
                    background: rgba(0,0,0,0.35);
                    padding: 3px 8px;
                    border-radius: 6px;
                    color: #ffd97d;
                }}
                a {{
                    display: inline-block;
                    margin-top: 24px;
                    color: #c5a059;
                    text-decoration: none;
                    border: 1px solid #c5a059;
                    padding: 10px 22px;
                    border-radius: 8px;
                }}
                a:hover {{ background: rgba(197,160,89,0.1); }}
            </style>
        </head>
        <body>
            <div class="box">
                <h1>Template Missing</h1>
                <p>
                    The template
                    <code>{template_name}</code>
                    was not found on the server.
                </p>
                <p style="color:#8a9199;font-size:13px;">
                    Create it under
                    <code>templates/{template_name}</code>
                    and redeploy.
                </p>
                <a href="/admin/dashboard">
                    ← Back to Dashboard
                </a>
            </div>
        </body>
        </html>
        """


# ============================================================
# DIRECTORIES
# ============================================================

os.makedirs(
    app.config["UPLOAD_FOLDER"],
    exist_ok=True
)

os.makedirs(
    app.config["UPLOAD_FOLDER_JOBS"],
    exist_ok=True
)

os.makedirs(
    os.path.join(BASE_DIR, "instance"),
    exist_ok=True
)


# ============================================================
# MODELS
# ============================================================

class AdminUser(db.Model):

    __tablename__ = "admin_users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    def __repr__(self):
        return f"<AdminUser {self.username}>"


class Department(db.Model):

    __tablename__ = "departments"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    icon = db.Column(
        db.String(50),
        nullable=True
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    jobs = db.relationship(
        "Job",
        backref="department_ref",
        lazy=True
    )

    def __repr__(self):
        return f"<Department {self.name}>"


class Location(db.Model):

    __tablename__ = "locations"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    address = db.Column(
        db.String(200),
        nullable=True
    )

    jobs = db.relationship(
        "Job",
        backref="location_ref",
        lazy=True
    )

    def __repr__(self):
        return f"<Location {self.name}>"


class Job(db.Model):

    __tablename__ = "jobs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    title = db.Column(
        db.String(120),
        nullable=False
    )

    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id"),
        nullable=True
    )

    location_id = db.Column(
        db.Integer,
        db.ForeignKey("locations.id"),
        nullable=True
    )

    short_description = db.Column(
        db.String(200),
        nullable=False
    )

    full_description = db.Column(
        db.Text,
        nullable=False
    )

    responsibilities = db.Column(
        db.Text,
        nullable=False
    )

    requirements = db.Column(
        db.Text,
        nullable=False
    )

    what_we_offer = db.Column(
        db.Text,
        nullable=False
    )

    employment_type = db.Column(
        db.String(30),
        nullable=False,
        default="Full-time"
    )

    experience_level = db.Column(
        db.String(30),
        nullable=True
    )

    salary_range = db.Column(
        db.String(100),
        nullable=True
    )

    deadline = db.Column(
        db.Date,
        nullable=True
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    is_featured = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    banner_image = db.Column(
        db.String(255),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    applications = db.relationship(
        "Application",
        backref="job",
        lazy=True
    )

    @property
    def department(self):
        return self.department_ref

    @property
    def location(self):
        return self.location_ref

    def responsibilities_list(self):

        return [
            item.strip()
            for item in (
                self.responsibilities or ""
            ).splitlines()
            if item.strip()
        ]

    def requirements_list(self):

        return [
            item.strip()
            for item in (
                self.requirements or ""
            ).splitlines()
            if item.strip()
        ]

    def what_we_offer_list(self):

        return [
            item.strip()
            for item in (
                self.what_we_offer or ""
            ).splitlines()
            if item.strip()
        ]

    @property
    def department_name(self):

        return (
            self.department_ref.name
            if self.department_ref
            else "Not specified"
        )

    @property
    def location_name(self):

        return (
            self.location_ref.name
            if self.location_ref
            else "Hawassa"
        )

    @property
    def is_expired(self):

        if not self.deadline:
            return False

        return (
            self.deadline
            < datetime.utcnow().date()
        )

    def __repr__(self):
        return f"<Job {self.title}>"


class Application(db.Model):

    __tablename__ = "applications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    job_id = db.Column(
        db.Integer,
        db.ForeignKey("jobs.id"),
        nullable=False
    )

    reference_no = db.Column(
        db.String(20),
        unique=True,
        nullable=True
    )

    full_name = db.Column(
        db.String(120),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        nullable=False
    )

    phone = db.Column(
        db.String(30),
        nullable=False
    )

    location = db.Column(
        db.String(120),
        nullable=False
    )

    education = db.Column(
        db.String(60),
        nullable=False
    )

    years_of_experience = db.Column(
        db.String(30),
        nullable=False
    )

    current_position = db.Column(
        db.String(120),
        nullable=True
    )

    previous_employer = db.Column(
        db.String(120),
        nullable=True
    )

    skills = db.Column(
        db.String(255),
        nullable=False
    )

    languages = db.Column(
        db.String(255),
        nullable=False
    )

    certifications = db.Column(
        db.String(255),
        nullable=True
    )

    availability_date = db.Column(
        db.Date,
        nullable=True
    )

    willing_to_relocate = db.Column(
        db.String(10),
        nullable=True
    )

    expected_salary = db.Column(
        db.String(50),
        nullable=True
    )

    cover_letter = db.Column(
        db.Text,
        nullable=False
    )

    cv_filename = db.Column(
        db.String(255),
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="NEW",
        nullable=False
    )

    status_updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    tags = db.Column(
        db.String(255),
        nullable=True
    )

    reviewed_by = db.Column(
        db.String(120),
        nullable=True
    )

    shortlisted_at = db.Column(
        db.DateTime,
        nullable=True
    )

    rejected_at = db.Column(
        db.DateTime,
        nullable=True
    )

    viewed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    submitted_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return f"<Application {self.full_name}>"


class TalentPool(db.Model):

    __tablename__ = "talent_pool"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    full_name = db.Column(
        db.String(120),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    phone = db.Column(
        db.String(30),
        nullable=False
    )

    location = db.Column(
        db.String(120),
        nullable=False
    )

    education = db.Column(
        db.String(60),
        nullable=False
    )

    years_of_experience = db.Column(
        db.String(30),
        nullable=False
    )

    skills = db.Column(
        db.String(255),
        nullable=False
    )

    languages = db.Column(
        db.String(255),
        nullable=False
    )

    certifications = db.Column(
        db.String(255),
        nullable=True
    )

    availability_date = db.Column(
        db.Date,
        nullable=True
    )

    willing_to_relocate = db.Column(
        db.String(10),
        nullable=True
    )

    expected_salary = db.Column(
        db.String(50),
        nullable=True
    )

    cover_letter = db.Column(
        db.Text,
        nullable=False
    )

    cv_filename = db.Column(
        db.String(255),
        nullable=False
    )

    submitted_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )


class Interview(db.Model):

    __tablename__ = "interviews"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    application_id = db.Column(
        db.Integer,
        db.ForeignKey("applications.id"),
        nullable=False
    )

    scheduled_at = db.Column(
        db.DateTime,
        nullable=False
    )

    duration_minutes = db.Column(
        db.Integer,
        default=30
    )

    interview_type = db.Column(
        db.String(50),
        default="In-person"
    )

    interviewer_name = db.Column(
        db.String(120),
        nullable=True
    )

    location = db.Column(
        db.String(200),
        nullable=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    evaluation = db.Column(
        db.Text,
        nullable=True
    )

    rating = db.Column(
        db.Integer,
        nullable=True
    )

    decision = db.Column(
        db.String(30),
        nullable=True
    )

    status = db.Column(
        db.String(30),
        default="Scheduled"
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    application = db.relationship(
        "Application",
        backref="interviews",
        lazy=True
    )


class Notification(db.Model):

    __tablename__ = "notifications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    recipient = db.Column(
        db.String(120),
        nullable=True
    )

    is_read = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class AuditLog(db.Model):

    __tablename__ = "audit_logs"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        nullable=True
    )

    user_name = db.Column(
        db.String(120),
        nullable=True
    )

    action = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    target_type = db.Column(
        db.String(100),
        nullable=True
    )

    target_id = db.Column(
        db.Integer,
        nullable=True
    )

    ip_address = db.Column(
        db.String(45),
        nullable=True
    )

    user_agent = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )


# ============================================================
# FORMS
# ============================================================

class ApplicationForm(FlaskForm):

    full_name = StringField(
        "Full Name",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    email = StringField(
        "Email",
        validators=[
            DataRequired(),
            Email(),
            Length(max=120)
        ]
    )

    phone = StringField(
        "Phone",
        validators=[
            DataRequired(),
            Length(max=30)
        ]
    )

    location = StringField(
        "Current Location",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    education = SelectField(
        "Highest Education Level",
        choices=[
            ("High School", "High School Diploma"),
            (
                "Technical Diploma",
                "TVET / Advanced Diploma"
            ),
            (
                "Bachelor Degree",
                "Bachelor's Degree"
            ),
            (
                "Master Degree",
                "Master's Degree / Doctorate"
            )
        ],
        validators=[DataRequired()]
    )

    years_of_experience = StringField(
        "Years of Experience",
        validators=[
            DataRequired(),
            Length(max=30)
        ]
    )

    current_position = StringField(
        "Current Position",
        validators=[
            Optional(),
            Length(max=120)
        ]
    )

    previous_employer = StringField(
        "Previous Employer",
        validators=[
            Optional(),
            Length(max=120)
        ]
    )

    skills = StringField(
        "Key Skills",
        validators=[
            DataRequired(),
            Length(max=255)
        ]
    )

    languages = StringField(
        "Languages Spoken",
        validators=[
            DataRequired(),
            Length(max=255)
        ]
    )

    certifications = StringField(
        "Professional Certifications",
        validators=[
            Optional(),
            Length(max=255)
        ]
    )

    availability_date = DateField(
        "Earliest Availability Date",
        validators=[Optional()],
        format="%Y-%m-%d"
    )

    willing_to_relocate = SelectField(
        "Willing to Relocate?",
        choices=[
            ("Yes", "Yes"),
            ("No", "No")
        ],
        validators=[DataRequired()]
    )

    expected_salary = StringField(
        "Expected Monthly Salary",
        validators=[
            Optional(),
            Length(max=50)
        ]
    )

    cover_letter = TextAreaField(
        "Cover Letter",
        validators=[
            DataRequired(),
            Length(max=5000)
        ]
    )

    cv_file = FileField(
        "Upload CV",
        validators=[DataRequired()]
    )


class TalentPoolForm(ApplicationForm):
    pass


class JobForm(FlaskForm):

    title = StringField(
        "Job Title",
        validators=[
            DataRequired(),
            Length(max=120)
        ]
    )

    department_id = SelectField(
        "Department",
        coerce=int,
        validators=[Optional()]
    )

    location_id = SelectField(
        "Location",
        coerce=int,
        validators=[Optional()]
    )

    short_description = StringField(
        "Short Description",
        validators=[
            DataRequired(),
            Length(max=200)
        ]
    )

    full_description = TextAreaField(
        "Full Description",
        validators=[DataRequired()]
    )

    responsibilities = TextAreaField(
        "Responsibilities",
        validators=[DataRequired()]
    )

    requirements = TextAreaField(
        "Requirements",
        validators=[DataRequired()]
    )

    what_we_offer = TextAreaField(
        "What We Offer",
        validators=[DataRequired()]
    )

    employment_type = SelectField(
        "Employment Type",
        choices=[
            ("Full-time", "Full-time"),
            ("Part-time", "Part-time"),
            ("Contract", "Contract")
        ],
        validators=[DataRequired()]
    )

    experience_level = StringField(
        "Experience Level",
        validators=[
            Optional(),
            Length(max=30)
        ]
    )

    salary_range = StringField(
        "Salary Range",
        validators=[
            Optional(),
            Length(max=100)
        ]
    )

    deadline = DateField(
        "Application Deadline",
        validators=[Optional()],
        format="%Y-%m-%d"
    )

    is_active = BooleanField(
        "Active",
        default=True
    )

    is_featured = BooleanField(
        "Featured",
        default=False
    )


class AdminLoginForm(FlaskForm):

    username = StringField(
        "Username",
        validators=[DataRequired()]
    )

    password = PasswordField(
        "Password",
        validators=[DataRequired()]
    )


class ChangePasswordForm(FlaskForm):

    current_password = PasswordField(
        "Current Password",
        validators=[DataRequired()]
    )

    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(
                min=6,
                message="Password must be at least 6 characters"
            )
        ]
    )

    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[
            DataRequired(),
            EqualTo(
                "new_password",
                message="Passwords must match"
            )
        ]
    )


class InterviewForm(FlaskForm):

    application_id = SelectField(
        "Candidate",
        coerce=int,
        validators=[DataRequired()]
    )

    scheduled_at = StringField(
        "Scheduled Date/Time",
        validators=[DataRequired()]
    )

    duration_minutes = IntegerField(
        "Duration",
        default=30,
        validators=[
            NumberRange(
                min=5,
                max=120
            )
        ]
    )

    interview_type = SelectField(
        "Type",
        choices=[
            ("In-person", "In-person"),
            ("Virtual", "Virtual"),
            ("Phone", "Phone")
        ],
        default="In-person"
    )

    interviewer_name = StringField(
        "Interviewer Name",
        validators=[
            Optional(),
            Length(max=120)
        ]
    )

    location = StringField(
        "Location / Meeting Link",
        validators=[
            Optional(),
            Length(max=200)
        ]
    )

    notes = TextAreaField(
        "Notes",
        validators=[Optional()]
    )


# ============================================================
# FILE HELPERS
# ============================================================

def allowed_file(filename):

    return bool(
        filename
        and "."
        in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in app.config["ALLOWED_EXTENSIONS"]
    )


def allowed_image_file(filename):

    return bool(
        filename
        and "."
        in filename
        and filename.rsplit(
            ".",
            1
        )[1].lower()
        in app.config["ALLOWED_IMAGE_EXTENSIONS"]
    )


# ============================================================
# CLOUDINARY HELPERS
# ============================================================

def cloudinary_ready():

    return bool(
        CLOUDINARY_AVAILABLE
        and app.config.get("CLOUDINARY_CLOUD_NAME")
        and app.config.get("CLOUDINARY_API_KEY")
        and app.config.get("CLOUDINARY_API_SECRET")
    )


def is_cloudinary_cv(filename):

    return bool(
        filename
        and filename.startswith("cloudinary:")
    )


def parse_cloudinary_cv(filename):

    if not is_cloudinary_cv(filename):
        return None, None

    value = filename[len("cloudinary:"):]

    if "|" not in value:
        return None, None

    public_id, extension = value.rsplit(
        "|",
        1
    )

    public_id = public_id.strip()
    extension = extension.strip().lower()

    if not public_id:
        return None, None

    if extension not in app.config[
        "ALLOWED_EXTENSIONS"
    ]:
        return None, None

    return public_id, extension


def save_uploaded_file(file):

    if not file or not file.filename:
        return None

    if not allowed_file(file.filename):
        return None

    original = secure_filename(
        file.filename
    )

    if not original:
        return None

    name, ext = os.path.splitext(
        original
    )

    extension = ext.lower().lstrip(".")

    timestamp = datetime.utcnow().strftime(
        "%Y%m%d%H%M%S%f"
    )

    safe_name = secure_filename(
        name
    ) or "cv"

    unique_name = (
        f"{safe_name}_{timestamp}"
    )

    if cloudinary_ready():

        try:

            upload_result = cloudinary.uploader.upload(
                file,
                resource_type="raw",
                type="authenticated",
                folder=app.config[
                    "CLOUDINARY_CV_FOLDER"
                ],
                public_id=unique_name,
                overwrite=False
            )

            public_id = upload_result.get(
                "public_id"
            )

            if not public_id:
                raise RuntimeError(
                    "Cloudinary did not return public_id."
                )

            stored_reference = (
                "cloudinary:"
                + public_id
                + "|"
                + extension
            )

            print(
                "[CLOUDINARY] CV uploaded:",
                public_id
            )

            return stored_reference

        except Exception as e:

            print(
                "[CLOUDINARY] CV upload failed:",
                e
            )

            traceback.print_exc()

            return None

    filename = (
        f"{unique_name}"
        f".{extension}"
    )

    path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    try:

        os.makedirs(
            app.config["UPLOAD_FOLDER"],
            exist_ok=True
        )

        file.save(path)

        if not os.path.isfile(path):
            return None

        return filename

    except Exception:

        traceback.print_exc()

        return None


def delete_uploaded_file(filename):

    if not filename:
        return

    if is_cloudinary_cv(filename):

        public_id, extension = parse_cloudinary_cv(
            filename
        )

        if not public_id:
            return

        if not cloudinary_ready():
            return

        try:

            cloudinary.uploader.destroy(
                public_id,
                resource_type="raw",
                type="authenticated"
            )

            print(
                "[CLOUDINARY] CV deleted:",
                public_id
            )

        except Exception:

            traceback.print_exc()

        return

    try:

        safe_filename = secure_filename(
            os.path.basename(filename)
        )

        if not safe_filename:
            return

        upload_directories = [
            app.config.get(
                "UPLOAD_FOLDER"
            ),

            os.path.join(
                BASE_DIR,
                "uploads",
                "resumes"
            ),

            os.path.join(
                BASE_DIR,
                "uploads"
            ),

            os.path.join(
                app.root_path,
                "static",
                "uploads",
                "resumes"
            ),

            os.path.join(
                app.root_path,
                "static",
                "uploads"
            )
        ]

        for directory in upload_directories:

            if not directory:
                continue

            path = os.path.join(
                directory,
                safe_filename
            )

            if os.path.isfile(path):

                os.remove(path)

                print(
                    "[LOCAL] CV deleted:",
                    path
                )

                break

    except Exception:

        traceback.print_exc()


def generate_cloudinary_cv_url(filename):

    public_id, extension = parse_cloudinary_cv(
        filename
    )

    if not public_id:
        return None

    if not cloudinary_ready():
        return None

    try:

        expires_at = int(
            (
                datetime.utcnow()
                + timedelta(minutes=10)
            ).timestamp()
        )

        url = cloudinary.utils.private_download_url(
            public_id,
            extension,
            resource_type="raw",
            type="authenticated",
            attachment=False,
            expires_at=expires_at
        )

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

    if not allowed_image_file(
        file.filename
    ):
        return None

    original = secure_filename(
        file.filename
    )

    if not original:
        return None

    name, ext = os.path.splitext(
        original
    )

    timestamp = datetime.utcnow().strftime(
        "%Y%m%d%H%M%S%f"
    )

    filename = (
        f"{name}_{timestamp}"
        f"{ext.lower()}"
    )

    path = os.path.join(
        app.config["UPLOAD_FOLDER_JOBS"],
        filename
    )

    try:

        os.makedirs(
            app.config["UPLOAD_FOLDER_JOBS"],
            exist_ok=True
        )

        file.save(path)

        if not os.path.isfile(path):
            return None

        return filename

    except Exception:

        traceback.print_exc()

        return None


def delete_job_image(filename):

    if not filename:
        return

    try:

        safe_filename = secure_filename(
            os.path.basename(filename)
        )

        if not safe_filename:
            return

        path = os.path.join(
            app.config["UPLOAD_FOLDER_JOBS"],
            safe_filename
        )

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

        if not session.get(
            "admin_logged_in"
        ):

            flash(
                "እባክዎን አስቀድመው Login ያድርጉ።",
                "warning"
            )

            return redirect(
                url_for(
                    "admin_login"
                )
            )

        return f(*args, **kwargs)

    return decorated


# ============================================================
# AUDIT
# ============================================================

def log_audit(
    action,
    description=None,
    target_type=None,
    target_id=None
):

    try:

        audit = AuditLog(

            user_id=session.get(
                "admin_id"
            ),

            user_name=session.get(
                "admin_username",
                "system"
            ),

            action=action,

            description=description,

            target_type=target_type,

            target_id=target_id,

            ip_address=request.remote_addr,

            user_agent=request.headers.get(
                "User-Agent"
            )
        )

        db.session.add(audit)
        db.session.commit()

    except Exception as e:

        db.session.rollback()

        print(
            f"AUDIT ERROR: {e}"
        )


# ============================================================
# EMAIL
# ============================================================

def send_async_email(message):

    try:

        with app.app_context():
            mail.send(message)

    except Exception as e:

        print(
            f"EMAIL ERROR: {e}"
        )


def send_application_status_email(
    application,
    old_status,
    new_status,
    notes=""
):

    if not app.config.get(
        "MAIL_USERNAME"
    ):
        return

    if not application.email:
        return

    status_messages = {

        "UNDER REVIEW":
            "Your application is currently under review by our HR team.",

        "SHORTLISTED":
            "Congratulations! Your application has been shortlisted for the next stage.",

        "INTERVIEW":
            "Your application has progressed to the interview stage.",

        "SELECTED":
            "Congratulations! You have been selected for the position.",

        "HIRED":
            "Congratulations! You have been hired by Rori Hotel.",

        "REJECTED":
            "We regret to inform you that your application was not successful."
    }

    try:

        reference = (
            application.reference_no
            or f"APP-{application.id}"
        )

        position = (
            application.job.title
            if application.job
            else "Rori Hotel Position"
        )

        status_message = status_messages.get(
            new_status,
            "Your application status has been updated."
        )

        notes_html = ""

        if notes:

            safe_notes = (
                notes
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )

            notes_html = f"""
            <p>
                <strong>HR Note:</strong><br>
                {safe_notes}
            </p>
            """

        message = Message(

            subject=(
                "Rori Hotel - Application Status "
                f"{reference}"
            ),

            sender=app.config[
                "MAIL_DEFAULT_SENDER"
            ],

            recipients=[
                application.email
            ]
        )

        message.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Rori Hotel Careers</title>
        </head>

        <body style="
            margin:0;
            padding:0;
            background:#f4f5f7;
            font-family:Arial,sans-serif;
        ">

        <div style="
            max-width:600px;
            margin:30px auto;
            background:#fff;
            padding:30px;
            border-radius:12px;
        ">

            <h1>Rori Hotel</h1>

            <p>
                Human Resources Department
            </p>

            <hr>

            <p>
                Dear <strong>
                    {application.full_name}
                </strong>,
            </p>

            <p>
                {status_message}
            </p>

            <p>
                <strong>Position:</strong>
                {position}
            </p>

            <p>
                <strong>Status:</strong>
                {new_status}
            </p>

            <p>
                <strong>Reference:</strong>
                {reference}
            </p>

            {notes_html}

            <hr>

            <p style="
                font-size:13px;
                color:#777;
            ">
                Please keep your reference number
                for future application tracking.
            </p>

            <p style="
                font-size:12px;
                color:#999;
            ">
                © 2026 Rori Hotel.
                All rights reserved.
            </p>

        </div>

        </body>
        </html>
        """

        Thread(
            target=send_async_email,
            args=(message,),
            daemon=True
        ).start()

    except Exception as e:

        print(
            f"EMAIL DISPATCH ERROR: {e}"
        )


# ============================================================
# INTERVIEW EMAIL + NOTIFICATION HELPERS
# ============================================================

def _format_interview_when(interview):

    try:
        return interview.scheduled_at.strftime(
            "%A, %B %d, %Y at %H:%M"
        )
    except Exception:
        return str(interview.scheduled_at)


def send_interview_email(
    application,
    interview,
    event="scheduled",
    extra_note=None
):

    if not app.config.get("MAIL_USERNAME"):
        return

    if not application or not application.email:
        return

    try:

        position = (
            application.job.title
            if application.job
            else "Rori Hotel Position"
        )

        reference = (
            application.reference_no
            or f"APP-{application.id}"
        )

        when = _format_interview_when(interview)

        subject_map = {
            "scheduled":
                f"Rori Hotel - Interview Scheduled ({reference})",
            "rescheduled":
                f"Rori Hotel - Interview Rescheduled ({reference})",
            "cancelled":
                f"Rori Hotel - Interview Cancelled ({reference})",
            "completed":
                f"Rori Hotel - Interview Completed ({reference})",
        }

        subject = subject_map.get(
            event,
            subject_map["scheduled"]
        )

        type_text = (
            interview.interview_type
            or "In-person"
        )

        location_text = (
            interview.location
            or "To be confirmed"
        )

        interviewer_text = (
            interview.interviewer_name
            or "To be confirmed"
        )

        duration_text = (
            f"{interview.duration_minutes} minutes"
            if interview.duration_minutes
            else "—"
        )

        extra_html = ""

        if extra_note:

            safe_extra = (
                extra_note
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )

            extra_html = (
                f"<p><strong>Additional Note:</strong><br>"
                f"{safe_extra}</p>"
            )

        headline = {
            "scheduled":
                "Your interview has been scheduled.",
            "rescheduled":
                "Your interview has been rescheduled.",
            "cancelled":
                "Your interview has been cancelled.",
            "completed":
                "Your interview has been marked as completed.",
        }.get(event, "Interview update.")

        message = Message(
            subject=subject,
            sender=app.config["MAIL_DEFAULT_SENDER"],
            recipients=[application.email]
        )

        message.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Rori Hotel Careers</title>
        </head>

        <body style="
            margin:0;
            padding:0;
            background:#f4f5f7;
            font-family:Arial,sans-serif;
        ">

        <div style="
            max-width:600px;
            margin:30px auto;
            background:#fff;
            padding:30px;
            border-radius:12px;
        ">

            <h1 style="margin-top:0;">Rori Hotel</h1>

            <p style="color:#666;margin-top:-8px;">
                Human Resources Department
            </p>

            <hr>

            <p>
                Dear <strong>{application.full_name}</strong>,
            </p>

            <p>{headline}</p>

            <p>
                <strong>Position:</strong> {position}<br>
                <strong>Reference:</strong> {reference}<br>
                <strong>Status:</strong> {interview.status or "Scheduled"}
            </p>

            <p>
                <strong>Date &amp; Time:</strong> {when}<br>
                <strong>Duration:</strong> {duration_text}<br>
                <strong>Type:</strong> {type_text}<br>
                <strong>Location / Link:</strong> {location_text}<br>
                <strong>Interviewer:</strong> {interviewer_text}
            </p>

            {extra_html}

            <hr>

            <p style="font-size:13px;color:#777;">
                Please keep your reference number for
                future application tracking.
            </p>

            <p style="font-size:12px;color:#999;">
                © 2026 Rori Hotel. All rights reserved.
            </p>

        </div>

        </body>
        </html>
        """

        Thread(
            target=send_async_email,
            args=(message,),
            daemon=True
        ).start()

    except Exception as e:

        print(
            f"INTERVIEW EMAIL ERROR: {e}"
        )


def create_interview_notification(
    application,
    interview,
    event="scheduled"
):

    if not application:
        return

    try:

        position = (
            application.job.title
            if application.job
            else "Rori Hotel Position"
        )

        when = _format_interview_when(interview)

        parts = [
            f"{event.capitalize()} interview for {position}",
            f"Date/Time: {when}",
        ]

        if interview.interview_type:
            parts.append(f"Type: {interview.interview_type}")

        if interview.location:
            parts.append(f"Location/Link: {interview.location}")

        if interview.interviewer_name:
            parts.append(
                f"Interviewer: {interview.interviewer_name}"
            )

        parts.append(
            f"Reference: "
            f"{application.reference_no or f'APP-{application.id}'}"
        )

        notification = Notification(
            title=(
                f"Interview {event.capitalize()}"
            ),
            message=" | ".join(parts),
            recipient=application.email,
            is_read=False
        )

        db.session.add(notification)
        db.session.commit()

    except Exception:

        db.session.rollback()
        traceback.print_exc()


def apply_interview_side_effects(
    application,
    interview,
    event="scheduled",
    extra_note=None
):

    if not application:
        return

    try:

        if application.status not in (
            "SELECTED",
            "HIRED",
            "REJECTED"
        ):

            application.status = "INTERVIEW"
            application.status_updated_at = datetime.utcnow()
            application.reviewed_by = session.get(
                "admin_username"
            )

            db.session.commit()

    except Exception:

        db.session.rollback()
        traceback.print_exc()

    create_interview_notification(
        application,
        interview,
        event=event
    )

    send_interview_email(
        application,
        interview,
        event=event,
        extra_note=extra_note
    )


# ============================================================
# SIMILAR JOBS
# ============================================================

def get_similar_jobs(
    job,
    limit=3
):

    query = Job.query.filter(
        Job.is_active.is_(True),
        Job.id != job.id
    )

    if job.department_id:

        query = query.filter(
            db.or_(
                Job.department_id
                == job.department_id,

                Job.employment_type
                == job.employment_type
            )
        )

    return (
        query
        .order_by(
            Job.created_at.desc()
        )
        .limit(limit)
        .all()
    )


# ============================================================
# CONTEXT
# ============================================================

@app.context_processor
def inject_globals():

    try:

        return {

            "now": datetime.utcnow,

            "all_departments":
                Department.query
                .order_by(
                    Department.name
                )
                .all(),

            "all_locations":
                Location.query
                .order_by(
                    Location.name
                )
                .all()
        }

    except Exception:

        return {

            "now": datetime.utcnow,

            "all_departments": [],

            "all_locations": []
        }


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    featured_jobs = (
        Job.query
        .filter_by(
            is_active=True,
            is_featured=True
        )
        .order_by(
            Job.created_at.desc()
        )
        .limit(6)
        .all()
    )

    latest_jobs = (
        Job.query
        .filter_by(
            is_active=True
        )
        .order_by(
            Job.created_at.desc()
        )
        .limit(6)
        .all()
    )

    return render_template(
        "home.html",
        featured_jobs=featured_jobs,
        latest_jobs=latest_jobs,
        departments=(
            Department.query
            .order_by(
                Department.name
            )
            .all()
        )
    )


# ============================================================
# PUBLIC JOBS
# ============================================================

@app.route("/jobs")
def jobs():

    department_id = request.args.get(
        "department",
        type=int
    )

    location_id = request.args.get(
        "location",
        type=int
    )

    type_filter = request.args.get(
        "type",
        ""
    ).strip()

    experience_filter = request.args.get(
        "experience",
        ""
    ).strip()

    search_query = request.args.get(
        "q",
        ""
    ).strip()

    query = Job.query.filter(
        Job.is_active.is_(True)
    )

    if department_id:

        query = query.filter(
            Job.department_id
            == department_id
        )

    if location_id:

        query = query.filter(
            Job.location_id
            == location_id
        )

    if type_filter:

        query = query.filter(
            Job.employment_type
            == type_filter
        )

    if experience_filter:

        query = query.filter(
            Job.experience_level
            == experience_filter
        )

    if search_query:

        search = f"%{search_query}%"

        query = query.filter(
            db.or_(
                Job.title.ilike(search),
                Job.short_description.ilike(search),
                Job.full_description.ilike(search)
            )
        )

    jobs_list = (
        query
        .order_by(
            Job.created_at.desc()
        )
        .all()
    )

    return render_template(
        "jobs.html",
        jobs=jobs_list,
        departments=Department.query.all(),
        locations=Location.query.all()
    )


# ============================================================
# JOB DETAIL
# ============================================================

@app.route(
    "/job/<int:job_id>"
)
def job_detail(job_id):

    job = Job.query.get_or_404(
        job_id
    )

    return render_template(
        "job_detail.html",
        job=job,
        similar_jobs=get_similar_jobs(job)
    )


# ============================================================
# DEPARTMENTS
# ============================================================

@app.route("/departments")
def departments():

    return render_template(
        "departments.html",
        departments=Department.query.all()
    )


@app.route(
    "/department/<int:dept_id>"
)
def department_detail(dept_id):

    department = (
        Department.query
        .get_or_404(dept_id)
    )

    jobs_list = (
        Job.query
        .filter_by(
            department_id=dept_id,
            is_active=True
        )
        .order_by(
            Job.created_at.desc()
        )
        .all()
    )

    return render_template(
        "department_detail.html",
        department=department,
        jobs=jobs_list
    )


# ============================================================
# LOCATIONS
# ============================================================

@app.route("/locations")
def locations():

    return render_template(
        "locations.html",
        locations=Location.query.all()
    )


# ============================================================
# ABOUT
# ============================================================

@app.route("/about-careers")
def about_careers():

    return render_template(
        "about_careers.html"
    )


# ============================================================
# TRACK STATUS
# ============================================================

@app.route(
    "/track-status",
    methods=["GET", "POST"]
)
@app.route(
    "/application/lookup",
    methods=["GET", "POST"]
)
def track_status():

    application = None
    searched = False

    if request.method == "POST":

        searched = True

        reference_no = (
            request.form
            .get(
                "reference_no",
                ""
            )
            .strip()
            .upper()
        )

        if reference_no:

            application = (
                Application.query
                .filter_by(
                    reference_no=reference_no
                )
                .first()
            )

    return render_template(
        "track_status.html",
        application=application,
        searched=searched
    )


# ============================================================
# APPLY
# ============================================================

@app.route(
    "/apply/<int:job_id>",
    methods=["GET", "POST"]
)
def apply(job_id):

    job = Job.query.get_or_404(
        job_id
    )

    if not job.is_active:

        flash(
            "This position is no longer accepting applications.",
            "warning"
        )

        return redirect(
            url_for(
                "job_detail",
                job_id=job.id
            )
        )

    if job.is_expired:

        flash(
            "The application deadline has passed.",
            "warning"
        )

        return redirect(
            url_for(
                "job_detail",
                job_id=job.id
            )
        )

    form = ApplicationForm()

    if form.validate_on_submit():

        cv_filename = save_uploaded_file(
            form.cv_file.data
        )

        if not cv_filename:

            flash(
                "CV upload failed. "
                "Please upload PDF, DOC, or DOCX.",
                "danger"
            )

            return render_template(
                "apply.html",
                form=form,
                job=job
            )

        reference_no = None

        for _ in range(20):

            candidate_reference = (
                "RH-"
                + secrets.token_hex(
                    4
                ).upper()
            )

            exists = (
                Application.query
                .filter_by(
                    reference_no=
                    candidate_reference
                )
                .first()
            )

            if not exists:

                reference_no = (
                    candidate_reference
                )

                break

        if not reference_no:

            delete_uploaded_file(
                cv_filename
            )

            flash(
                "Could not generate application reference number.",
                "danger"
            )

            return render_template(
                "apply.html",
                form=form,
                job=job
            )

        application = Application(

            job_id=job.id,

            reference_no=reference_no,

            full_name=(
                form.full_name.data
                .strip()
            ),

            email=(
                form.email.data
                .strip()
                .lower()
            ),

            phone=(
                form.phone.data
                .strip()
            ),

            location=(
                form.location.data
                .strip()
            ),

            education=form.education.data,

            years_of_experience=(
                form.years_of_experience.data
                .strip()
            ),

            current_position=(
                form.current_position.data
                .strip()
                if form.current_position.data
                else None
            ),

            previous_employer=(
                form.previous_employer.data
                .strip()
                if form.previous_employer.data
                else None
            ),

            skills=(
                form.skills.data
                .strip()
            ),

            languages=(
                form.languages.data
                .strip()
            ),

            certifications=(
                form.certifications.data
                .strip()
                if form.certifications.data
                else None
            ),

            availability_date=(
                form.availability_date.data
            ),

            willing_to_relocate=(
                form.willing_to_relocate.data
            ),

            expected_salary=(
                form.expected_salary.data
                .strip()
                if form.expected_salary.data
                else None
            ),

            cover_letter=(
                form.cover_letter.data
                .strip()
            ),

            cv_filename=cv_filename,

            status="NEW",

            status_updated_at=
                datetime.utcnow(),

            submitted_at=
                datetime.utcnow()
        )

        try:

            db.session.add(
                application
            )

            db.session.flush()

            notification = Notification(

                title="New Application",

                message=(
                    f"{application.full_name} "
                    f"applied for "
                    f"{job.title}. "
                    f"Reference: "
                    f"{reference_no}"
                ),

                recipient="admin",

                is_read=False
            )

            db.session.add(
                notification
            )

            db.session.commit()

        except Exception:

            db.session.rollback()

            delete_uploaded_file(
                cv_filename
            )

            traceback.print_exc()

            flash(
                "Application could not be submitted. "
                "Please try again.",
                "danger"
            )

            return render_template(
                "apply.html",
                form=form,
                job=job
            )

        log_audit(
            "New Application",

            (
                f"{application.full_name} "
                f"applied for "
                f"{job.title}"
            ),

            "Application",

            application.id
        )

        flash(
            "Your application has been submitted successfully!",
            "success"
        )

        return redirect(
            url_for(
                "application_success",
                app_id=application.id
            )
        )

    return render_template(
        "apply.html",
        form=form,
        job=job
    )


# ============================================================
# APPLICATION SUCCESS
# ============================================================

@app.route(
    "/application/success/<int:app_id>"
)
def application_success(app_id):

    application = (
        Application.query
        .get_or_404(app_id)
    )

    return render_template(
        "success.html",
        application=application,
        job=application.job
    )


# ============================================================
# APPLICATION STATUS
# ============================================================

@app.route(
    "/application/status/<int:app_id>"
)
def application_status(app_id):

    application = (
        Application.query
        .get_or_404(app_id)
    )

    if not application.viewed_at:

        application.viewed_at = (
            datetime.utcnow()
        )

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

    return render_template(
        "application_status.html",
        application=application,
        job=application.job
    )


# ============================================================
# TALENT POOL
# ============================================================

@app.route(
    "/talent-pool",
    methods=["GET", "POST"]
)
def talent_pool():

    form = TalentPoolForm()

    if form.validate_on_submit():

        email = (
            form.email.data
            .strip()
            .lower()
        )

        existing = (
            TalentPool.query
            .filter(
                db.func.lower(
                    TalentPool.email
                ) == email
            )
            .first()
        )

        if existing:

            flash(
                "You have already joined the Rori Hotel Talent Pool with this email.",
                "warning"
            )

            return redirect(
                url_for("talent_pool")
            )

        cv_filename = save_uploaded_file(
            form.cv_file.data
        )

        if not cv_filename:

            flash(
                "Invalid CV. Please upload PDF, DOC, or DOCX.",
                "danger"
            )

            return render_template(
                "talent_pool.html",
                form=form
            )

        talent = TalentPool(

            full_name=(
                form.full_name.data
                .strip()
            ),

            email=email,

            phone=(
                form.phone.data
                .strip()
            ),

            location=(
                form.location.data
                .strip()
            ),

            education=form.education.data,

            years_of_experience=(
                form.years_of_experience.data
                .strip()
            ),

            skills=(
                form.skills.data
                .strip()
            ),

            languages=(
                form.languages.data
                .strip()
            ),

            certifications=(
                form.certifications.data
                .strip()
                if form.certifications.data
                else None
            ),

            availability_date=(
                form.availability_date.data
            ),

            willing_to_relocate=(
                form.willing_to_relocate.data
            ),

            expected_salary=(
                form.expected_salary.data
                .strip()
                if form.expected_salary.data
                else None
            ),

            cover_letter=(
                form.cover_letter.data
                .strip()
            ),

            cv_filename=cv_filename
        )

        try:

            db.session.add(
                talent
            )

            db.session.commit()

        except Exception:

            db.session.rollback()

            delete_uploaded_file(
                cv_filename
            )

            traceback.print_exc()

            flash(
                "Could not join the talent pool.",
                "danger"
            )

            return render_template(
                "talent_pool.html",
                form=form
            )

        flash(
            "You have successfully joined the Rori Hotel Talent Pool!",
            "success"
        )

        return redirect(
            url_for("home")
        )

    return render_template(
        "talent_pool.html",
        form=form
    )


# ============================================================
# ADMIN / HR LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
@app.route(
    "/hr/login",
    methods=["GET", "POST"]
)
@app.route(
    "/auth/login",
    methods=["GET", "POST"]
)
def admin_login():

    if session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for(
                "admin_dashboard"
            )
        )

    form = AdminLoginForm()

    if request.method == "POST":

        username = (
            request.form
            .get(
                "username",
                ""
            )
            .strip()
        )

        password = request.form.get(
            "password",
            ""
        )

        if not username:
            username = (
                form.username.data
                or ""
            ).strip()

        if not password:
            password = (
                form.password.data
                or ""
            )

        if not username or not password:

            flash(
                "እባክዎን Username እና Password ይሙሉ!",
                "warning"
            )

            return render_template(
                "login.html",
                form=form
            )

        try:

            admin_user = (
                AdminUser.query
                .filter_by(
                    username=username
                )
                .first()
            )

            if (
                admin_user
                and check_password_hash(
                    admin_user.password_hash,
                    password
                )
            ):

                session.clear()

                session[
                    "admin_logged_in"
                ] = True

                session[
                    "admin_username"
                ] = username

                session[
                    "admin_id"
                ] = admin_user.id

                log_audit(
                    "Login",
                    f"Admin {username} logged in."
                )

                flash(
                    "እንኳን በደህና መጡ!",
                    "success"
                )

                return redirect(
                    url_for(
                        "admin_dashboard"
                    )
                )

        except Exception:

            db.session.rollback()

            traceback.print_exc()

        default_username = (
            app.config.get(
                "HR_USERNAME",
                "admin"
            )
        )

        default_hash = (
            app.config.get(
                "HR_PASSWORD_HASH"
            )
        )

        if (
            username == default_username
            and default_hash
            and check_password_hash(
                default_hash,
                password
            )
        ):

            admin_id = None

            try:

                new_admin = AdminUser(
                    username=username,
                    password_hash=default_hash
                )

                db.session.add(
                    new_admin
                )

                db.session.commit()

                admin_id = new_admin.id

            except Exception:

                db.session.rollback()

                existing = (
                    AdminUser.query
                    .filter_by(
                        username=username
                    )
                    .first()
                )

                if existing:
                    admin_id = existing.id

            if admin_id is None:
                admin_id = 1

            session.clear()

            session[
                "admin_logged_in"
            ] = True

            session[
                "admin_username"
            ] = username

            session[
                "admin_id"
            ] = admin_id

            log_audit(
                "Login",
                (
                    f"Admin {username} "
                    f"logged in via fallback."
                )
            )

            flash(
                "እንኳን በደህና መጡ!",
                "success"
            )

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )

        flash(
            "የተሳሳተ Username ወይም Password!",
            "danger"
        )

    return render_template(
        "login.html",
        form=form
    )


# ============================================================
# CHANGE PASSWORD
# ============================================================

@app.route(
    "/admin/change-password",
    methods=["GET", "POST"]
)
@app.route(
    "/hr/change-password",
    methods=["GET", "POST"]
)
@admin_required
def admin_change_password():

    form = ChangePasswordForm()

    if form.validate_on_submit():

        username = session.get(
            "admin_username"
        )

        admin_user = (
            AdminUser.query
            .filter_by(
                username=username
            )
            .first()
        )

        if (
            admin_user
            and check_password_hash(
                admin_user.password_hash,
                form.current_password.data
            )
        ):

            admin_user.password_hash = (
                generate_password_hash(
                    form.new_password.data
                )
            )

            try:

                db.session.commit()

            except Exception:

                db.session.rollback()

                flash(
                    "Password update failed.",
                    "danger"
                )

                return render_template(
                    "admin/change_password.html",
                    form=form
                )

            log_audit(
                "Change Password",
                (
                    f"Admin {username} "
                    f"changed their password."
                )
            )

            flash(
                "የይለፍ ቃልዎ በስኬት ተቀይሯል!",
                "success"
            )

            return redirect(
                url_for(
                    "admin_dashboard"
                )
            )

        flash(
            "ያስተገቡት Current Password ትክክል አይደለም!",
            "danger"
        )

    return render_template(
        "admin/change_password.html",
        form=form
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/admin/logout")
@app.route("/hr/logout")
@app.route("/auth/logout")
def admin_logout():

    username = session.get(
        "admin_username",
        "Unknown"
    )

    if session.get(
        "admin_logged_in"
    ):

        log_audit(
            "Logout",
            f"Admin {username} logged out."
        )

    session.clear()

    flash(
        "በስኬት ወጥተዋል።",
        "info"
    )

    return redirect(
        url_for(
            "admin_login"
        )
    )


# ============================================================
# FORGOT PASSWORD
# ============================================================

@app.route(
    "/auth/forgot-password",
    methods=["GET", "POST"]
)
def forgot_password():

    if request.method == "POST":

        flash(
            "If an account exists with that email, "
            "we will send a reset link.",
            "info"
        )

        return redirect(
            url_for(
                "admin_login"
            )
        )

    return render_template(
        "forgot_password.html"
    )


# ============================================================
# HR DASHBOARD
# ============================================================

@app.route("/admin")
@app.route("/admin/dashboard")
@app.route("/hr")
@app.route("/hr/dashboard")
@admin_required
def admin_dashboard():

    total_jobs = Job.query.count()

    active_jobs = (
        Job.query
        .filter_by(
            is_active=True
        )
        .count()
    )

    total_applications = (
        Application.query.count()
    )

    total_interviews = (
        Interview.query.count()
    )

    recent_applications = (
        Application.query
        .order_by(
            Application.submitted_at.desc()
        )
        .limit(10)
        .all()
    )

    notifications = (
        Notification.query
        .order_by(
            Notification.created_at.desc()
        )
        .limit(10)
        .all()
    )

    statuses = [
        "NEW",
        "UNDER REVIEW",
        "SHORTLISTED",
        "INTERVIEW",
        "SELECTED",
        "HIRED",
        "REJECTED"
    ]

    status_counts = {}

    for status in statuses:

        status_counts[status] = (
            Application.query
            .filter_by(
                status=status
            )
            .count()
        )

    return safe_render(
        "admin/dashboard.html",

        total_jobs=total_jobs,

        active_jobs=active_jobs,

        total_applications=
            total_applications,

        total_interviews=
            total_interviews,

        recent_applications=
            recent_applications,

        notifications=
            notifications,

        status_counts=
            status_counts,

        applications=
            recent_applications
    )


# ============================================================
# CANDIDATES
# ============================================================

@app.route(
    "/admin/candidates"
)
@app.route(
    "/hr/candidates"
)
@admin_required
def admin_candidates():

    query = Application.query

    search = (
        request.args
        .get(
            "search",
            ""
        )
        .strip()
    )

    if search:

        search_value = (
            f"%{search}%"
        )

        query = query.filter(
            db.or_(
                Application.full_name
                .ilike(search_value),

                Application.email
                .ilike(search_value),

                Application.reference_no
                .ilike(search_value)
            )
        )

    status_filter = (
        request.args
        .get(
            "status",
            ""
        )
        .strip()
    )

    if (
        status_filter
        and status_filter != "ALL"
    ):

        query = query.filter(
            Application.status
            == status_filter
        )

    applications = (
        query
        .order_by(
            Application.submitted_at.desc()
        )
        .all()
    )

    return safe_render(
        "admin/candidates.html",
        applications=applications,
        departments=Department.query.all()
    )


# ============================================================
# CANDIDATE DETAIL
# ============================================================

@app.route(
    "/admin/candidate/<int:app_id>"
)
@app.route(
    "/hr/candidate/<int:app_id>"
)
@admin_required
def admin_candidate_detail(app_id):

    application = (
        Application.query
        .get_or_404(app_id)
    )

    interviews = (
        Interview.query
        .filter_by(
            application_id=app_id
        )
        .order_by(
            Interview.scheduled_at.desc()
        )
        .all()
    )

    if not application.viewed_at:

        application.viewed_at = (
            datetime.utcnow()
        )

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

    return safe_render(
        "admin/candidate_detail.html",
        application=application,
        interviews=interviews
    )


# ============================================================
# CV DOWNLOAD
# ============================================================

@app.route(
    "/admin/candidate/<int:app_id>/cv/download"
)
@app.route(
    "/hr/candidate/<int:app_id>/cv/download"
)
@admin_required
def download_candidate_cv(app_id):

    application = (
        Application.query
        .get_or_404(app_id)
    )

    filename = application.cv_filename

    if not filename:

        flash(
            "CV ለዚህ አመልካች አልተገኘም።",
            "warning"
        )

        return redirect(
            request.referrer
            or url_for(
                "admin_candidates"
            )
        )

    if is_cloudinary_cv(
        filename
    ):

        download_url = (
            generate_cloudinary_cv_url(
                filename
            )
        )

        if download_url:

            log_audit(
                "CV Download",
                (
                    f"HR downloaded CV for "
                    f"{application.full_name}"
                ),
                "Application",
                application.id
            )

            return redirect(
                download_url
            )

        flash(
            "Cloudinary CV ማግኘት አልተቻለም።",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "admin_candidates"
            )
        )

    safe_filename = secure_filename(
        os.path.basename(filename)
    )

    if not safe_filename:

        flash(
            "የCV ፋይል ስም ትክክል አይደለም።",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "admin_candidates"
            )
        )

    upload_directories = [

        app.config.get(
            "UPLOAD_FOLDER"
        ),

        os.path.join(
            BASE_DIR,
            "uploads",
            "resumes"
        ),

        os.path.join(
            BASE_DIR,
            "uploads"
        ),

        os.path.join(
            app.root_path,
            "static",
            "uploads",
            "resumes"
        ),

        os.path.join(
            app.root_path,
            "static",
            "uploads"
        )
    ]

    upload_directories = list(
        dict.fromkeys(
            directory
            for directory
            in upload_directories
            if directory
        )
    )

    for directory in upload_directories:

        file_path = os.path.join(
            directory,
            safe_filename
        )

        if os.path.isfile(
            file_path
        ):

            log_audit(
                "CV Download",
                (
                    f"HR downloaded local CV "
                    f"for {application.full_name}"
                ),
                "Application",
                application.id
            )

            return send_from_directory(
                directory,
                safe_filename,
                as_attachment=False
            )

    flash(
        "የCV ፋይሉ በserver ላይ አልተገኘም።",
        "danger"
    )

    return redirect(
        request.referrer
        or url_for(
            "admin_candidates"
        )
    )


# ============================================================
# UPDATE APPLICATION STATUS
# ============================================================

@app.route(
    "/admin/application/<int:app_id>/status",
    methods=["POST"]
)
@app.route(
    "/hr/application/<int:app_id>/status",
    methods=["POST"]
)
@app.route(
    "/admin/application/<int:app_id>/action",
    methods=["POST"]
)
@app.route(
    "/hr/application/<int:app_id>/action",
    methods=["POST"]
)
@admin_required
def update_application_status(app_id):

    application = (
        Application.query
        .get_or_404(app_id)
    )

    new_status = (
        request.form
        .get(
            "status",
            ""
        )
        .strip()
        .upper()
    )

    if not new_status:

        new_status = (
            request.form
            .get(
                "action",
                ""
            )
            .strip()
            .upper()
        )

    notes = (
        request.form
        .get(
            "notes",
            ""
        )
        .strip()
    )

    allowed_statuses = {
        "NEW",
        "UNDER REVIEW",
        "SHORTLISTED",
        "INTERVIEW",
        "SELECTED",
        "HIRED",
        "REJECTED"
    }

    if new_status not in allowed_statuses:

        flash(
            "Invalid application status.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "admin_dashboard"
            )
        )

    old_status = application.status

    application.status = new_status

    application.status_updated_at = (
        datetime.utcnow()
    )

    application.reviewed_by = (
        session.get(
            "admin_username"
        )
    )

    if new_status == "SHORTLISTED":

        application.shortlisted_at = (
            datetime.utcnow()
        )

    if new_status == "REJECTED":

        application.rejected_at = (
            datetime.utcnow()
        )

    if notes:

        application.notes = notes

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        traceback.print_exc()

        flash(
            "Status ማዘመን አልተቻለም።",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "admin_dashboard"
            )
        )

    try:

        position = (
            application.job.title
            if application.job
            else "Rori Hotel Position"
        )

        status_notification = Notification(

            title=(
                "Application Status Updated"
            ),

            message=(
                f"Your application for "
                f"{position} is now "
                f"{new_status}. "
                f"Reference: "
                f"{application.reference_no}"
            ),

            recipient=application.email,

            is_read=False
        )

        db.session.add(
            status_notification
        )

        db.session.commit()

    except Exception:

        db.session.rollback()

    log_audit(
        "Status Update",

        (
            f"Changed "
            f"{application.full_name} "
            f"from {old_status} "
            f"to {new_status}"
        ),

        "Application",

        application.id
    )

    send_application_status_email(
        application,
        old_status,
        new_status,
        notes
    )

    flash(
        (
            f'የአመልካቹ Status ወደ '
            f'"{new_status}" ተቀይሯል!'
        ),
        "success"
    )

    return redirect(
        request.referrer
        or url_for(
            "admin_dashboard"
        )
    )


# ============================================================
# JOB MANAGEMENT
# ============================================================

@app.route(
    "/admin/jobs"
)
@app.route(
    "/hr/jobs"
)
@admin_required
def admin_jobs():

    jobs_list = (
        Job.query
        .order_by(
            Job.created_at.desc()
        )
        .all()
    )

    return safe_render(
        "admin/jobs.html",
        jobs=jobs_list
    )


# ============================================================
# JOB FORM CHOICES
# ============================================================

def configure_job_form_choices(form):

    departments_list = (
        Department.query
        .order_by(
            Department.name
        )
        .all()
    )

    locations_list = (
        Location.query
        .order_by(
            Location.name
        )
        .all()
    )

    form.department_id.choices = (
        [(0, "None")]
        + [
            (
                department.id,
                department.name
            )
            for department
            in departments_list
        ]
    )

    form.location_id.choices = (
        [(0, "None")]
        + [
            (
                location.id,
                location.name
            )
            for location
            in locations_list
        ]
    )


# ============================================================
# CREATE JOB
# ============================================================

@app.route(
    "/admin/job/new",
    methods=["GET", "POST"]
)
@app.route(
    "/hr/job/new",
    methods=["GET", "POST"]
)
@admin_required
def admin_job_new():

    form = JobForm()

    configure_job_form_choices(
        form
    )

    if request.method == "POST":

        banner_image = None

        if form.validate_on_submit():

            banner_image = save_job_image(
                request.files.get(
                    "banner_image"
                )
            )

            dept_id = (
                form.department_id.data
            )

            loc_id = (
                form.location_id.data
            )

            job = Job(

                title=(
                    form.title.data
                    .strip()
                ),

                department_id=(
                    dept_id
                    if dept_id
                    and dept_id != 0
                    else None
                ),

                location_id=(
                    loc_id
                    if loc_id
                    and loc_id != 0
                    else None
                ),

                short_description=(
                    form.short_description.data
                    .strip()
                ),

                full_description=(
                    form.full_description.data
                    .strip()
                ),

                responsibilities=(
                    form.responsibilities.data
                    .strip()
                ),

                requirements=(
                    form.requirements.data
                    .strip()
                ),

                what_we_offer=(
                    form.what_we_offer.data
                    .strip()
                ),

                employment_type=(
                    form.employment_type.data
                ),

                experience_level=(
                    form.experience_level.data
                    .strip()
                    if form.experience_level.data
                    else None
                ),

                salary_range=(
                    form.salary_range.data
                    .strip()
                    if form.salary_range.data
                    else None
                ),

                deadline=(
                    form.deadline.data
                ),

                is_active=(
                    bool(
                        form.is_active.data
                    )
                ),

                is_featured=(
                    bool(
                        form.is_featured.data
                    )
                ),

                banner_image=banner_image
            )

            try:

                db.session.add(
                    job
                )

                db.session.commit()

                log_audit(
                    "Created Job",
                    (
                        f"Created job: "
                        f"{job.title}"
                    ),
                    "Job",
                    job.id
                )

                flash(
                    "የስራ ማስታወቂያው በስኬት ተለጥፏል!",
                    "success"
                )

                return redirect(
                    url_for(
                        "admin_jobs"
                    )
                )

            except Exception:

                db.session.rollback()

                if banner_image:
                    delete_job_image(
                        banner_image
                    )

                traceback.print_exc()

                flash(
                    "የስራ ማስታወቂያውን መፍጠር አልተቻለም።",
                    "danger"
                )

        else:

            flash(
                "እባክዎን የተጠየቁትን የስራ መረጃዎች በትክክል ይሙሉ።",
                "warning"
            )

    return safe_render(
        "admin/job_form.html",
        form=form,
        is_new=True
    )


# ============================================================
# EDIT JOB
# ============================================================

@app.route(
    "/admin/job/<int:job_id>/edit",
    methods=["GET", "POST"]
)
@app.route(
    "/hr/job/<int:job_id>/edit",
    methods=["GET", "POST"]
)
@admin_required
def admin_job_edit(job_id):

    job = Job.query.get_or_404(
        job_id
    )

    form = JobForm()

    configure_job_form_choices(
        form
    )

    if request.method == "GET":

        form.title.data = job.title

        form.department_id.data = (
            job.department_id or 0
        )

        form.location_id.data = (
            job.location_id or 0
        )

        form.short_description.data = (
            job.short_description
        )

        form.full_description.data = (
            job.full_description
        )

        form.responsibilities.data = (
            job.responsibilities
        )

        form.requirements.data = (
            job.requirements
        )

        form.what_we_offer.data = (
            job.what_we_offer
        )

        form.employment_type.data = (
            job.employment_type
        )

        form.experience_level.data = (
            job.experience_level
        )

        form.salary_range.data = (
            job.salary_range
        )

        form.deadline.data = (
            job.deadline
        )

        form.is_active.data = (
            job.is_active
        )

        form.is_featured.data = (
            job.is_featured
        )

    if request.method == "POST":

        if form.validate_on_submit():

            old_banner = (
                job.banner_image
            )

            new_banner = save_job_image(
                request.files.get(
                    "banner_image"
                )
            )

            job.title = (
                form.title.data.strip()
            )

            job.department_id = (
                form.department_id.data
                if form.department_id.data
                and form.department_id.data != 0
                else None
            )

            job.location_id = (
                form.location_id.data
                if form.location_id.data
                and form.location_id.data != 0
                else None
            )

            job.short_description = (
                form.short_description.data
                .strip()
            )

            job.full_description = (
                form.full_description.data
                .strip()
            )

            job.responsibilities = (
                form.responsibilities.data
                .strip()
            )

            job.requirements = (
                form.requirements.data
                .strip()
            )

            job.what_we_offer = (
                form.what_we_offer.data
                .strip()
            )

            job.employment_type = (
                form.employment_type.data
            )

            job.experience_level = (
                form.experience_level.data
                .strip()
                if form.experience_level.data
                else None
            )

            job.salary_range = (
                form.salary_range.data
                .strip()
                if form.salary_range.data
                else None
            )

            job.deadline = (
                form.deadline.data
            )

            job.is_active = (
                bool(
                    form.is_active.data
                )
            )

            job.is_featured = (
                bool(
                    form.is_featured.data
                )
            )

            if new_banner:
                job.banner_image = new_banner

            try:

                db.session.commit()

                if (
                    new_banner
                    and old_banner
                    and old_banner != new_banner
                ):
                    delete_job_image(
                        old_banner
                    )

                log_audit(
                    "Updated Job",
                    (
                        f"Updated job: "
                        f"{job.title}"
                    ),
                    "Job",
                    job.id
                )

                flash(
                    "የስራ ማስታወቂያው ተስተካክሏል!",
                    "success"
                )

                return redirect(
                    url_for(
                        "admin_jobs"
                    )
                )

            except Exception:

                db.session.rollback()

                if new_banner:
                    delete_job_image(
                        new_banner
                    )

                traceback.print_exc()

                flash(
                    "የስራ ማስታወቂያውን ማስተካከል አልተቻለም።",
                    "danger"
                )

    return safe_render(
        "admin/job_form.html",
        form=form,
        is_new=False,
        job=job
    )


# ============================================================
# TOGGLE JOB
# ============================================================

@app.route(
    "/admin/job/<int:job_id>/toggle",
    methods=["GET", "POST"]
)
@app.route(
    "/hr/job/<int:job_id>/toggle",
    methods=["GET", "POST"]
)
@admin_required
def admin_job_toggle(job_id):

    job = Job.query.get_or_404(
        job_id
    )

    job.is_active = not job.is_active

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        traceback.print_exc()

        flash(
            "Could not update job.",
            "danger"
        )

        return redirect(
            url_for("admin_jobs")
        )

    log_audit(
        "Toggled Job",

        (
            f"{job.title} active status "
            f"changed to {job.is_active}"
        ),

        "Job",

        job.id
    )

    flash(
        (
            "Job activated."
            if job.is_active
            else "Job deactivated."
        ),
        "success"
    )

    return redirect(
        url_for("admin_jobs")
    )


# ============================================================
# DELETE JOB
# ============================================================

@app.route(
    "/admin/job/<int:job_id>/delete",
    methods=["POST", "GET"]
)
@app.route(
    "/hr/job/<int:job_id>/delete",
    methods=["POST", "GET"]
)
@admin_required
def admin_job_delete(job_id):

    job = Job.query.get_or_404(
        job_id
    )

    application_count = (
        Application.query
        .filter_by(
            job_id=job.id
        )
        .count()
    )

    if application_count > 0:

        flash(
            (
                "ይህ vacancy የተመዘገቡ "
                f"{application_count} application(s) አሉት። "
                "ስለዚህ መሰረዝ አይቻልም። "
                "Toggle በማድረግ ዝጋው።"
            ),
            "warning"
        )

        return redirect(
            url_for(
                "admin_jobs"
            )
        )

    try:

        old_banner = (
            job.banner_image
        )

        db.session.delete(
            job
        )

        db.session.commit()

        if old_banner:
            delete_job_image(
                old_banner
            )

        log_audit(
            "Deleted Job",

            (
                f"Deleted job: "
                f"{job.title}"
            ),

            "Job",

            job_id
        )

        flash(
            "የስራ ማስታወቂያው በስኬት ተሰርዟል!",
            "success"
        )

    except Exception:

        db.session.rollback()

        traceback.print_exc()

        flash(
            "ማስታወቂያውን ለማጥፋት ችግር አጋጥሟል!",
            "danger"
        )

    return redirect(
        url_for(
            "admin_jobs"
        )
    )


# ============================================================
# INTERVIEWS  (LIST)
# ============================================================

@app.route("/admin/interviews")
@app.route("/hr/interviews")
@admin_required
def admin_interviews():

    interviews = (
        Interview.query
        .order_by(Interview.scheduled_at.desc())
        .all()
    )

    return safe_render(
        "admin/interviews.html",
        interviews=interviews
    )


# ============================================================
# NEW INTERVIEW
# ============================================================

@app.route("/admin/interview/new", methods=["GET", "POST"])
@app.route("/admin/interviews/new", methods=["GET", "POST"])
@app.route("/hr/interview/new", methods=["GET", "POST"])
@app.route("/hr/interviews/new", methods=["GET", "POST"])
@admin_required
def admin_interview_new():

    applications = (
        Application.query
        .order_by(Application.id.desc())
        .all()
    )

    if request.method == "POST":

        application_id = request.form.get("application_id")
        scheduled_at_raw = request.form.get("scheduled_at")

        if not application_id or not scheduled_at_raw:

            flash(
                "Please select a candidate and interview date.",
                "danger"
            )

            return safe_render(
                "admin/interview_form.html",
                applications=applications,
                interview=None,
                selected_app_id=None
            )

        try:

            scheduled_at = datetime.strptime(
                scheduled_at_raw,
                "%Y-%m-%dT%H:%M"
            )

        except ValueError:

            flash(
                "Invalid date format. Use the date/time picker.",
                "danger"
            )

            return safe_render(
                "admin/interview_form.html",
                applications=applications,
                interview=None,
                selected_app_id=int(application_id)
            )

        try:

            duration = request.form.get("duration_minutes")

            interview_type = (
                request.form.get("interview_type")
                or "In-person"
            )

            interview = Interview(
                application_id=int(application_id),
                scheduled_at=scheduled_at,
                duration_minutes=(
                    int(duration) if duration else 30
                ),
                interview_type=interview_type,
                interviewer_name=request.form.get(
                    "interviewer_name"
                ) or None,
                location=request.form.get(
                    "location"
                ) or None,
                notes=request.form.get(
                    "notes"
                ) or None,
                status="Scheduled"
            )

            db.session.add(interview)
            db.session.flush()

            application = Application.query.get(
                int(application_id)
            )

            db.session.commit()

            apply_interview_side_effects(
                application,
                interview,
                event="scheduled",
                extra_note=interview.notes
            )

            log_audit(
                "Interview Scheduled",
                (
                    f"Scheduled interview for "
                    f"{application.full_name if application else application_id} "
                    f"on {scheduled_at}"
                ),
                "Interview",
                interview.id
            )

            flash(
                "Interview scheduled successfully.",
                "success"
            )

            return redirect(url_for("admin_interviews"))

        except Exception:

            db.session.rollback()

            app.logger.exception(
                "Error creating interview"
            )

            flash(
                "Could not schedule interview.",
                "danger"
            )

    return safe_render(
        "admin/interview_form.html",
        applications=applications,
        interview=None,
        selected_app_id=None
    )


# ============================================================
# EDIT INTERVIEW
# ============================================================

@app.route(
    "/admin/interview/<int:interview_id>/edit",
    methods=["GET", "POST"]
)
@app.route(
    "/admin/interviews/<int:interview_id>/edit",
    methods=["GET", "POST"]
)
@app.route(
    "/hr/interview/<int:interview_id>/edit",
    methods=["GET", "POST"]
)
@admin_required
def admin_interview_edit(interview_id):

    interview = Interview.query.get_or_404(interview_id)

    applications = (
        Application.query
        .order_by(Application.id.desc())
        .all()
    )

    if request.method == "POST":

        try:

            scheduled_at_raw = request.form.get("scheduled_at")

            if not scheduled_at_raw:

                flash(
                    "Interview date and time are required.",
                    "danger"
                )

                return redirect(
                    url_for(
                        "admin_interview_edit",
                        interview_id=interview.id
                    )
                )

            old_status = interview.status
            old_when = interview.scheduled_at

            interview.scheduled_at = datetime.strptime(
                scheduled_at_raw,
                "%Y-%m-%dT%H:%M"
            )

            duration = request.form.get("duration_minutes")

            if duration:
                interview.duration_minutes = int(duration)

            interview.interview_type = (
                request.form.get("interview_type")
                or interview.interview_type
            )

            interview.interviewer_name = (
                request.form.get("interviewer_name")
                or None
            )

            interview.location = (
                request.form.get("location")
                or None
            )

            interview.notes = (
                request.form.get("notes")
                or None
            )

            new_status = request.form.get("status")

            if new_status:
                interview.status = new_status

            db.session.commit()

            event = None

            if (
                new_status
                and new_status.lower() == "cancelled"
                and old_status != "Cancelled"
            ):
                event = "cancelled"

            elif (
                new_status
                and new_status.lower() == "completed"
                and old_status != "Completed"
            ):
                event = "completed"

            elif (
                interview.scheduled_at != old_when
                or (
                    new_status
                    and new_status.lower() == "rescheduled"
                )
            ):
                event = "rescheduled"

            if event:

                application = (
                    interview.application
                    or Application.query.get(
                        interview.application_id
                    )
                )

                apply_interview_side_effects(
                    application,
                    interview,
                    event=event,
                    extra_note=interview.notes
                )

            log_audit(
                "Interview Updated",
                (
                    f"Updated interview #{interview.id} "
                    f"for application #{interview.application_id}"
                ),
                "Interview",
                interview.id
            )

            flash(
                "Interview updated successfully.",
                "success"
            )

            return redirect(
                url_for("admin_interviews")
            )

        except Exception:

            db.session.rollback()

            app.logger.exception(
                "Error updating interview"
            )

            flash(
                "Could not update interview.",
                "danger"
            )

    return safe_render(
        "admin/interview_form.html",
        applications=applications,
        interview=interview,
        selected_app_id=interview.application_id
    )


# ============================================================
# INTERVIEW STATUS (quick update)
# ============================================================

@app.route(
    "/admin/interview/<int:interview_id>/status",
    methods=["POST"]
)
@app.route(
    "/hr/interview/<int:interview_id>/status",
    methods=["POST"]
)
@admin_required
def admin_interview_status(interview_id):

    interview = Interview.query.get_or_404(interview_id)

    new_status = (
        request.form.get("status", "")
        .strip()
    )

    allowed = {
        "Scheduled",
        "Completed",
        "Cancelled",
        "Rescheduled"
    }

    if new_status not in allowed:

        flash(
            "Invalid interview status.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for("admin_interviews")
        )

    old_status = interview.status
    interview.status = new_status

    evaluation = request.form.get("evaluation")
    rating = request.form.get("rating")
    decision = request.form.get("decision")

    if evaluation is not None:
        interview.evaluation = evaluation or None

    if rating:
        try:
            interview.rating = int(rating)
        except ValueError:
            pass

    if decision is not None:
        interview.decision = decision or None

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        traceback.print_exc()

        flash(
            "Could not update interview status.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for("admin_interviews")
        )

    event = None

    if new_status == "Cancelled" and old_status != "Cancelled":
        event = "cancelled"
    elif new_status == "Rescheduled" and old_status != "Rescheduled":
        event = "rescheduled"
    elif new_status == "Completed" and old_status != "Completed":
        event = "completed"

    if event:

        application = (
            interview.application
            or Application.query.get(
                interview.application_id
            )
        )

        apply_interview_side_effects(
            application,
            interview,
            event=event,
            extra_note=interview.notes
        )

    log_audit(
        "Interview Status",
        (
            f"Interview #{interview.id} status "
            f"changed from {old_status} to {new_status}"
        ),
        "Interview",
        interview.id
    )

    flash(
        "Interview status updated.",
        "success"
    )

    return redirect(
        request.referrer
        or url_for("admin_interviews")
    )


# ============================================================
# TALENT POOL ADMIN
# ============================================================

@app.route(
    "/admin/talent-pool"
)
@app.route(
    "/hr/talent-pool"
)
@admin_required
def admin_talent_pool():

    candidates = (
        TalentPool.query
        .order_by(
            TalentPool.submitted_at.desc()
        )
        .all()
    )

    return safe_render(
        "admin/talent_pool.html",
        candidates=candidates
    )


# ============================================================
# AUDIT LOG
# ============================================================

@app.route(
    "/admin/audit-log"
)
@app.route(
    "/hr/audit-log"
)
@admin_required
def admin_audit_log():

    logs = (
        AuditLog.query
        .order_by(
            AuditLog.created_at.desc()
        )
        .limit(200)
        .all()
    )

    return safe_render(
        "admin/audit_log.html",
        logs=logs
    )


# ============================================================
# DATABASE MIGRATION
# ============================================================

def safe_add_column(
    table_name,
    column_name,
    column_type
):

    try:

        inspector = inspect(
            db.engine
        )

        if (
            table_name
            not in inspector.get_table_names()
        ):
            return

        columns = {
            column["name"]
            for column
            in inspector.get_columns(
                table_name
            )
        }

        if column_name in columns:
            return

        type_str = str(
            column_type
        ).upper()

        default_clause = ""

        if (
            "DATETIME"
            in type_str
            or "TIMESTAMP"
            in type_str
        ):

            default_clause = (
                " DEFAULT CURRENT_TIMESTAMP"
            )

        elif "BOOLEAN" in type_str:

            default_clause = (
                " DEFAULT FALSE"
            )

        elif "INTEGER" in type_str:

            default_clause = (
                " DEFAULT 0"
            )

        elif (
            "VARCHAR"
            in type_str
            or "TEXT"
            in type_str
        ):

            default_clause = (
                " DEFAULT ''"
            )

        with db.engine.begin() as connection:

            connection.execute(
                text(
                    f'ALTER TABLE "{table_name}" '
                    f'ADD COLUMN "{column_name}" '
                    f'{column_type}'
                    f'{default_clause}'
                )
            )

        print(
            "[DB AUTO-MIGRATION] "
            f"Added missing column: "
            f"{table_name}.{column_name}"
        )

    except Exception as e:

        print(
            "[DB WARNING] Could not add "
            f"column {table_name}."
            f"{column_name}: {e}"
        )


def migrate_existing_database():

    inspector = inspect(
        db.engine
    )

    existing_tables = set(
        inspector.get_table_names()
    )

    db.create_all()

    models = [
        AdminUser,
        Department,
        Location,
        Job,
        Application,
        TalentPool,
        Interview,
        Notification,
        AuditLog
    ]

    for model in models:

        table_name = (
            model.__tablename__
        )

        if (
            table_name
            not in existing_tables
        ):
            continue

        existing_columns = {
            column["name"]
            for column
            in inspector.get_columns(
                table_name
            )
        }

        for column in model.__table__.columns:

            if column.name in existing_columns:
                continue

            if column.primary_key:
                continue

            try:

                dialect = db.engine.dialect

                column_type = (
                    column.type.compile(
                        dialect=dialect
                    )
                )

            except Exception:

                column_type = "TEXT"

            safe_add_column(
                table_name,
                column.name,
                column_type
            )


# ============================================================
# SEED DEFAULT DATA
# ============================================================

def seed_default_data():

    admin = (
        AdminUser.query
        .filter_by(
            username=app.config[
                "HR_USERNAME"
            ]
        )
        .first()
    )

    if not admin:

        db.session.add(
            AdminUser(

                username=app.config[
                    "HR_USERNAME"
                ],

                password_hash=app.config[
                    "HR_PASSWORD_HASH"
                ]
            )
        )

    departments = [

        "Front Office",

        "Housekeeping",

        "Food & Beverage",

        "Kitchen",

        "Engineering",

        "Finance",

        "Human Resources",

        "IT",

        "Security",

        "Spa & Wellness",

        "Sales & Marketing"
    ]

    for name in departments:

        existing = (
            Department.query
            .filter_by(
                name=name
            )
            .first()
        )

        if not existing:

            db.session.add(
                Department(
                    name=name
                )
            )

    location = (
        Location.query
        .filter_by(
            name="Hawassa"
        )
        .first()
    )

    if not location:

        db.session.add(
            Location(

                name="Hawassa",

                address=(
                    "Hawassa, "
                    "Sidama Region, "
                    "Ethiopia"
                )
            )
        )

    db.session.commit()


def init_db_safe():

    with app.app_context():

        try:

            db.create_all()

            migrate_existing_database()

            seed_default_data()

            print(
                "======================================"
            )

            print(
                "DATABASE INITIALIZATION SUCCESS"
            )

            print(
                "======================================"
            )

        except Exception:

            db.session.rollback()

            print(
                "======================================"
            )

            print(
                "DATABASE INITIALIZATION ERROR"
            )

            print(
                "======================================"
            )

            traceback.print_exc()


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template(
        "404.html"
    ), 404


@app.errorhandler(413)
def file_too_large(error):

    flash(
        "File is too large. Maximum size is 10 MB.",
        "danger"
    )

    return redirect(
        request.referrer
        or url_for("home")
    )


@app.errorhandler(500)
def internal_server_error(error):

    try:

        db.session.rollback()

    except Exception:

        pass

    print(
        "======================================"
    )

    print(
        "INTERNAL SERVER ERROR"
    )

    traceback.print_exc()

    print(
        "======================================"
    )

    return render_template(
        "500.html"
    ), 500


# ============================================================
# STARTUP
# ============================================================

try:

    init_db_safe()

except Exception:

    traceback.print_exc()


# ============================================================
# DEVELOPMENT
# ============================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),

        debug=True
    ) 