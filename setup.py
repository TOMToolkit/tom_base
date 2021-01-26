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
        'astroplan==0.8',
        'astropy==4.1',
        'beautifulsoup4==4.9.3',
        'dataclasses; python_version < "3.7"',
        'django==3.1.5',  # TOM Toolkit requires db math functions
        'djangorestframework==3.12.2',
        'django-bootstrap4==2.3.1',
        'django-contrib-comments==2.0.0',  # Earlier version are incompatible with Django >= 3.0
        'django-crispy-forms==1.10.0',
        'django-extensions==3.1.0',
        'django-gravatar2==1.4.4',
        'django-filter==2.4.0',
        'django-guardian==2.3.0',
        'fits2image==0.4.3',
        'Markdown==3.3.3',  # django-rest-framework doc headers require this to support Markdown
        'numpy==1.19.5',
        'pillow==8.1.0',
        'plotly==4.14.3',
        'python-dateutil==2.8.1',
        'requests==2.25.1',
        'specutils==1.1.1',
    ],
    extras_require={
        'test': ['factory_boy==3.2.0']
    },
    include_package_data=True,
)
