from django.test import TestCase

from parser.models import File

class FileTestCase(TestCase):
    def test_all_things(self):
        path = '/tmp/abcd_file_module'
        open(path, 'w').write('abc')
        self.assertTrue(File.objects.is_changed(path))
        File.objects.save_file(path=path)
        self.assertFalse(File.objects.is_changed(path))
        open(path, 'w').write('def')
        self.assertTrue(File.objects.is_changed(path))
        File.objects.save_file(path=path)
        self.assertFalse(File.objects.is_changed(path))
        self.assertTrue(File.objects.is_changed(path, content=':-)'))

        File.objects.save_file(path='/mario', content='xyz')
        self.assertFalse(File.objects.is_changed('/mario', content='xyz'))
