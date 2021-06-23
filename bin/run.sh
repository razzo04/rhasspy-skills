set -e
groupadd -r docker -g $(stat -c '%g' "/var/run/docker.sock")
usermod -a -G docker rhasspy-skills
python3 app/generate_config.py
gosu rhasspy-skills uvicorn app.main:app --port 9090 --host 0.0.0.0 & gosu mosquitto:mosquitto mosquitto -c /etc/mosquitto/mosquitto.conf