#!/bin/bash
# Azure Web App Startup Script for Unified Service Bus WebSocket Relay

# Set Python path
export PYTHONPATH=/home/site/wwwroot/src:$PYTHONPATH

# Start the unified relay with gunicorn
cd /home/site/wwwroot
gunicorn -k uvicorn.workers.UvicornWorker common_adapters.relay.unified_relay:app \
    --bind 0.0.0.0:${PORT:-8000} \
    --timeout 120 \
    --workers 1 \
    --access-logfile - \
    --error-logfile -
