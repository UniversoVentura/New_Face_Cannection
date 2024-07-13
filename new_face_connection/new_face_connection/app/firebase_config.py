# app/firebase_config.py

import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate('path/to/your/serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()
