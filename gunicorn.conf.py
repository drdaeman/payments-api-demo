# Gunicorn configuration file

import os

# Defaults
# Refer to http://docs.gunicorn.org/en/stable/settings.html for details
bind = ["0.0.0.0:8000"]
backlog = 2048
daemon = False
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Load from GUNICORN_* environment variables
for k, v in os.environ.items():
    if k.startswith("GUNICORN_"):
        key = k.split("_", 1)[1].lower()
        locals()[key] = v
