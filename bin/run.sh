if [[ ! -S "/var/run/docker.sock" ]];
then
    echo "/var/run/docker.sock must be mapped"
    exit 1
fi
set -e
groupadd -r docker -g $(stat -c '%g' "/var/run/docker.sock")
usermod -a -G docker rhasspy-skills
if [ "$(stat -c '%u' "/data")" == "0" ];
then
    chown -R rhasspy-skills:rhasspy-skills /data
fi
if [ "$(stat -c '%U' "/data")" != "rhasspy-skills" ];
then
    groupadd -r data -g $(stat -c '%g' "/data")
    usermod -a -G data rhasspy-skills
    chmod -R g+rw data
fi
python3 bin/setup_network.py
python3 bin/generate_config.py

gosu rhasspy-skills uvicorn app.main:app --port 9090 --host 0.0.0.0 & 
gosu mosquitto:mosquitto mosquitto -c /etc/mosquitto/mosquitto.conf &
sleep 5
python3 -m app.start_skills
wait