import requests

try:
    r = requests.get('http://localhost:8000/api/laporan/rekap-presensi?start_date=2026-02-01&end_date=2026-02-27&search=WIRAWAN')
    print(r.status_code)
    print(r.text)
except Exception as e:
    print(e)
