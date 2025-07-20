#!/bin/bash

# 1. Activate virtual environment
source venv/bin/activate

# 2. Start Flask app in background
echo "Starting Flask backend..."
FLASK_APP=backend/app.py flask run --host=0.0.0.0 --port=5000 &

# 3. Wait a moment for Flask to launch
sleep 2

# 4. Start ngrok
echo "Starting ngrok tunnel..."
ngrok http 5000
