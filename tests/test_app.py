/* ============================================
   TESTS / TEST_APP.PY - Unit Test Suite
   Rori Hotel Careers Portal
   ============================================ */

import io
import unittest
from app import app, db, Job, Department


class RoriCareersTestCase(unittest.TestCase):
    def setUp(self):
        """የሙከራ አካባቢ (Testing Environment) ማዘጋጃ።"""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # በቴስት ወቅት CSRF ጥበቃን ለማገድ
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['MAIL_SUPPRESS_SEND'] = True  # የኢሜይል መላክን ለሙከራ ለማገድ

        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

        db.create_all()
        self._seed_test_data()

    def tearDown(self):
        """የሙከራ አካባቢ እና ዳታቤዝ ማጽጃ።"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _seed_test_data(self):
        """ለሙከራ የሚሆኑ መነሻ ዳታዎችን (Mock Data) በዳታቤዝ ውስጥ ይፈጥራል።"""
        dept = Department(name="Information Technology")
        db.session.add(dept)
        db.session.commit()

        job = Job(
            title="IT Support Specialist",
            description="Provide technical support for hotel IT systems.",
            requirements="Degree/Diploma in IT or related fields.",
            department_id=dept.id,
            employment_type="Full-time",
            is_active=True
        )
        db.session.add(job)
        db.session.commit()

    # ===== PUBLIC PAGES TESTS =====

    def test_home_page(self):
        """የመግቢያ ገፅ (Home Page) መስራቱን ያረጋግጣል።"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'RORI HOTEL', response.data)

    def test_jobs_page(self):
        """የሥራ ማስታወቂያዎች ዝርዝር ገፅ መስራቱን ያረጋግጣል።"""
        response = self.client.get('/jobs')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'IT Support Specialist', response.data)

    def test_job_details_page(self):
        """የነጠላ ሥራ ዝርዝር ገፅ መከፈቱን ያረጋግጣል።"""
        job = Job.query.first()
        response = self.client.get(f'/jobs/{job.id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'IT Support Specialist', response.data)

    # ===== APPLICATION SUBMISSION TESTS =====

    def test_submit_job_application(self):
        """የሥራ ማመልከቻ ፎርም በስኬት መላኩንና CV መጫኑን ያረጋግጣል።"""
        job = Job.query.first()
        data = {
            'full_name': 'Abebe Bikila',
            'email': 'abebe@example.com',
            'phone': '+251911223344',
            'cover_letter': 'I am applying for the IT Support position.',
            'resume': (io.BytesIO(b"%PDF-1.4 Mock CV Content"), 'test_resume.pdf')
        }

        response = self.client.post(
            f'/apply/{job.id}',
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)

    # ===== SECURITY & ADMIN TESTS =====

    def test_admin_login_page_renders(self):
        """የአድሚን መግቢያ ገፅ መከፈቱን ያረጋግጣል።"""
        response = self.client.get('/auth/login')
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_admin_dashboard_access(self):
        """ያልተፈቀደለት ሰው የአድሚን ዳሽቦርድ እንዳይከፍት መከልከሉን ያረጋግጣል።"""
        response = self.client.get('/admin/dashboard', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'login', response.request.path.lower())


if __name__ == '__main__':
    unittest.main()
