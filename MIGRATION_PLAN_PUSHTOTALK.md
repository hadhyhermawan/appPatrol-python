# Rencana Migrasi Push-to-Talk (Audio) ke Python: Menggunakan Socket.IO

Dokumen ini menjelaskan strategi teknis untuk memindahkan layanan Walkie Talkie Audio (`/var/www/PushToTalkServer`) dari Node.js WebSocket Murni ke **Python FastAPI dengan Socket.IO**.

**Keputusan Desain**: Menggunakan **Socket.IO** untuk menyatukan protokol dengan fitur lain (Video/Chat), menyederhanakan kode Client/Server, dan memanfaatkan fitur *Rooms* bawaan.

---

## 1. Analisis Perubahan (WS Murni -> Socket.IO)

*   **Protokol Lama**: WebSocket Murni (Binary Frame langsung).
*   **Protokol Baru**: Socket.IO Event-based (`emit('audio')`).
*   **Keuntungan**:
    *   Konsistensi library di Android (cukup maintain 1 lib socket).
    *   Manajemen Room otomatis (tidak perlu coding manual list connection).
    *   Auto-reconnect yang handal.

---

## 2. Persiapan Python

Menggunakan library `python-socketio` (sama dengan WebRTC Signaling).

```python
import socketio

# Gunakan AsyncServer agar non-blocking
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
```

---

## 3. Alur Komunikasi (Event-Driven)

### A. Namespace
Untuk memisahkan trafik PTT dengan fitur lain, kita bisa menggunakan **Namespace** khusus, misal `/ptt`. Atau gunakan default `/` jika traffic belum massive.

### B. Event Mapping

| Aksi | Event Name | Payload (Data) | Arah |
| :--- | :--- | :--- | :--- |
| **Login** | `connect` | `auth={token: '...'}` | Client -> Server |
| **Masuk Channel** | `join_channel` | `{ channel_id: '...' }` | Client -> Server |
| **Kirim Suara** | `voice_packet` | (Binary Audio Chunk) | Client -> Server |
| **Terima Suara** | `voice_packet` | (Binary Audio Chunk + sender info) | Server -> Client (Broadcast) |
| **Leave / Putus** | `disconnect` | - | Client -> Server |

---

## 4. Contoh Kode Implementasi (Python)

```python
# app/socket_ptt.py

@sio.event
async def connect(sid, environ, auth):
    # 1. Validasi Token (Database)
    token = auth.get('token')
    user = await validate_user_token(token)
    if not user:
        raise ConnectionRefusedError('Autentikasi Gagal')
    
    # Simpan session user
    await sio.save_session(sid, {'user': user})
    print(f"User {user.name} connected to PTT")

@sio.event
async def join_channel(sid, data):
    channel_id = data.get('channel_id')
    user = (await sio.get_session(sid))['user']

    # 2. Validasi Hak Akses Channel
    if not can_access_channel(user, channel_id):
        return {'status': 'error', 'msg': 'Akses Ditolak'}

    # 3. Masuk Room (Fitur Built-in Socket.IO)
    sio.enter_room(sid, channel_id)
    return {'status': 'ok', 'channel': channel_id}

@sio.event
async def voice_packet(sid, data):
    # 'data' adalah binary audio chunk (bytes)
    # Kita perlu tahu user ini sedang di channel mana
    # (Bisa disimpan di session saat join, atau dikirim client)
    
    session = await sio.get_session(sid)
    current_channel = session.get('current_channel')
    
    if current_channel:
        # 4. Broadcast ke semua orang di channel (kecuali pengirim)
        # Kirim balik raw binary atau wrap dalam object
        await sio.emit('voice_packet', data, room=current_channel, skip_sid=sid)

```

---

## 5. Perubahan di Android (Client)

1.  **Library**: Gunakan `socket.io-client-java`.
2.  **Inisialisasi**:
    ```java
    IO.Options options = new IO.Options();
    options.auth = Collections.singletonMap("token", userToken);
    Socket socket = IO.socket("https://api-v2.k3guard.com", options);
    socket.connect();
    ```
3.  **Sending Audio**:
    ```java
    // Saat mic.read() dapat buffer
    socket.emit("voice_packet", audioBuffer);
    ```

---

## 6. Kesimpulan

Menggunakan Socket.IO membuat kode backend jauh lebih bersih (`sio.enter_room`, `sio.emit`) dibandingkan mengelola `List<WebSocket>` secara manual. Overhead protokol Socket.IO dapat diterima untuk kemudahan pengembangan ini.
