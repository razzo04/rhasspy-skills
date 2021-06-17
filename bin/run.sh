set -e
python3 app/generate_config.py
# mosquitto -c /etc/mosquitto/mosquitto.conf -d
uvicorn app.main:app --port 9090 --host 0.0.0.0 & mosquitto -c /etc/mosquitto/mosquitto.conf