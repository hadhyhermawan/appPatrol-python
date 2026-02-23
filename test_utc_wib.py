from datetime import datetime
import pytz

# simulasi payload insert data absensi 
print(datetime.now().strftime("Server local time: %Y-%m-%d %H:%M:%S"))
print(datetime.utcnow().strftime("Server UTC time:   %Y-%m-%d %H:%M:%S"))
print(datetime.now(pytz.timezone('Asia/Jakarta')).strftime("Jakarta time:     %Y-%m-%d %H:%M:%S"))
