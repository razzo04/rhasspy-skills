import pathlib
from docker.models.containers import Container
from docker.models.networks import Network
from fastapi.testclient import TestClient

from ..config import Settings
from ..main import app
from ..dependencies import get_db, get_docker, get_settings, get_temp_directory
from ..models import SkillModel
from unittest.mock import Mock
from sys import platform
import os
from pathlib import Path
from pytest_httpx import HTTPXMock
import pytest

db = Mock()
docker = Mock()


def override_get_db():
    return db


def override_get_docker():
    return docker


client = TestClient(app)

app.dependency_overrides[get_docker] = override_get_docker
app.dependency_overrides[get_db] = override_get_db


def get_test_resource(name: str) -> Path:
    return Path(os.path.join(os.path.dirname(__file__), "testresources", name))


@pytest.fixture(scope="session")
def tmp_dir(tmp_path_factory: pytest.TempPathFactory):
    tmp_path = tmp_path_factory.getbasetemp()
    app.dependency_overrides[get_settings] = lambda: Settings(
        store_directory=tmp_path.as_posix()
    )
    app.dependency_overrides[get_temp_directory] = lambda: tmp_path.resolve()
    return tmp_path


def test_install_skill_invalid_archive(tmp_dir: pathlib.Path):
    response = client.post("/api/skills", files={"file": b"invalid data"})
    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_archive"
    db.insert_skill.assert_not_called()
    docker.containers.list.assert_not_called()
    docker.containers.run.assert_not_called()


def test_install_skill_invalid_manifest(tmp_dir: pathlib.Path):
    response = client.post(
        "/api/skills",
        files={"file": get_test_resource("invalid_manifest.tar").read_bytes()},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "invalid_manifest"
    db.insert_skill.assert_not_called()
    docker.containers.list.assert_not_called()
    docker.containers.run.assert_not_called()


def test_install_skill_no_image(tmp_dir: pathlib.Path):
    response = client.post(
        "/api/skills",
        files={"file": get_test_resource("manifest_correct.tar").read_bytes()},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "image_not_present"
    db.insert_skill.assert_not_called()
    docker.containers.list.assert_not_called()
    docker.containers.run.assert_not_called()


def test_install_skill(tmp_dir: pathlib.Path, httpx_mock: HTTPXMock):
    # TODO check request
    httpx_mock.add_response(method="POST")
    slug = "weather"
    # TODO add more test to check container name conflict
    docker.containers.list.return_value = [Container({"Name": "rhasspy"})]
    db.insert_skill.return_value = True
    docker.networks.list.return_value = [Network()]
    docker.api.inspect_container.return_value = {
        "Mounts": [
            {
                "Type": "bind",
                "Source": "/path/to/data",
                "Destination": "/data",
            }
        ]
    }
    response = client.post(
        "/api/skills",
        files={"file": get_test_resource("manifest_docker_sentences.tar").read_bytes()},
    )
    install_path = response.json()["detail"].replace(f"installed {slug} in", "").strip()
    if platform != "win32":
        assert (
            install_path.replace("\\", "/")
            == tmp_dir.joinpath("skills/weather").as_posix()
        )
    assert response.json()["state"] == "success"
    db.insert_skill.assert_called_once_with(
        SkillModel(
            skill_name=slug,
            hashed_password=db.insert_skill.call_args[0][0].hashed_password,
            topic_access=None,
            start_on_boot=False,
        )
    )
    tag = "skill_" + slug
    docker.containers.run.assert_called_once_with(
        tag,
        environment={
            "MQTT_PASS": docker.containers.run.call_args[1]["environment"]["MQTT_PASS"],
            "MQTT_USER": "weather",
        },
        network="mqtt-net",
        detach=True,
        name=tag,
        labels={"skill_name": slug},
        volumes={os.path.join(install_path, "data"): {"bind": "/data", "mode": "rw"}},
    )
