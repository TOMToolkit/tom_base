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
        'astroquery>=0.4.2',
        'astroplan==0.8',
        'astropy==4.2.1',
        'beautifulsoup4~=4.9',
        'django~=3.1',  # TOM Toolkit requires db math functions
        'djangorestframework~=3.12',
        'django-bootstrap4~=3.0',
        'django-contrib-comments~=2.0',  # Earlier version are incompatible with Django >= 3.0
        'django-crispy-forms~=1.11',
        'django-extensions~=3.1',
        'django-filter~=2.4',
        'django-gravatar2~=1.4',
        'django-guardian~=2.3',
        'fits2image==0.4.4',
        'Markdown==3.3.4',  # django-rest-framework doc headers require this to support Markdown
        'numpy~=1.20',
        'pillow==8.3.2',
        'plotly~=5.0',
        'python-dateutil~=2.8',
        'requests~=2.25',
        'specutils==1.4.0',
    ],
    extras_require={
        'test': ['factory_boy==3.2.0'],
        'docs': [
            'recommonmark~=0.7',
            'sphinx~=4.0',
            'tom_antares',
            'tom_scimma'
        ]
    },
    include_package_data=True,
)
