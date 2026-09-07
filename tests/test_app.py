import unittest
from app import app, db

class BasicTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.drop_all()

    def test_home_page(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'RORI HOTEL', response.data)

    def test_jobs_page(self):
        response = self.app.get('/jobs')
        self.assertEqual(response.status_code, 200)

    def test_admin_login_page(self):
        response = self.app.get('/auth/login')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()