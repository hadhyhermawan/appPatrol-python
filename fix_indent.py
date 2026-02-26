import re

with open("app/routers/laporan.py", "r") as f:
    text = f.read()

# I want to remove the wrong imports inserted by sed
text = text.replace("        import traceback; traceback.print_exc()\n", "")

with open("app/routers/laporan.py", "w") as f:
    f.write(text)
