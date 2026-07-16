#!/bin/bash
# Start the Sigtap application using Gunicorn and uv
# We bind to 127.0.0.1 since we expect a reverse proxy (Caddy) to handle external traffic.
# -w 4 sets 4 worker processes.
uv run gunicorn -w 4 -b 127.0.0.1:5000 app:app
