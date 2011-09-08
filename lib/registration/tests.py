from django.test import TestCase

class RegistrationViewsTestCase(TestCase):
    def test_index(self):
        resp = self.client.get('/account/login')
        self.assertEqual(resp.status_code, 200)