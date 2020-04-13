from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='tomtoolkit',
    version='1.3.1',
    description='The TOM Toolkit and base modules',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://tomtoolkit.github.io',
    author='TOM Toolkit Project',
    author_email='ariba@lco.global',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Topic :: Scientific/Engineering :: Astronomy',
        'Topic :: Scientific/Engineering :: Physics'
    ],
    keywords=['tomtoolkit', 'astronomy', 'astrophysics', 'cosmology', 'science', 'fits', 'observatory'],
    packages=find_packages(),
    install_requires=[
        'astroquery',
        'astroplan',
        'astropy==4.0',
        'dataclasses; python_version < "3.7"',
        'django>=2.2',  # TOM Toolkit requires db math functions
        'django-bootstrap4',
        'django-contrib-comments>=1.9.2',  # Earlier version are incompatible with Django >= 3.0
        'django-crispy-forms',
        'django-extensions',
        'django-filter',
        'django-gravatar2',
        'django-guardian',
        'djangorestframework',
        'fits2image',
        'matplotlib',
        'numpy',
        'pillow',
        'plotly',
        'python-dateutil',
        'requests',
        'specutils==0.7',
    ],
    extras_require={
        'test': ['factory_boy']
    },
    include_package_data=True,
)
