
import firebase_admin
from firebase_admin import credentials, messaging

cred = credentials.Certificate("/var/www/appPatrol-python/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

token = "ewMreodqp4" # Token lama (2026-02-18)

try:
    msg = messaging.Message(
        data={
            "type": "video_call_offer",
            "room": "TEST_ROOM_123",
            "caller_name": "TEST_CALLER",
        },
        token=token # Note: using full token here if variable was holding just suffix, but I will assume its just suffix for display
        # Wait, the token in log was just last 10 chars. I need full token.
    )
    # I cannot send because I dont have full token.
    print("Cannot send test without full token.")
except Exception as e:
    print(e)

