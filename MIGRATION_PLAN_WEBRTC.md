# Rencana Migrasi WebRTC Signaling: Node.js ke Python FastAPI

Dokumen ini merinci langkah teknis untuk memindahkan layanan Signaling Server (`/var/www/walkieWebRTC`) yang saat ini berbasis Node.js + Socket.IO ke dalam backend Python FastAPI (`/var/www/appPatrol-python`).

## 1. Analisis Layanan Lama (Node.js)

File sumber: `/var/www/walkieWebRTC/server.js`
Port Lama: 3005
Teknologi: `socket.io` (v4), `express`.

**Event yang Ditangani:**
1.  **`connection`**: Client terhubung.
2.  **`join_room`**: User masuk room, broadcast ke peer lain, terima list peer yang sudah ada.
3.  **`signal`**: Meneruskan data signaling WebRTC (SDP offer/answer, ICE candidates) antar peer secara privat.
4.  **`disconnect`**: Membersihkan data client dan memberitahu room.

---

## 2. Persiapan Python

Kita perlu menginstal library `python-socketio` yang kompatibel dengan protokol Socket.IO standar. Library ini bekerja secara *asynchronous* (ASGI) sangat cocok dengan FastAPI.

**Dependency:**
```text
python-socketio
```

---

## 3. Implementasi Kode (Python)

Kita akan membuat file baru `app/socket_io.py` (atau `socket_events.py`) untuk memisahkan logika WebSocket dari logika HTTP API biasa.

### A. Inisialisasi Server
Menggunakan `AsyncServer` agar tidak memblokir thread utama FastAPI.

```python
import socketio

# CORs allowed origins * pentign agar Android/Web bisa connect
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
```

### B. Struktur Data (State)
Menyimpan state user secara *in-memory* (sama seperti Node.js saat ini).

```python
# Mapping: sid -> { 'room': str, 'role': str, 'userId': str }
clients = {} 
```

### C. Migrasi Event (Node.js vs Python)

| Event | Node.js Logic | Python Logic |
| :--- | :--- | :--- |
| **Join Room** | `socket.join(room)` | `await sio.enter_room(sid, room)` |
| **Broadcast** | `socket.to(room).emit(...)` | `await sio.emit(..., room=room, skip_sid=sid)` |
| **Direct Msg** | `io.to(targetId).emit(...)` | `await sio.emit(..., to=targetId)` |
| **Disconnect**| `delete clients[socket.id]` | `del clients[sid]` |

---

## 4. Langkah Integrasi ke FastAPI

File `app/main.py` akan dimodifikasi untuk menampung HTTP (FastAPI) dan WebSocket (Socket.IO) dalam satu port (8000).

```python
# app/main.py

from fastapi import FastAPI
from .socket_io import sio # Import objek sio yang sudah dibuat
import socketio

app = FastAPI()

# ... include routers ...

# Mount Socket.IO app
# Ini akan menangani path /socket.io/ secara otomatis
app_with_socket = socketio.ASGIApp(sio, app)

# Note: Saat menjalankan uvicorn, yang dijalankan adalah 'app_with_socket', bukan 'app'
# Atau gunakan mount specific path jika ingin mempertahankan object 'app' sebagai entry utama
```

---

## 5. Perubahan di Sisi Klien (Android / Web)

Setelah migrasi selesai, klien hanya perlu mengubah URL koneksi Socket.IO.

*   **URL Lama**: `http://k3guard.com:3005` (Node.js)
*   **URL Baru**: `https://api-v2.k3guard.com` (Python FastAPI Port 8000)
*   **Path**: Default Socket.IO path adalah `/socket.io/`, ini tetap sama.

---

## 6. Contoh Kode Implementasi (Preview)

Berikut adalah *snippet* kode Python yang akan kita buat:

```python
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def join_room(sid, data):
    # data: {'room': '...', 'role': '...', 'userId': '...'}
    room = data.get('room')
    role = data.get('role')
    user_id = data.get('userId')
    
    # Simpan state
    clients[sid] = {'room': room, 'role': role, 'userId': user_id}
    await sio.enter_room(sid, room)
    
    # Beritahu user lain di room
    await sio.emit('new_peer', {'peerId': sid, 'role': role, 'userId': user_id}, room=room, skip_sid=sid)
    
    # Kirim list user yang online ke user baru (Opsional, Nodejs melakukannya)
    # ... logic here ...

@sio.event
async def signal(sid, data):
    target_id = data.get('targetId')
    payload = data.get('signal')
    # Forward signal
    await sio.emit('signal', {'fromId': sid, 'signal': payload}, to=target_id)

@sio.event
async def disconnect(sid):
    if sid in clients:
        client_data = clients[sid]
        room = client_data.get('room')
        # Beritahu room
        await sio.emit('peer_disconnected', {'peerId': sid}, room=room)
        del clients[sid]
```

## 7. Kesimpulan

Migrasi ini **Low Risk** karena logika bisnisnya sederhana (hanya meneruskan pesan/signaling). Keuntungannya adalah mengurangi beban maintenance server (Node.js tidak perlu lagi), dan seluruh backend terpusat di Python.
