# setup.py

from setuptools import setup, find_packages

setup(
    name='new_face_connection',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'Pillow',
        'spotipy',
        'pyscard',
        'firebase-admin',
        'psutil',
        'tk',
    ],
    entry_points={
        'console_scripts': [
            'new-face-connection = app.main:main',
        ],
    },
)
