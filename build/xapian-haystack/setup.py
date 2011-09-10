import os
from distutils.core import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name='xapian-haystack',
    version='1.1.5beta',
    description="A Xapian backend for Haystack",
    long_description=read('README.rst'),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Framework :: Django',
    ],
    author='David Sauve',
    author_email='dsauve@trapeze.com',
    url='http://github.com/notanumber/xapian-haystack',
    license='GPL3',
    py_modules=['xapian_backend'],
)
