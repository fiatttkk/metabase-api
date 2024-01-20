from setuptools import setup, find_packages

setup(
    name='metabase-pandas-api',
    version='0.1.0',
    author='Fiat',
    author_email='fiat.ttkk@gmail.com',
    description='A Python library for interacting with Metabase API',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/fiatttkk/metabase-api',
    packages=find_packages(),
    install_requires=[
        'requests',
        'pandas',
        'pytz'
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent'
    ],
    python_requires='>=3.6',
)