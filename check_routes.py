from app.main import app_fastapi as app

print("Checking ALL routes for /api/android...")
for route in app.routes:
    if hasattr(route, "path") and "/api/android" in route.path:
        print(f"Found route: {route.path} [{route.methods}]")
    if hasattr(route, "path") and "tamu" in route.path:
        print(f"Found route: {route.path} [{route.methods}]")
