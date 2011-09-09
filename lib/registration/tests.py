from django.test import TestCase
from django.test.client import Client 
from forms import SignupForm, UserField

class RegistrationViewsTestCase(TestCase):

    def test_index(self):
    	client = Client()
        resp = client.get('/accounts/login')
        self.assertEqual(resp.status_code, 200)

    def test_form(self):
    	form = SignupForm()
        self.assertFalse(form.is_valid())
    
    def test_register(self):
    	client = Client()
        resp = client.post('/registration/register', {'first_name': 'first_name', 'last_name': 'last_name', 'username': 'username', 'password': 'password', 'password2': 'password','email': 'email@email.com', 'email2': 'email@email.com'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue('first_name' in resp.content, 'first_name not in the returned page')
        self.assertTrue('last_name' in resp.content, 'last_name not in the returned page')
        self.assertTrue('username' in resp.content, 'username not in the returned page')
        self.assertTrue('password' in resp.content, 'password not in the returned page')
        self.assertTrue('email@email.com' in resp.content, 'email not in the returned page')