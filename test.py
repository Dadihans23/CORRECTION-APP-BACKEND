# delete_chat_tables.py
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("DROP TABLE IF EXISTS treatment_chatsession")
    cursor.execute("DROP TABLE IF EXISTS treatment_chatmessage")

print("Tables supprimées !")