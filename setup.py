from setuptools import setup, find_packages
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='tomtoolkit',
    description='The TOM Toolkit and base modules',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://tomtoolkit.github.io',
    author='TOM Toolkit Project',
    author_email='dcollom@lco.global',
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
    use_scm_version=True,
    setup_requires=['setuptools_scm', 'wheel'],
    install_requires=[
        'astroquery==0.4.1',
        'astroplan==0.6',
        'astropy==4.0.1.post1',
        'beautifulsoup4==4.9.1',
        'dataclasses; python_version < "3.7"',
        'django==3.1.0',  # TOM Toolkit requires db math functions
        'djangorestframework==3.11.1',
        'django-bootstrap4==2.2.0',
        'django-contrib-comments==1.9.2',  # Earlier version are incompatible with Django >= 3.0
        'django-crispy-forms==1.9.2',
        'django-extensions==3.0.5',
        'django-gravatar2==1.4.4',
        'django-filter==2.3.0',
        'django-guardian==2.3.0',
        'fits2image==0.4.3',
        'Markdown==3.2.2',  # django-rest-framework doc headers require this to support Markdown
        'numpy==1.19.1',
        'pillow==7.2.0',
        'plotly==4.9.0',
        'python-dateutil==2.8.1',
        'requests==2.24.0',
        'specutils==1.0',
    ],
    extras_require={
        'test': ['factory_boy==3.0.1']
    },
    include_package_data=True,
)
