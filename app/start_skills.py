import docker as dc
import os
import json
from .models import DBFile
from .dependencies import get_container_by_skill_name
docker = dc.from_env()

config = DBFile.parse_file(os.path.join(os.environ.get("store_directory".upper(), "/data"),  "store.json"))

for skill in config.skills:
    if skill.start_on_boot:
        container = get_container_by_skill_name(docker, skill.skill_name)
        #TODO create container if not present  
        if not container:
            print(f"Skill {skill.skill_name} has not a container")
            continue
        if container.status != "running":
            try:
                container.start()
            except Exception:
                print(f"failed to start container {container.id} of skill {skill.skill_name}")
