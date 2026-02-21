import socketio
from jose import jwt, JWTError
from app.routers.auth_legacy import SECRET_KEY, ALGORITHM, validate_sanctum_token
from app.database import SessionLocal
from urllib.parse import parse_qs

# Create Socket.IO Server (Async implementation for ASGI)
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True
)

# State Management (In-Memory)
# clients[sid] = { 
#    'userId': str, 
#    'role': str, 
#    'webrtc_room': str,      # Current WebRTC Signalling Room
#    'walkie_channel': str    # Current Walkie Talkie Channel
# }
clients = {}

@sio.event
async def connect(sid, environ, auth):
    """
    Handle connection event.
    Validate jwt token.
    """
    token = None
    
    # 1. Check Auth payload
    if auth:
        token = auth.get('token')
        
    # 2. Check Query String
    if not token:
        query_string = environ.get('query_string', b'').decode('utf-8')
        params = parse_qs(query_string)
        if 'token' in params:
            token = params['token'][0]

    if not token:
        print(f"Socket Connect Rejected: No Token (SID: {sid})")
        return False

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        print(f"Socket Connected: User {user_id} (SID: {sid})")
        
        await sio.save_session(sid, {'user_id': user_id})
        
        # Init Client State
        clients[sid] = {
            'userId': user_id,
            'role': None,
            'webrtc_room': None,
            'walkie_channel': None
        }
        
    except JWTError:
        # Fallback: Try Sanctum Token (Legacy Android)
        print(f"Socket: JWT Decode failed for SID {sid}. Trying Sanctum...")
        db = SessionLocal()
        try:
            sanctum_user_id = validate_sanctum_token(db, token)
            if sanctum_user_id:
                user_id = str(sanctum_user_id)
                print(f"Socket Connected (Sanctum): User {user_id} (SID: {sid})")
                
                await sio.save_session(sid, {'user_id': user_id})
                
                clients[sid] = {
                    'userId': user_id,
                    'role': None,
                    'webrtc_room': None,
                    'walkie_channel': None
                }
                return True
        except Exception as e:
            print(f"Socket Sanctum Error: {e}")
        finally:
            db.close()

        print(f"Socket Connect Rejected: Invalid Token (SID: {sid})")
        return False

# --- Helper: Push Online Users (WebRTC) ---
async def push_online_users(room):
    online_users = []
    for c_sid, c_data in clients.items():
        if c_data.get('webrtc_room') == room:
            online_users.append({'userId': c_data.get('userId'), 'role': c_data.get('role')})
    
    await sio.emit('room_status', {'members': online_users}, room=room)

# --- WebRTC Signaling Events ---

@sio.event
async def join_room(sid, data):
    # data: { room, role, userId }
    room = data.get('room')
    role = data.get('role')
    user_id = data.get('userId') # Override userId from data? Or use token userId? Data for now.
    
    # 1. Join Room & Save State
    await sio.enter_room(sid, room)
    
    if sid in clients:
        clients[sid]['webrtc_room'] = room
        clients[sid]['role'] = role
        clients[sid]['userId'] = user_id # Sync with payload
    
    print(f"[WebRTC] {role} {user_id} joined room {room} (SID: {sid})")
    
    # 2. Broadcast 'new_peer'
    await sio.emit('new_peer', 
                   {'peerId': sid, 'role': role, 'userId': user_id}, 
                   room=room, 
                   skip_sid=sid)
                   
    # 3. Send Existing Peers List
    for c_sid, c_data in clients.items():
        if c_data.get('webrtc_room') == room and c_sid != sid:
            peer_payload = {
                'peerId': c_sid,
                'role': c_data.get('role'),
                'userId': c_data.get('userId')
            }
            await sio.emit('new_peer', peer_payload, to=sid)
            
    # 4. Push Updated Online Users
    await push_online_users(room)

@sio.event
async def signal(sid, data):
    # data: { targetId, signal }
    target_id = data.get('targetId')
    payload = data.get('signal')
    
    # Forward Signal P2P
    await sio.emit('signal', 
                   {'fromId': sid, 'signal': payload}, 
                   to=target_id)


# --- Walkie Talkie Events ---

@sio.event
async def join_channel(sid, data):
    # data: {'channel': 'CODE'}
    channel = data.get('channel')
    if not channel:
        return
        
    # Leave previous channel logic?
    prev_channel = clients[sid].get('walkie_channel')
    if prev_channel:
        await sio.leave_room(sid, prev_channel)
        
    await sio.enter_room(sid, channel)
    clients[sid]['walkie_channel'] = channel
    
    user_id = clients[sid].get('userId')
    print(f"[Walkie] User {user_id} joined channel {channel}")

@sio.event
async def voice_stream(sid, data):
    # data: Binary bytes
    c_data = clients.get(sid)
    if not c_data: return
    
    channel = c_data.get('walkie_channel')
    if channel:
        # Broadcast audio to channel, skip sender
        await sio.emit('voice_stream', data, room=channel, skip_sid=sid)
        
@sio.event
async def leave_channel(sid):
    c_data = clients.get(sid)
    if c_data and c_data.get('walkie_channel'):
        channel = c_data['walkie_channel']
        await sio.leave_room(sid, channel)
        c_data['walkie_channel'] = None
        print(f"[Walkie] User {c_data.get('userId')} left channel {channel}")


@sio.event
async def disconnect(sid):
    print(f"Socket Disconnected: {sid}")
    
    if sid in clients:
        c_data = clients[sid]
        
        # Cleanup WebRTC
        webrtc_room = c_data.get('webrtc_room')
        if webrtc_room:
            print(f"[WebRTC] Disconnect from {webrtc_room}")
            await sio.emit('peer_disconnected', {'peerId': sid}, room=webrtc_room)
            # Push Update
            # await push_online_users(webrtc_room) # Can't push here if client deleted?
            # Need to push AFTER delete? No, push needs to filter clients.
        
        # Cleanup State
        channel = c_data.get('walkie_channel')
        # ... logic if needed
        
        del clients[sid]
        
        if webrtc_room:
             await push_online_users(webrtc_room)

# --- Test Event ---
@sio.on('ping_test')
async def on_ping_test(sid, data):
    print(f"Ping received from {sid}: {data}")
    await sio.emit('pong_test', {'message': 'Hello from Python Socket.IO!'}, room=sid)

# --- Future: WebRTC Signaling & PTT Logic will be added here ---
