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

BASE_DIR = os.path.abspath(
    os.path.dirname(__file__)
)


class Config:

    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "change-this-secret-key-in-production-rori-2026"
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    DATABASE_URL = os.environ.get(
        "DATABASE_URL"
    )

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

    # --------------------------------------------------------
    # FILES
    # --------------------------------------------------------

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

    MAX_CONTENT_LENGTH = (
        10 * 1024 * 1024
    )

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

    # --------------------------------------------------------
    # CLOUDINARY
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # HR LOGIN
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MAIL
    # --------------------------------------------------------

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
# APPLICATION
# ============================================================

app = Flask(__name__)

app.config.from_object(
    Config
)

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
        cloud_name=app.config[
            "CLOUDINARY_CLOUD_NAME"
        ],
        api_key=app.config[
            "CLOUDINARY_API_KEY"
        ],
        api_secret=app.config[
            "CLOUDINARY_API_SECRET"
        ],
        secure=True
    )

    print(
        "[CLOUDINARY] Configuration loaded successfully."
    )

else:

    print(
        "[CLOUDINARY] WARNING: "
        "Cloudinary is NOT fully configured."
    )


# ============================================================
# TEMPLATE LOADER
# ============================================================

template_dirs = [

    os.path.join(
        app.root_path,
        "templates"
    ),

    os.path.join(
        app.root_path,
        "templates",
        "careers"
    ),

    os.path.join(
        app.root_path,
        "templates",
        "application"
    ),

    os.path.join(
        app.root_path,
        "templates",
        "auth"
    ),

    os.path.join(
        app.root_path,
        "templates",
        "admin"
    ),

    os.path.join(
        app.root_path,
        "templates",
        "hr"
    )
]

app.jinja_loader = jinja2.FileSystemLoader(
    template_dirs
)


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
    os.path.join(
        BASE_DIR,
        "instance"
    ),
    exist_ok=True
)


# ============================================================
# TEMPLATE HELPERS
# ============================================================

def template_exists(template_name):

    try:

        app.jinja_loader.get_source(
            app.jinja_env,
            template_name
        )

        return True

    except Exception:

        return False


def render_hr_template(
    hr_template,
    admin_template,
    **context
):

    """
    HR template first.

    If templates/hr/<template> exists,
    use it.

    Otherwise use existing admin template.

    This prevents conflicts between:
        templates/hr
        templates/admin
        app.py
    """

    if template_exists(hr_template):

        return render_template(
            hr_template,
            **context
        )

    return render_template(
        admin_template,
        **context
    )


def render_login_template(
    **context
):

    if template_exists(
        "hr/login.html"
    ):

        return render_template(
            "hr/login.html",
            **context
        )

    if template_exists(
        "auth/login.html"
    ):

        return render_template(
            "auth/login.html",
            **context
        )

    return render_template(
        "login.html",
        **context
    )


def published_jobs_query():

    return Job.query.filter(
        Job.is_active.is_(True),
        Job.status == "PUBLISHED"
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

        return (
            f"<AdminUser {self.username}>"
        )


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

        return (
            f"<Department {self.name}>"
        )


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

        return (
            f"<Location {self.name}>"
        )


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
        db.ForeignKey(
            "departments.id"
        ),
        nullable=True
    )

    location_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "locations.id"
        ),
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

    # IMPORTANT:
    # DRAFT / PUBLISHED / CLOSED

    status = db.Column(
        db.String(20),
        nullable=False,
        default="PUBLISHED"
    )

    published_at = db.Column(
        db.DateTime,
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

    @property
    def is_published(self):

        return (
            self.status == "PUBLISHED"
            and self.is_active
        )

    def __repr__(self):

        return (
            f"<Job {self.title}>"
        )


class Application(db.Model):

    __tablename__ = "applications"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    job_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "jobs.id"
        ),
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

        return (
            f"<Application {self.full_name}>"
        )


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

    # IMPORTANT:
    # Existing Render DB expects this column.

    preferred_department = db.Column(
        db.String(120),
        nullable=False,
        default=""
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
        db.ForeignKey(
            "applications.id"
        ),
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
            (
                "High School",
                "High School Diploma"
            ),
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
        validators=[
            DataRequired()
        ]
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
        validators=[
            Optional()
        ],
        format="%Y-%m-%d"
    )

    willing_to_relocate = SelectField(
        "Willing to Relocate?",
        choices=[
            ("Yes", "Yes"),
            ("No", "No")
        ],
        validators=[
            DataRequired()
        ]
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
        validators=[
            DataRequired()
        ]
    )


class TalentPoolForm(ApplicationForm):

    preferred_department = SelectField(
        "Preferred Department",
        choices=[
            (
                "",
                "Any Department"
            ),
            (
                "Front Office",
                "Front Office"
            ),
            (
                "Housekeeping",
                "Housekeeping"
            ),
            (
                "Food & Beverage",
                "Food & Beverage"
            ),
            (
                "Kitchen",
                "Kitchen"
            ),
            (
                "Engineering",
                "Engineering"
            ),
            (
                "Finance",
                "Finance"
            ),
            (
                "Human Resources",
                "Human Resources"
            ),
            (
                "IT",
                "IT"
            ),
            (
                "Security",
                "Security"
            ),
            (
                "Spa & Wellness",
                "Spa & Wellness"
            ),
            (
                "Sales & Marketing",
                "Sales & Marketing"
            )
        ],
        validators=[
            Optional()
        ]
    )


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
        validators=[
            Optional()
        ]
    )

    location_id = SelectField(
        "Location",
        coerce=int,
        validators=[
            Optional()
        ]
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
        validators=[
            DataRequired()
        ]
    )

    responsibilities = TextAreaField(
        "Responsibilities",
        validators=[
            DataRequired()
        ]
    )

    requirements = TextAreaField(
        "Requirements",
        validators=[
            DataRequired()
        ]
    )

    what_we_offer = TextAreaField(
        "What We Offer",
        validators=[
            DataRequired()
        ]
    )

    employment_type = SelectField(
        "Employment Type",
        choices=[
            (
                "Full-time",
                "Full-time"
            ),
            (
                "Part-time",
                "Part-time"
            ),
            (
                "Contract",
                "Contract"
            )
        ],
        validators=[
            DataRequired()
        ]
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
        validators=[
            Optional()
        ],
        format="%Y-%m-%d"
    )

    status = SelectField(
        "Vacancy Status",
        choices=[
            (
                "DRAFT",
                "Draft"
            ),
            (
                "PUBLISHED",
                "Published"
            ),
            (
                "CLOSED",
                "Closed"
            )
        ],
        validators=[
            Optional()
        ],
        default="PUBLISHED"
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
        validators=[
            DataRequired()
        ]
    )

    password = PasswordField(
        "Password",
        validators=[
            DataRequired()
        ]
    )


class ChangePasswordForm(FlaskForm):

    current_password = PasswordField(
        "Current Password",
        validators=[
            DataRequired()
        ]
    )

    new_password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(
                min=6,
                message=(
                    "Password must be at least 6 characters"
                )
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
        validators=[
            DataRequired()
        ]
    )

    scheduled_at = StringField(
        "Scheduled Date/Time",
        validators=[
            DataRequired()
        ]
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
            (
                "In-person",
                "In-person"
            ),
            (
                "Virtual",
                "Virtual"
            ),
            (
                "Phone",
                "Phone"
            )
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
        validators=[
            Optional()
        ]
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
        in app.config[
            "ALLOWED_EXTENSIONS"
        ]
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
        in app.config[
            "ALLOWED_IMAGE_EXTENSIONS"
        ]
    )


# ============================================================
# CLOUDINARY HELPERS
# ============================================================

def cloudinary_ready():

    return bool(
        CLOUDINARY_AVAILABLE
        and app.config.get(
            "CLOUDINARY_CLOUD_NAME"
        )
        and app.config.get(
            "CLOUDINARY_API_KEY"
        )
        and app.config.get(
            "CLOUDINARY_API_SECRET"
        )
    )


def is_cloudinary_cv(filename):

    return bool(
        filename
        and filename.startswith(
            "cloudinary:"
        )
    )


def parse_cloudinary_cv(filename):

    if not is_cloudinary_cv(
        filename
    ):

        return None, None

    value = filename[
        len("cloudinary:")
    :]

    if "|" not in value:

        return None, None

    public_id, extension = (
        value.rsplit(
            "|",
            1
        )
    )

    public_id = public_id.strip()

    extension = (
        extension
        .strip()
        .lower()
    )

    if not public_id:

        return None, None

    if extension not in app.config[
        "ALLOWED_EXTENSIONS"
    ]:

        return None, None

    return (
        public_id,
        extension
    )


# ============================================================
# CV STORAGE
# ============================================================

def save_uploaded_file(file):

    """
    PRODUCTION CV STORAGE

    CV is stored in Cloudinary authenticated RAW storage.

    We intentionally DO NOT silently fallback to Render
    local storage.

    Why?

    Render local filesystem is not persistent storage.
    A restart/redeploy can remove local uploaded files.

    Therefore:

        Applicant
            ↓
        Cloudinary
            ↓
        Database reference

    """

    if not file or not file.filename:

        return None

    if not allowed_file(
        file.filename
    ):

        print(
            "[CV] Invalid CV extension."
        )

        return None

    original = secure_filename(
        file.filename
    )

    if not original:

        return None

    name, ext = os.path.splitext(
        original
    )

    extension = (
        ext
        .lower()
        .lstrip(".")
    )

    if extension not in app.config[
        "ALLOWED_EXTENSIONS"
    ]:

        return None

    # --------------------------------------------------------
    # CLOUDINARY REQUIRED
    # --------------------------------------------------------

    if not cloudinary_ready():

        print(
            "[CV] ERROR: Cloudinary is not configured."
        )

        print(
            "[CV] Upload rejected to prevent "
            "CV loss on Render restart/redeploy."
        )

        return None

    timestamp = datetime.utcnow().strftime(
        "%Y%m%d%H%M%S%f"
    )

    safe_name = (
        secure_filename(name)
        or "cv"
    )

    unique_name = (
        f"{safe_name}_{timestamp}"
    )

    try:

        print(
            "[CV] Uploading CV to Cloudinary..."
        )

        result = cloudinary.uploader.upload(
            file,
            resource_type="raw",
            type="authenticated",
            folder=app.config[
                "CLOUDINARY_CV_FOLDER"
            ],
            public_id=unique_name,
            overwrite=False
        )

        public_id = result.get(
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
            "[CV] SUCCESS:",
            public_id
        )

        return stored_reference

    except Exception as e:

        print(
            "[CV] CLOUDINARY UPLOAD FAILED:"
        )

        print(
            str(e)
        )

        traceback.print_exc()

        return None


def delete_uploaded_file(filename):

    """
    Deletes a CV only when explicitly requested.

    Existing candidate CVs are NOT automatically deleted
    during normal application operations.
    """

    if not filename:

        return

    if is_cloudinary_cv(
        filename
    ):

        public_id, extension = (
            parse_cloudinary_cv(
                filename
            )
        )

        if not public_id:

            return

        if not cloudinary_ready():

            print(
                "[CV DELETE] Cloudinary not configured."
            )

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

    # --------------------------------------------------------
    # OLD LOCAL CV SUPPORT
    # --------------------------------------------------------

    try:

        safe_filename = secure_filename(
            os.path.basename(
                filename
            )
        )

        if not safe_filename:

            return

        directories = [

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

        for directory in directories:

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

    public_id, extension = (
        parse_cloudinary_cv(
            filename
        )
    )

    if not public_id:

        return None

    if not cloudinary_ready():

        return None

    try:

        expires_at = int(
            (
                datetime.utcnow()
                + timedelta(
                    minutes=10
                )
            ).timestamp()
        )

        url = (
            cloudinary.utils
            .private_download_url(
                public_id,
                extension,
                resource_type="raw",
                type="authenticated",
                attachment=False,
                expires_at=expires_at
            )
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
        f"{secure_filename(name) or 'job'}_"
        f"{timestamp}"
        f"{ext.lower()}"
    )

    path = os.path.join(
        app.config[
            "UPLOAD_FOLDER_JOBS"
        ],
        filename
    )

    try:

        os.makedirs(
            app.config[
                "UPLOAD_FOLDER_JOBS"
            ],
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
            os.path.basename(
                filename
            )
        )

        if not safe_filename:

            return

        path = os.path.join(
            app.config[
                "UPLOAD_FOLDER_JOBS"
            ],
            safe_filename
        )

        if os.path.isfile(path):

            os.remove(path)

    except Exception:

        traceback.print_exc()


# ============================================================
# SECURITY
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

        return f(
            *args,
            **kwargs
        )

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

        db.session.add(
            audit
        )

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        print(
            "[AUDIT ERROR]",
            str(e)
        )


# ============================================================
# EMAIL
# ============================================================

def send_async_email(message):

    try:

        with app.app_context():

            mail.send(
                message
            )

    except Exception as e:

        print(
            "[EMAIL ERROR]",
            str(e)
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

        status_message = (
            status_messages.get(
                new_status,
                "Your application status has been updated."
            )
        )

        notes_html = ""

        if notes:

            safe_notes = (
                notes
                .replace(
                    "&",
                    "&amp;"
                )
                .replace(
                    "<",
                    "&lt;"
                )
                .replace(
                    ">",
                    "&gt;"
                )
                .replace(
                    "\n",
                    "<br>"
                )
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
                Dear
                <strong>
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
            "[EMAIL DISPATCH ERROR]",
            str(e)
        )


# ============================================================
# SIMILAR JOBS
# ============================================================

def get_similar_jobs(
    job,
    limit=3
):

    query = published_jobs_query().filter(
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
# GLOBAL TEMPLATE CONTEXT
# ============================================================

@app.context_processor
def inject_globals():

    try:

        return {

            "now":
                datetime.utcnow,

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
                .all(),

            "current_admin":
                session.get(
                    "admin_username"
                ),

            "admin_logged_in":
                bool(
                    session.get(
                        "admin_logged_in"
                    )
                )
        }

    except Exception:

        return {

            "now":
                datetime.utcnow,

            "all_departments": [],

            "all_locations": [],

            "current_admin": None,

            "admin_logged_in": False
        }


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    featured_jobs = (
        published_jobs_query()
        .filter(
            Job.is_featured.is_(True)
        )
        .order_by(
            Job.created_at.desc()
        )
        .limit(6)
        .all()
    )

    latest_jobs = (
        published_jobs_query()
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

    type_filter = (
        request.args
        .get(
            "type",
            ""
        )
        .strip()
    )

    experience_filter = (
        request.args
        .get(
            "experience",
            ""
        )
        .strip()
    )

    search_query = (
        request.args
        .get(
            "q",
            ""
        )
        .strip()
    )

    query = published_jobs_query()

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

        search = (
            f"%{search_query}%"
        )

        query = query.filter(
            db.or_(
                Job.title.ilike(
                    search
                ),

                Job.short_description.ilike(
                    search
                ),

                Job.full_description.ilike(
                    search
                )
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
        departments=(
            Department.query
            .order_by(
                Department.name
            )
            .all()
        ),
        locations=(
            Location.query
            .order_by(
                Location.name
            )
            .all()
        )
    )


# ============================================================
# PUBLIC JOB DETAIL
# ============================================================

@app.route(
    "/job/<int:job_id>"
)
def job_detail(job_id):

    job = (
        published_jobs_query()
        .filter(
            Job.id == job_id
        )
        .first()
    )

    if not job:

        abort(404)

    return render_template(
        "job_detail.html",
        job=job,
        similar_jobs=get_similar_jobs(
            job
        )
    )


# ============================================================
# DEPARTMENTS
# ============================================================

@app.route(
    "/departments"
)
def departments():

    return render_template(
        "departments.html",
        departments=(
            Department.query
            .order_by(
                Department.name
            )
            .all()
        )
    )


@app.route(
    "/department/<int:dept_id>"
)
def department_detail(
    dept_id
):

    department = (
        Department.query
        .get_or_404(
            dept_id
        )
    )

    jobs_list = (
        published_jobs_query()
        .filter(
            Job.department_id
            == dept_id
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

@app.route(
    "/locations"
)
def locations():

    return render_template(
        "locations.html",
        locations=(
            Location.query
            .order_by(
                Location.name
            )
            .all()
        )
    )


# ============================================================
# ABOUT
# ============================================================

@app.route(
    "/about-careers"
)
def about_careers():

    return render_template(
        "about_careers.html"
    )


# ============================================================
# TRACK APPLICATION STATUS
# ============================================================

@app.route(
    "/track-status",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/application/lookup",
    methods=[
        "GET",
        "POST"
    ]
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
                    reference_no=
                    reference_no
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
    methods=[
        "GET",
        "POST"
    ]
)
def apply(job_id):

    job = (
        published_jobs_query()
        .filter(
            Job.id == job_id
        )
        .first()
    )

    if not job:

        abort(404)

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
                "Please make sure Cloudinary is configured "
                "and upload PDF, DOC, or DOCX.",
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
def application_success(
    app_id
):

    application = (
        Application.query
        .get_or_404(
            app_id
        )
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
def application_status(
    app_id
):

    application = (
        Application.query
        .get_or_404(
            app_id
        )
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
    methods=[
        "GET",
        "POST"
    ]
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
                url_for(
                    "talent_pool"
                )
            )

        cv_filename = save_uploaded_file(
            form.cv_file.data
        )

        if not cv_filename:

            flash(
                "Invalid CV or Cloudinary is not configured. "
                "Please upload PDF, DOC, or DOCX.",
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

            preferred_department=(
                form.preferred_department.data
                or ""
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
            url_for(
                "home"
            )
        )

    return render_template(
        "talent_pool.html",
        form=form
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/login",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/auth/login",
    methods=[
        "GET",
        "POST"
    ]
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

            return render_login_template(
                form=form
            )

        # ----------------------------------------------------
        # DATABASE LOGIN
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # ENVIRONMENT LOGIN FALLBACK
        # ----------------------------------------------------

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
            username
            == default_username
            and default_hash
        ):

            try:

                valid_password = (
                    check_password_hash(
                        default_hash,
                        password
                    )
                )

            except Exception:

                valid_password = False

            if valid_password:

                admin_id = None

                try:

                    new_admin = AdminUser(

                        username=username,

                        password_hash=
                            default_hash
                    )

                    db.session.add(
                        new_admin
                    )

                    db.session.commit()

                    admin_id = (
                        new_admin.id
                    )

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

                        admin_id = (
                            existing.id
                        )

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
                        "logged in via environment fallback."
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

    return render_login_template(
        form=form
    )


# ============================================================
# CHANGE PASSWORD
# ============================================================

@app.route(
    "/admin/change-password",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/change-password",
    methods=[
        "GET",
        "POST"
    ]
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
                    "changed their password."
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

@app.route(
    "/admin/logout"
)
@app.route(
    "/hr/logout"
)
@app.route(
    "/auth/logout"
)
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
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/forgot-password",
    methods=[
        "GET",
        "POST"
    ]
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

    if template_exists(
        "hr/forgot_password.html"
    ):

        return render_template(
            "hr/forgot_password.html"
        )

    return render_template(
        "forgot_password.html"
    )


# ============================================================
# HR / ADMIN DASHBOARD
# ============================================================

@app.route(
    "/admin"
)
@app.route(
    "/admin/dashboard"
)
@app.route(
    "/hr"
)
@app.route(
    "/hr/dashboard"
)
@admin_required
def admin_dashboard():

    total_jobs = Job.query.count()

    active_jobs = (
        Job.query
        .filter(
            Job.is_active.is_(True)
        )
        .count()
    )

    published_jobs = (
        Job.query
        .filter(
            Job.status == "PUBLISHED",
            Job.is_active.is_(True)
        )
        .count()
    )

    draft_jobs = (
        Job.query
        .filter(
            Job.status == "DRAFT"
        )
        .count()
    )

    closed_jobs = (
        Job.query
        .filter(
            Job.status == "CLOSED"
        )
        .count()
    )

    total_applications = (
        Application.query.count()
    )

    total_interviews = (
        Interview.query.count()
    )

    total_talent_pool = (
        TalentPool.query.count()
    )

    new_applications = (
        Application.query
        .filter_by(
            status="NEW"
        )
        .count()
    )

    selected_applications = (
        Application.query
        .filter_by(
            status="SELECTED"
        )
        .count()
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

    recent_jobs = (
        Job.query
        .order_by(
            Job.created_at.desc()
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

    context = {

        "total_jobs":
            total_jobs,

        "active_jobs":
            active_jobs,

        "published_jobs":
            published_jobs,

        "draft_jobs":
            draft_jobs,

        "closed_jobs":
            closed_jobs,

        "total_applications":
            total_applications,

        "total_interviews":
            total_interviews,

        "total_talent_pool":
            total_talent_pool,

        "new_applications":
            new_applications,

        "selected_applications":
            selected_applications,

        "recent_applications":
            recent_applications,

        "applications":
            recent_applications,

        "notifications":
            notifications,

        "recent_jobs":
            recent_jobs,

        "jobs":
            recent_jobs,

        "vacancies":
            recent_jobs,

        "status_counts":
            status_counts
    }

    return render_hr_template(
        "hr/dashboard.html",
        "admin/dashboard.html",
        **context
    )


# ============================================================
# APPLICATIONS / CANDIDATES
# ============================================================

@app.route(
    "/admin/candidates"
)
@app.route(
    "/hr/candidates"
)
@app.route(
    "/admin/applications"
)
@app.route(
    "/hr/applications"
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
                Application.full_name.ilike(
                    search_value
                ),

                Application.email.ilike(
                    search_value
                ),

                Application.phone.ilike(
                    search_value
                ),

                Application.reference_no.ilike(
                    search_value
                )
            )
        )

    status_filter = (
        request.args
        .get(
            "status",
            ""
        )
        .strip()
        .upper()
    )

    if status_filter:

        status_filter = (
            status_filter
            .replace(
                "UNDER_REVIEW",
                "UNDER REVIEW"
            )
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

    context = {

        "applications":
            applications,

        "candidates":
            applications,

        "departments":
            Department.query
            .order_by(
                Department.name
            )
            .all(),

        "statuses": [
            "NEW",
            "UNDER REVIEW",
            "SHORTLISTED",
            "INTERVIEW",
            "SELECTED",
            "HIRED",
            "REJECTED"
        ],

        "search":
            search,

        "status_filter":
            status_filter
    }

    return render_hr_template(
        "hr/applications.html",
        "admin/candidates.html",
        **context
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
@app.route(
    "/admin/application/<int:app_id>"
)
@app.route(
    "/hr/applications/<int:app_id>"
)
@admin_required
def admin_candidate_detail(
    app_id
):

    application = (
        Application.query
        .get_or_404(
            app_id
        )
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

    context = {

        "application":
            application,

        "candidate":
            application,

        "interviews":
            interviews
    }

    return render_hr_template(
        "hr/application_detail.html",
        "admin/candidate_detail.html",
        **context
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
@app.route(
    "/hr/applications/<int:app_id>/cv"
)
@app.route(
    "/hr/applications/<int:app_id>/cv/download"
)
@app.route(
    "/admin/application/<int:app_id>/cv"
)
@admin_required
def download_candidate_cv(
    app_id
):

    # --------------------------------------------------------
    # SECURITY
    #
    # This route cannot be used by public users.
    # Login is required.
    # --------------------------------------------------------

    application = (
        Application.query
        .get_or_404(
            app_id
        )
    )

    filename = (
        application.cv_filename
    )

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

    # --------------------------------------------------------
    # CLOUDINARY
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # OLD LOCAL FILE SUPPORT
    # --------------------------------------------------------

    safe_filename = secure_filename(
        os.path.basename(
            filename
        )
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

    directories = [

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

    directories = list(
        dict.fromkeys(
            directory
            for directory
            in directories
            if directory
        )
    )

    for directory in directories:

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
# APPLICATION STATUS UPDATE
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
    "/hr/applications/<int:app_id>/status",
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
def update_application_status(
    app_id
):

    application = (
        Application.query
        .get_or_404(
            app_id
        )
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

    new_status = (
        new_status
        .replace(
            "UNDER_REVIEW",
            "UNDER REVIEW"
        )
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

    old_status = (
        application.status
    )

    application.status = (
        new_status
    )

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

        application.notes = (
            notes
        )

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

    # --------------------------------------------------------
    # DATABASE NOTIFICATION
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # AUDIT
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

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
@app.route(
    "/hr/vacancies"
)
@app.route(
    "/admin/vacancies"
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

    context = {

        "jobs":
            jobs_list,

        "vacancies":
            jobs_list
    }

    return render_hr_template(
        "hr/vacancies.html",
        "admin/jobs.html",
        **context
    )


# ============================================================
# JOB FORM CHOICES
# ============================================================

def configure_job_form_choices(
    form
):

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
        [
            (
                0,
                "None"
            )
        ]
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
        [
            (
                0,
                "None"
            )
        ]
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
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/job/new",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/vacancy/new",
    methods=[
        "GET",
        "POST"
    ]
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

            selected_status = (
                form.status.data
                or "PUBLISHED"
            )

            if selected_status == "PUBLISHED":

                is_active = True

                published_at = (
                    datetime.utcnow()
                )

            elif selected_status == "CLOSED":

                is_active = False

                published_at = None

            else:

                is_active = False

                published_at = None

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

                status=selected_status,

                is_active=is_active,

                is_featured=bool(
                    form.is_featured.data
                ),

                banner_image=banner_image,

                published_at=published_at
            )

            try:

                db.session.add(
                    job
                )

                db.session.commit()

                log_audit(
                    "Created Job",

                    (
                        f"Created vacancy "
                        f"{job.title} "
                        f"with status "
                        f"{job.status}"
                    ),

                    "Job",

                    job.id
                )

                flash(
                    "የስራ ማስታወቂያው በስኬት ተፈጥሯል!",
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
                "እባክዎን የስራ መረጃዎችን በትክክል ይሙሉ።",
                "warning"
            )

    return render_hr_template(
        "hr/vacancy_form.html",
        "admin/job_form.html",
        form=form,
        is_new=True
    )


# ============================================================
# EDIT JOB
# ============================================================

@app.route(
    "/admin/job/<int:job_id>/edit",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/job/<int:job_id>/edit",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/vacancy/<int:job_id>/edit",
    methods=[
        "GET",
        "POST"
    ]
)
@admin_required
def admin_job_edit(
    job_id
):

    job = (
        Job.query
        .get_or_404(
            job_id
        )
    )

    form = JobForm()

    configure_job_form_choices(
        form
    )

    if request.method == "GET":

        form.title.data = (
            job.title
        )

        form.department_id.data = (
            job.department_id
            or 0
        )

        form.location_id.data = (
            job.location_id
            or 0
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

        form.status.data = (
            job.status
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

            selected_status = (
                form.status.data
                or "PUBLISHED"
            )

            job.title = (
                form.title.data
                .strip()
            )

            job.department_id = (
                form.department_id.data
                if (
                    form.department_id.data
                    and
                    form.department_id.data != 0
                )
                else None
            )

            job.location_id = (
                form.location_id.data
                if (
                    form.location_id.data
                    and
                    form.location_id.data != 0
                )
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

            job.status = (
                selected_status
            )

            if selected_status == "PUBLISHED":

                job.is_active = True

                if not job.published_at:

                    job.published_at = (
                        datetime.utcnow()
                    )

            elif selected_status == "CLOSED":

                job.is_active = False

            else:

                job.is_active = False

            job.is_featured = bool(
                form.is_featured.data
            )

            if new_banner:

                job.banner_image = (
                    new_banner
                )

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
                        f"Updated vacancy "
                        f"{job.title} "
                        f"status={job.status}"
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

    return render_hr_template(
        "hr/vacancy_form.html",
        "admin/job_form.html",
        form=form,
        is_new=False,
        job=job
    )


# ============================================================
# TOGGLE / PUBLISH / CLOSE JOB
# ============================================================

@app.route(
    "/admin/job/<int:job_id>/toggle",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/job/<int:job_id>/toggle",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/vacancy/<int:job_id>/toggle",
    methods=[
        "GET",
        "POST"
    ]
)
@admin_required
def admin_job_toggle(
    job_id
):

    job = (
        Job.query
        .get_or_404(
            job_id
        )
    )

    if job.status == "PUBLISHED":

        job.status = "CLOSED"

        job.is_active = False

        message = (
            "Job closed."
        )

    else:

        job.status = "PUBLISHED"

        job.is_active = True

        if not job.published_at:

            job.published_at = (
                datetime.utcnow()
            )

        message = (
            "Job published."
        )

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        traceback.print_exc()

        flash(
            "Could not update vacancy.",
            "danger"
        )

        return redirect(
            url_for(
                "admin_jobs"
            )
        )

    log_audit(
        "Changed Job Status",

        (
            f"{job.title} "
            f"status changed to "
            f"{job.status}"
        ),

        "Job",

        job.id
    )

    flash(
        message,
        "success"
    )

    return redirect(
        url_for(
            "admin_jobs"
        )
    )


# ============================================================
# DELETE JOB
# ============================================================

@app.route(
    "/admin/job/<int:job_id>/delete",
    methods=[
        "POST",
        "GET"
    ]
)
@app.route(
    "/hr/job/<int:job_id>/delete",
    methods=[
        "POST",
        "GET"
    ]
)
@admin_required
def admin_job_delete(
    job_id
):

    job = (
        Job.query
        .get_or_404(
            job_id
        )
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
                "CLOSED አድርገው ይዝጉት።"
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

        title = job.title

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
                f"{title}"
            ),

            "Job",

            job_id
        )

        flash(
            "የስራ ማስታወቂያው ተሰርዟል!",
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
# INTERVIEWS
# ============================================================

@app.route(
    "/admin/interviews"
)
@app.route(
    "/hr/interviews"
)
@admin_required
def admin_interviews():

    interviews = (
        Interview.query
        .order_by(
            Interview.scheduled_at.desc()
        )
        .all()
    )

    return render_hr_template(
        "hr/interviews.html",
        "admin/interviews.html",
        interviews=interviews
    )


# ============================================================
# INTERVIEW CREATE
# ============================================================

@app.route(
    "/admin/interview/new",
    methods=[
        "GET",
        "POST"
    ]
)
@app.route(
    "/hr/interview/new",
    methods=[
        "GET",
        "POST"
    ]
)
@admin_required
def admin_interview_new():

    form = InterviewForm()

    applications = (
        Application.query
        .order_by(
            Application.full_name.asc()
        )
        .all()
    )

    form.application_id.choices = [
        (
            application.id,
            (
                f"{application.full_name} - "
                f"{application.reference_no or application.id}"
            )
        )
        for application
        in applications
    ]

    if form.validate_on_submit():

        scheduled_at = None

        raw_datetime = (
            form.scheduled_at.data
            .strip()
        )

        try:

            scheduled_at = (
                datetime.fromisoformat(
                    raw_datetime
                )
            )

        except Exception:

            try:

                scheduled_at = (
                    datetime.strptime(
                        raw_datetime,
                        "%Y-%m-%d %H:%M"
                    )
                )

            except Exception:

                flash(
                    "Invalid interview date/time.",
                    "danger"
                )

                return render_hr_template(
                    "hr/interview_form.html",
                    "admin/interviews.html",
                    form=form,
                    applications=applications
                )

        interview = Interview(

            application_id=(
                form.application_id.data
            ),

            scheduled_at=scheduled_at,

            duration_minutes=(
                form.duration_minutes.data
            ),

            interview_type=(
                form.interview_type.data
            ),

            interviewer_name=(
                form.interviewer_name.data
                or None
            ),

            location=(
                form.location.data
                or None
            ),

            notes=(
                form.notes.data
                or None
            )
        )

        try:

            db.session.add(
                interview
            )

            db.session.commit()

            log_audit(
                "Created Interview",
                (
                    f"Created interview "
                    f"for application "
                    f"{interview.application_id}"
                ),
                "Interview",
                interview.id
            )

            flash(
                "Interview created successfully.",
                "success"
            )

            return redirect(
                url_for(
                    "admin_interviews"
                )
            )

        except Exception:

            db.session.rollback()

            traceback.print_exc()

            flash(
                "Could not create interview.",
                "danger"
            )

    return render_hr_template(
        "hr/interview_form.html",
        "admin/interviews.html",
        form=form,
        applications=applications
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

    return render_hr_template(
        "hr/talent_pool.html",
        "admin/talent_pool.html",
        candidates=candidates,
        entries=candidates,
        talent_pool=candidates
    )


# ============================================================
# TALENT POOL CV DOWNLOAD
# ============================================================

@app.route(
    "/admin/talent-pool/<int:talent_id>/cv"
)
@app.route(
    "/hr/talent-pool/<int:talent_id>/cv"
)
@admin_required
def download_talent_pool_cv(
    talent_id
):

    candidate = (
        TalentPool.query
        .get_or_404(
            talent_id
        )
    )

    filename = (
        candidate.cv_filename
    )

    if not filename:

        flash(
            "CV not found.",
            "warning"
        )

        return redirect(
            request.referrer
            or url_for(
                "admin_talent_pool"
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
                "Talent Pool CV Download",
                (
                    f"HR downloaded Talent Pool "
                    f"CV for {candidate.full_name}"
                ),
                "TalentPool",
                candidate.id
            )

            return redirect(
                download_url
            )

        flash(
            "Cloudinary CV could not be opened.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "admin_talent_pool"
            )
        )

    safe_filename = secure_filename(
        os.path.basename(
            filename
        )
    )

    directories = [

        app.config.get(
            "UPLOAD_FOLDER"
        ),

        os.path.join(
            BASE_DIR,
            "uploads",
            "resumes"
        )
    ]

    for directory in directories:

        if not directory:

            continue

        path = os.path.join(
            directory,
            safe_filename
        )

        if os.path.isfile(path):

            return send_from_directory(
                directory,
                safe_filename,
                as_attachment=False
            )

    flash(
        "CV file not found on server.",
        "danger"
    )

    return redirect(
        request.referrer
        or url_for(
            "admin_talent_pool"
        )
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

    return render_hr_template(
        "hr/audit_log.html",
        "admin/audit_log.html",
        logs=logs
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route(
    "/admin/notifications"
)
@app.route(
    "/hr/notifications"
)
@admin_required
def admin_notifications():

    notifications = (
        Notification.query
        .order_by(
            Notification.created_at.desc()
        )
        .limit(100)
        .all()
    )

    return render_hr_template(
        "hr/notifications.html",
        "admin/dashboard.html",
        notifications=notifications,
        applications=[],
        recent_applications=[],
        jobs=[],
        vacancies=[]
    )


# ============================================================
# MARK NOTIFICATION READ
# ============================================================

@app.route(
    "/admin/notification/<int:notification_id>/read",
    methods=[
        "POST",
        "GET"
    ]
)
@app.route(
    "/hr/notification/<int:notification_id>/read",
    methods=[
        "POST",
        "GET"
    ]
)
@admin_required
def mark_notification_read(
    notification_id
):

    notification = (
        Notification.query
        .get_or_404(
            notification_id
        )
    )

    notification.is_read = True

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

    return redirect(
        request.referrer
        or url_for(
            "admin_dashboard"
        )
    )


# ============================================================
# DATABASE MIGRATION HELPERS
# ============================================================

def safe_add_column(
    table_name,
    column_name,
    column_type,
    default_value=None
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

        # ----------------------------------------------------
        # Important:
        # Existing PostgreSQL tables may contain rows.
        #
        # We first add the column nullable/default,
        # backfill it,
        # then attempt to make it NOT NULL where supported.
        # ----------------------------------------------------

        type_str = str(
            column_type
        ).upper()

        if default_value is not None:

            escaped_default = str(
                default_value
            ).replace(
                "'",
                "''"
            )

            default_sql = (
                f" DEFAULT '{escaped_default}'"
            )

        elif (
            "BOOLEAN"
            in type_str
        ):

            default_sql = (
                " DEFAULT FALSE"
            )

        elif (
            "INTEGER"
            in type_str
        ):

            default_sql = (
                " DEFAULT 0"
            )

        elif (
            "VARCHAR"
            in type_str
            or "TEXT"
            in type_str
        ):

            default_sql = (
                " DEFAULT ''"
            )

        else:

            default_sql = ""

        sql = (
            f'ALTER TABLE "{table_name}" '
            f'ADD COLUMN "{column_name}" '
            f'{column_type}'
            f'{default_sql}'
        )

        with db.engine.begin() as connection:

            connection.execute(
                text(sql)
            )

        print(
            "[DB AUTO-MIGRATION] Added:",
            f"{table_name}.{column_name}"
        )

    except Exception as e:

        print(
            "[DB WARNING] Could not add column:",
            f"{table_name}.{column_name}",
            str(e)
        )


def migrate_existing_database():

    # First create all tables that don't exist.
    db.create_all()

    # --------------------------------------------------------
    # Re-inspect AFTER create_all.
    # --------------------------------------------------------

    inspector = inspect(
        db.engine
    )

    existing_tables = set(
        inspector.get_table_names()
    )

    # --------------------------------------------------------
    # TALENT POOL
    # --------------------------------------------------------

    if "talent_pool" in existing_tables:

        safe_add_column(
            "talent_pool",
            "preferred_department",
            "VARCHAR(120)",
            ""
        )

    # --------------------------------------------------------
    # JOB STATUS
    # --------------------------------------------------------

    if "jobs" in existing_tables:

        safe_add_column(
            "jobs",
            "status",
            "VARCHAR(20)",
            "PUBLISHED"
        )

        safe_add_column(
            "jobs",
            "published_at",
            "TIMESTAMP"
        )

    # --------------------------------------------------------
    # Backfill jobs safely.
    # --------------------------------------------------------

    try:

        if "jobs" in existing_tables:

            with db.engine.begin() as connection:

                connection.execute(
                    text(
                        """
                        UPDATE jobs
                        SET status =
                            CASE
                                WHEN is_active = TRUE
                                THEN 'PUBLISHED'
                                ELSE 'CLOSED'
                            END
                        WHERE status IS NULL
                           OR status = ''
                        """
                    )
                )

    except Exception as e:

        print(
            "[DB WARNING] Job status backfill failed:",
            str(e)
        )

    # --------------------------------------------------------
    # Backfill published_at
    # --------------------------------------------------------

    try:

        if "jobs" in existing_tables:

            with db.engine.begin() as connection:

                connection.execute(
                    text(
                        """
                        UPDATE jobs
                        SET published_at = created_at
                        WHERE status = 'PUBLISHED'
                          AND published_at IS NULL
                        """
                    )
                )

    except Exception as e:

        print(
            "[DB WARNING] published_at backfill failed:",
            str(e)
        )

    # --------------------------------------------------------
    # TALENT POOL BACKFILL
    # --------------------------------------------------------

    try:

        if "talent_pool" in existing_tables:

            with db.engine.begin() as connection:

                connection.execute(
                    text(
                        """
                        UPDATE talent_pool
                        SET preferred_department = ''
                        WHERE preferred_department IS NULL
                        """
                    )
                )

    except Exception as e:

        print(
            "[DB WARNING] Talent Pool backfill failed:",
            str(e)
        )

    # --------------------------------------------------------
    # Generic model-column migration.
    #
    # This handles other missing nullable columns.
    # --------------------------------------------------------

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

    inspector = inspect(
        db.engine
    )

    for model in models:

        table_name = (
            model.__tablename__
        )

        if (
            table_name
            not in inspector.get_table_names()
        ):

            continue

        try:

            existing_columns = {
                column["name"]
                for column
                in inspector.get_columns(
                    table_name
                )
            }

        except Exception:

            continue

        for column in model.__table__.columns:

            if column.name in existing_columns:

                continue

            if column.primary_key:

                continue

            # Skip fields already explicitly handled.
            if (
                table_name == "jobs"
                and column.name
                in [
                    "status",
                    "published_at"
                ]
            ):

                continue

            if (
                table_name == "talent_pool"
                and column.name
                == "preferred_department"
            ):

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

    # --------------------------------------------------------
    # ADMIN
    # --------------------------------------------------------

    username = app.config[
        "HR_USERNAME"
    ]

    admin = (
        AdminUser.query
        .filter_by(
            username=username
        )
        .first()
    )

    if not admin:

        db.session.add(
            AdminUser(

                username=username,

                password_hash=
                    app.config[
                        "HR_PASSWORD_HASH"
                    ]
            )
        )

    # --------------------------------------------------------
    # DEPARTMENTS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # HAWASSA LOCATION
    # --------------------------------------------------------

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

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        traceback.print_exc()


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db_safe():

    with app.app_context():

        try:

            migrate_existing_database()

            seed_default_data()

            print(
                "======================================"
            )

            print(
                "RORI HOTEL DATABASE INITIALIZATION OK"
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
# HEALTH CHECK
# ============================================================

@app.route(
    "/health"
)
def health():

    try:

        db.session.execute(
            text(
                "SELECT 1"
            )
        )

        return jsonify(
            {
                "status": "ok",
                "database": "connected",
                "cloudinary":
                    cloudinary_ready()
            }
        )

    except Exception as e:

        return jsonify(
            {
                "status": "error",
                "database": "error",
                "cloudinary":
                    cloudinary_ready(),
                "message": str(e)
            }
        ), 500


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    if template_exists(
        "404.html"
    ):

        return render_template(
            "404.html"
        ), 404

    return (
        "404 - Page Not Found",
        404
    )


@app.errorhandler(413)
def file_too_large(error):

    flash(
        "File is too large. Maximum size is 10 MB.",
        "danger"
    )

    return redirect(
        request.referrer
        or url_for(
            "home"
        )
    )


@app.errorhandler(500)
def internal_server_error(
    error
):

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

    if template_exists(
        "500.html"
    ):

        return render_template(
            "500.html"
        ), 500

    return (
        "500 - Internal Server Error",
        500
    )


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