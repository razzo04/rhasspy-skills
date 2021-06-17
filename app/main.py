from fastapi import FastAPI, status, Response
from .routers.mqtt import mqtt_router
from .routers.skill import skill_router


app = FastAPI(debug=True, version="0.0.1")
app.include_router(mqtt_router, prefix="/api")
app.include_router(skill_router, prefix="/api")


@app.get("/")
def read_root(response: Response):
    response.status_code = status.HTTP_307_TEMPORARY_REDIRECT
    response.headers["Location"] = "/docs"
