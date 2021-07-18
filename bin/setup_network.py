from typing import List
import docker as dc
from docker.models.containers import Container
from docker.models.networks import Network
from socket import gethostname

docker = dc.from_env()

networks: List[Network] = docker.networks.list(
    names=["mqtt-net"], greedy=True
)
self_container: Container = docker.containers.get(gethostname())
if len(networks) == 0:
    print("Creating network")
    # TODO set static ip
    network: Network = docker.networks.create(
        "mqtt-net", driver="bridge", check_duplicate=True, internal=True
    )
    network.connect(self_container, aliases=["mqtt.server"])
else:
    is_connected = False
    for net in networks:
        for container in net.containers:
            if container.id == self_container.id:
                is_connected = True
                break
        if is_connected:
            break
    if not is_connected:
        print("Connecting container")
        networks[0].connect(self_container, aliases=["mqtt.server"])