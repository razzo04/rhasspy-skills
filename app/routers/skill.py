import os
import shutil
import tarfile
from socket import gethostname
from typing import Callable, List, Union
from urllib.parse import urljoin

import httpx
from starlette.responses import JSONResponse
from app.models import SkillModel
from docker.client import DockerClient
from docker.models.containers import Container
from docker.models.images import Image
from docker.models.networks import Network
from fastapi import (APIRouter, File, HTTPException, Response, UploadFile,
                     status, Request)
from fastapi.datastructures import UploadFile
from fastapi.param_functions import Depends
from fastapi.responses import UJSONResponse
from pydantic import ValidationError
from rhasspy_skills_cli.manifest import Manifest
from fastapi.routing import APIRoute

from .exceptions import SkillInstallException

from ..config import settings
from ..database import DB
from ..dependencies import (create_skill, get_db, get_docker, get_skills_dir,
                            get_temp_directory)


class APIRouteExceptionHandling(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()
        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except SkillInstallException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail":exc.detail,"error_code":exc.error_code})
        return custom_route_handler

skill_router = APIRouter(
    route_class=APIRouteExceptionHandling,
    tags=["skill"],
    responses={
        404: {"detail": "Skill not found"},
    },
)


@skill_router.get("/skills")
def get_skills(db: DB = Depends(get_db)):
    return db.get_skills()


def get_skill(name: str, db: DB = Depends(get_db)) -> Union[SkillModel, None]:
    return db.get_skill(name)

@skill_router.post("/skills", responses={400: {"detail":"file is required"}})
async def install_skill(
    file: UploadFile = File(None),
    force: bool = False,
    db: DB = Depends(get_db),
    docker: DockerClient = Depends(get_docker),
):
    if file is None:
        raise SkillInstallException(status.HTTP_400_BAD_REQUEST, detail="file is required", error_code="file_required")
    file_path = os.path.join(get_temp_directory(), file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    try:
        tar = tarfile.open(file_path, "r")

    except tarfile.ReadError:
        os.remove(file_path)
        raise SkillInstallException(400, detail="archive is in a invalid format", error_code="invalid_archive")
    if not "manifest.json" in tar.getnames():
        tar.close()
        os.remove(file_path)
        raise SkillInstallException(400, detail="the archive do not contain a manifest.json", error_code="manifest_not_present")
    manifest_tar = tar.extractfile("manifest.json")
    try:
        manifest = Manifest.parse_raw(manifest_tar.read())
    except ValidationError as e:
        tar.close()
        os.remove(file_path)
        raise SkillInstallException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.errors(), error_code="invalid_manifest")
    skill_path = os.path.join(get_skills_dir(), manifest.slug)
    try:
        is_dockerFile = not "Dockerfile" in tar.getnames()
        print(f"{not manifest.image} and {is_dockerFile}")
        if not manifest.image and not ("Dockerfile" in tar.getnames()):
            raise SkillInstallException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="no dockerfile and image detected",
                error_code="image_not_present"
            )
        # TODO add multi language support
        if not "sentences.ini" in tar.getnames():
            raise SkillInstallException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="the archive do not contain a sentences.ini",
                error_code="sentences_not_present"
            )
        try:
            os.mkdir(skill_path)
        except FileExistsError:
            if force:
                shutil.rmtree(skill_path)
            else:
                raise SkillInstallException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="skill with the same name already exist",
                    error_code="skill_already_installed"
                )
        try:
            tar.extractall(skill_path)
        finally:
            tar.close()
            os.remove(file_path)
        data_skill_path = os.path.join(skill_path, "data")
        os.mkdir(data_skill_path)
        config_skill_path = os.path.join(skill_path, "config.json")
        if os.path.isfile(config_skill_path):
            shutil.copy(config_skill_path,os.path.join(data_skill_path,"config.json"))
        tag = "skill_" + manifest.slug
        containers: List[Container] = docker.containers.list(all=True)
        for container in containers:
            if tag == container.name:
                if force:
                    container.remove(force=True)
                else:    
                    raise SkillInstallException(
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"The container name {tag} is already in use by another container {container.id}",
                        error_code="container_name_already_used"
                    )
        try:
            image = docker.images.build(path=skill_path, tag=tag)
        except Exception as e:
            raise SkillInstallException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"failed to build image. Error: {str(e)}",
                error_code="build_image"
            )

        try:
            # TODO separate in another file
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
            is_connected = False
            for net in networks:
                for container in net.containers:
                    if container.id == self_container.id:
                        is_connected = True
                        break
            if not is_connected:
                print("Connecting container")
                networks[0].connect(self_container, aliases=["mqtt.server"])
            mounts = docker.api.inspect_container(self_container.id)["Mounts"]
            path_host = None
            for mount in mounts:
                if mount["Destination"] == "/data":
                    path_host = mount["Source"]
            
            bind_path = os.path.join(os.path.abspath(os.path.join(path_host, os.pardir)), data_skill_path.replace("/","",1)) if path_host else None
            container: Container = docker.containers.run(
                tag,
                environment={
                    "MQTT_PASS": create_skill(db, manifest.slug, manifest.topic_access),
                    "MQTT_USER": manifest.slug,
                },
                network="mqtt-net",
                detach=True,
                name=tag,
                labels={"skill_name": manifest.slug},
                volumes={bind_path: {'bind': '/data', 'mode': 'rw'}}
            )
            if manifest.internet_access:
                net_bridge : Network = docker.networks.list(names=["bridge"])[0]
                net_bridge.connect(container)
        except Exception as e:
            raise SkillInstallException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e), error_code="container_creation")
    except SkillInstallException as e:
        print("Error cleaning up installation...")
        tar.close()
        if os.path.isfile(file_path):
            os.remove(file_path)
        if e.error_code != "skill_already_installed" and os.path.isdir(skill_path):
            db.remove_skill(manifest.slug)
            shutil.rmtree(skill_path)
        raise

    if manifest.auto_train:
        # TODO add multi language support
        sentences_file = os.path.join(skill_path, "sentences.ini")
        async with httpx.AsyncClient() as client:
            try:
                res = await client.post(
                    urljoin(settings.rhasspy_url, "sentences"),
                    headers=httpx.Headers(
                        {"Content-Type": "application/json"}
                    ),
                    json={
                        f"intents/skills/{manifest.slug}/sentences.ini": open(sentences_file, "r").read()
                    },
                )
            except Exception:
                raise HTTPException(
                    status.HTTP_424_FAILED_DEPENDENCY,
                    detail="unable to comunicate with rhasspy",
                )
            if res.status_code != 200:
                print(res.text)
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"status_code": res.status_code, "response": res.text},
                )
            # train and restart rhasspy
            await client.post(urljoin(settings.rhasspy_url, "train"))
            await client.post(urljoin(settings.rhasspy_url, "restart"))
    return {"state":"success", "detail": f"installed {manifest.name} in {skill_path}"}


@skill_router.delete("/skills/{skill_name}")
async def delete_skill(skill_name: str, force: bool = False, db: DB = Depends(get_db), docker: DockerClient = Depends(get_docker)):
    skill = db.get_skill(skill_name)
    if not skill:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="skill not found")
    containers: List[Container] = docker.containers.list(all=True,filters={"label":f"skill_name={skill_name}"})
    if len(containers) != 0:
        container = containers[0]
        if not force:
            container.stop()
        container.remove(v=True, force=force)
    else:
        print(f"No container found for {skill_name}")
    #TODO add support for remote docker image
    tag = "skill_" + skill_name
    docker.images.remove(tag,force=force)
    shutil.rmtree(os.path.join(get_skills_dir(), skill_name))
    db.remove_skill(skill_name)
    async with httpx.AsyncClient() as client:
        await client.post(
            urljoin(settings.rhasspy_url, "sentences"),
            headers=httpx.Headers(
                {"Content-Type": "application/json"}
            ),
            json={f"intents/skills/{skill_name}/sentences.ini": ""},
        )
        await client.post(urljoin(settings.rhasspy_url, "train"))
        await client.post(urljoin(settings.rhasspy_url, "restart"))
    return {"state":"success", "detail": f"uninstalled {skill_name}"}


@skill_router.get(
    "/skills/{skill_name}",
    response_model=SkillModel,
    responses={404: {"message": "skill not found"}},
)
def get_skill_by_name(
    skill_name: str, response: Response, db: DB = Depends(get_db)
) -> Union[SkillModel, None]:
    skill = db.get_skill(skill_name)
    print(skill)
    if skill:
        return skill
    else:
        response.status_code = status.HTTP_404_NOT_FOUND
