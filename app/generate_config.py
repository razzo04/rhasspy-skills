
import os
from typing import Optional

from pydantic import BaseSettings

#    log_dest file /var/log/mosquitto.log

class Settings(BaseSettings):
    mqtt_password: Optional[str]
    mqtt_user: Optional[str]
    client_id: str = "bridge_skill"
    mqtt_host: str
    dest_file: str = "/etc/mosquitto/mosquitto.conf"

if __name__ == "__main__":
    settings = Settings()
    template = f'''
    protocol mqtt
    user root
    log_dest stdout
    log_type all
    persistence true
    persistence_location /data/

    auth_plugin /mosquitto/go-auth.so

    auth_opt_cache true
    auth_opt_auth_cache_seconds 30
    auth_opt_acl_cache_seconds 30
    auth_opt_backends http
    auth_opt_http_host 127.0.0.1
    auth_opt_http_port 9090
    auth_opt_http_getuser_uri /api/login
    auth_opt_http_superuser_uri /api/superuser
    auth_opt_http_aclcheck_uri /api/acl
    auth_opt_http_params_mode form

    allow_anonymous false

    listener 1883
    protocol mqtt

    connection bridge
    address {settings.mqtt_host}
    topic rhasspy/# both
    topic hermes/# both
    remote_username {settings.mqtt_user}
    remote_password {settings.mqtt_password}
    remote_clientid {settings.client_id}
    '''
    if os.path.isfile(settings.dest_file):
        print("confing already present removing...")
        os.remove(settings.dest_file)
    with open(settings.dest_file, "w") as f:
        f.write(template.strip())
    print("config saved")