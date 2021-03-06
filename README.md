# Rhasspy skills

This is a skills management solution for rhasspy that isolates every skill inside a docker container and manages access through MQTT ACL.

# Getting Started
First you need to run the container and change the env variable accordingly. 
```bash
docker run -d -p 9090:9090 \
-e MQTT_HOST="192.168.1.2:1883" \
-e MQTT_PASSWORD=mqttbrokerpassword \
-e MQTT_USER=mqttuser \
-e RHASSPY_URL="http://192.168.1.2:12101/api/" \
-v /var/run/docker.sock:/var/run/docker.sock \
-v "$HOME/.config/rhasspyskills/data:/data" razzo04/rhasspyskills
```
Once the container starts, the endpoint documentation should be accessible at http://localhost:9090/docs. It can be used to install new skills, but you can also use [rhasspy-skills-cli](https://github.com/razzo04/rhasspy-skills-cli). A skill is just a tar archive which contains a manifest.json that include information about the skill, a dockerfile, a sentences.ini and other file need by the skill. Skill examples can be found in the [examples](https://github.com/razzo04/rhasspy-skills-examples) repository. To install a new skill you can follow the guide on [here](https://github.com/razzo04/rhasspy-skills-cli#install-new-skill).

Once the skill is installed rhasspy should be retrained with the new sentences.

This is very experimental so you will find a lot of bugs and some futures are not implemented yet. If you want to report a bug or you have a question you can open an issue or go to [rhasspy community](https://community.rhasspy.org/t/rhasspy-skills-and-mqtt-acl).
