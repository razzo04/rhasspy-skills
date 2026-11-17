import io
import json
import pathlib
import tarfile
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


def _skill_tar(extra=None) -> bytes:
    """A minimal valid skill archive, plus any extra member (name, bytes | linkname)."""
    buffer = io.BytesIO()
    files = {
        "manifest.json": json.dumps(
            {"name": "weather", "slug": "weather", "version": "1.0.0"}
        ).encode(),
        "Dockerfile": b"FROM scratch\n",
        "sentences.ini": b"[weather]\nwhat is the weather\n",
    }
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        if extra is not None:
            name, payload = extra
            info = tarfile.TarInfo(name)
            if isinstance(payload, bytes):
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
            else:
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                tar.addfile(info)
    return buffer.getvalue()


def test_install_skill_rejects_member_outside_skill_directory(tmp_dir: pathlib.Path):
    db.reset_mock()
    docker.reset_mock()

    response = client.post(
        "/api/skills?force=true",
        files={"file": _skill_tar(("../../escaped-skill-file.txt", b"pwned"))},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "archive_entry_outside_skill"
    assert not (tmp_dir / "escaped-skill-file.txt").exists()
    assert not (tmp_dir / "skills" / "escaped-skill-file.txt").exists()
    assert not (tmp_dir / "skills" / "weather").exists()
    db.insert_skill.assert_not_called()
    docker.containers.run.assert_not_called()


def test_install_skill_rejects_archive_links(tmp_dir: pathlib.Path):
    db.reset_mock()
    docker.reset_mock()

    response = client.post(
        "/api/skills?force=true",
        files={"file": _skill_tar(("payload", "/etc/passwd"))},
    )

    assert response.status_code == 422
    assert response.json()["error_code"] == "archive_entry_outside_skill"
    assert not (tmp_dir / "skills" / "weather" / "payload").exists()
    db.insert_skill.assert_not_called()
