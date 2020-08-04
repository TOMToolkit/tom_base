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
        'beautifulsoup4==4.9.1',
        'django==3.0.7',  # TOM Toolkit requires db math functions
        'django-bootstrap4==1.1.1',
        'django-extensions==2.2.9',
        'django-filter==2.2.0',
        'django-contrib-comments==1.9.2',  # Earlier version are incompatible with Django >= 3.0
        'django-gravatar2==1.4.3',
        'django-crispy-forms==1.9.0',
        'django-guardian==2.2.0',
        'numpy==1.18.2',
        'python-dateutil==2.8.1',
        'requests==2.23.0',
        'astroquery==0.4',
        'astropy==4.0',
        'astroplan==0.6',
        'plotly==4.6.0',
        'pillow==7.1.0',
        'fits2image==0.4.3',
        'specutils==1.0',
        'dataclasses; python_version < "3.7"',
    ],
    extras_require={
        'test': ['factory_boy']
    },
    include_package_data=True,
)
