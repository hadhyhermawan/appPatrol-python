"""
FCM V1 Push Notification Service
==================================
Mengirim push notification ke device Android melalui Firebase Cloud Messaging (FCM) v1 API.
Menggunakan Service Account credentials (serviceAccountKey.json).
Menggunakan JWT manual + requests dengan IPv4 force (seperti PHP Laravel FcmV1Service).
"""

import os
import json
import time
import logging
import socket
import requests

logger = logging.getLogger(__name__)

# ─── Force IPv4 untuk semua requests (workaround IPv6 timeout di server) ───
_orig_getaddrinfo = socket.getaddrinfo

def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _ipv4_getaddrinfo
# ───────────────────────────────────────────────────────────────────────────

# Path ke service account key
SERVICE_ACCOUNT_PATH = "/var/www/appPatrol-python/serviceAccountKey.json"

# Cache token
_cached_token: str = ""
_token_expiry: float = 0.0


def _load_service_account() -> dict:
    with open(SERVICE_ACCOUNT_PATH) as f:
        return json.load(f)


def _get_access_token() -> str:
    """Ambil OAuth2 access token menggunakan JWT + Google Token endpoint (cached 55 menit)."""
    global _cached_token, _token_expiry

    now = time.time()
    if _cached_token and now < _token_expiry:
        return _cached_token

    import base64
    import json
    import hmac
    import hashlib

    try:
        sa = _load_service_account()

        # Build JWT
        header = {"alg": "RS256", "typ": "JWT"}
        now_ts = int(time.time())
        payload = {
            "iss": sa["client_email"],
            "scope": "https://www.googleapis.com/auth/firebase.messaging",
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now_ts,
            "exp": now_ts + 3600,
        }

        def b64(data: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b'=').decode()

        signing_input = f"{b64(header)}.{b64(payload)}"

        # Sign dengan private key menggunakan cryptography
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        private_key = serialization.load_pem_private_key(
            sa["private_key"].encode(), password=None
        )
        signature = private_key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
        jwt_token = f"{signing_input}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"

        # Exchange JWT untuk access token
        resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            },
            timeout=10,
        )

        if resp.status_code != 200:
            raise Exception(f"Token exchange failed: {resp.status_code} {resp.text[:200]}")

        token_data = resp.json()
        _cached_token = token_data["access_token"]
        _token_expiry = now + 3300  # Cache 55 menit

        logger.info("[FCM] ✅ Access token berhasil di-refresh via JWT")
        return _cached_token

    except Exception as e:
        logger.error(f"[FCM] ❌ Gagal ambil access token: {e}")
        raise


def send_chat_notification(
    target_niks: list,
    sender_nama: str,
    message_text: str,
    room: str,
    db_session=None
) -> list:
    """
    Kirim push notification chat ke semua device dari daftar NIK.
    """
    if not target_niks or not db_session:
        return []

    try:
        from sqlalchemy import text as sa_text

        # Handle single NIK (SQLAlchemy IN requires tuple with >1 elements or use different approach)
        if len(target_niks) == 1:
            result = db_session.execute(
                sa_text("SELECT fcm_token FROM karyawan_devices WHERE nik = :nik AND fcm_token IS NOT NULL AND fcm_token != ''"),
                {"nik": target_niks[0]}
            ).fetchall()
        else:
            result = db_session.execute(
                sa_text("SELECT fcm_token FROM karyawan_devices WHERE nik IN :niks AND fcm_token IS NOT NULL AND fcm_token != ''"),
                {"niks": tuple(target_niks)}
            ).fetchall()

        tokens = list({row[0] for row in result if row[0]})  # unique tokens

        if not tokens:
            logger.info(f"[FCM CHAT] Tidak ada FCM token untuk NIKs: {target_niks}")
            print(f"[FCM CHAT] Tidak ada FCM token untuk NIKs: {target_niks}")
            return []

        print(f"[FCM CHAT] Mengirim ke {len(tokens)} token | room={room}")
        logger.info(f"[FCM CHAT] Mengirim ke {len(tokens)} token | room={room} | pengirim={sender_nama}")

        return _send_to_tokens(tokens, {
            "type": "chat",
            "title": sender_nama,
            "body": message_text,
            "room": room,
        })

    except Exception as e:
        logger.error(f"[FCM CHAT] Error saat kirim notifikasi: {e}")
        print(f"[FCM CHAT] Error saat kirim notifikasi: {e}")
        return []


def _send_to_tokens(tokens: list, data: dict) -> list:
    """Kirim data-only push notification ke list token via FCM v1 API."""
    try:
        access_token = _get_access_token()
        sa = _load_service_account()
        project_id = sa["project_id"]
        url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        responses = []
        for token in tokens:
            payload = {
                "message": {
                    "token": token,
                    "data": {k: str(v) for k, v in data.items()},
                    "android": {
                        "priority": "high"
                    }
                }
            }

            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=10)
                if resp.status_code == 200:
                    logger.info(f"[FCM] ✅ Terkirim ke token: {token[:30]}...")
                    print(f"[FCM] ✅ Terkirim ke token: {token[:30]}...")
                else:
                    logger.warning(f"[FCM] ⚠️ Gagal ke token {token[:30]}... | status={resp.status_code} | {resp.text[:200]}")
                    print(f"[FCM] ⚠️ Gagal | status={resp.status_code} | {resp.text[:300]}")
                responses.append({"token": token[:30], "status": resp.status_code})
            except Exception as e:
                logger.error(f"[FCM] ❌ Error kirim ke token {token[:30]}: {e}")
                print(f"[FCM] ❌ Error: {e}")
                responses.append({"token": token[:30], "status": "error", "error": str(e)})

        return responses

    except Exception as e:
        logger.error(f"[FCM] _send_to_tokens error: {e}")
        print(f"[FCM] _send_to_tokens error: {e}")
        return []
