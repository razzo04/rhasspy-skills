import logging
import os
from datetime import datetime

from rhasspyhermes.nlu import NluIntent
from rhasspyhermes_app import EndSession, HermesApp

_LOGGER = logging.getLogger("TimeApp")

app = HermesApp("TimeApp", host="mqtt.server",username=os.environ["MQTT_USER"], password=os.environ["MQTT_PASS"])

@app.on_intent("GetTime")
async def get_time(intent: NluIntent):
    """Tell the time."""
    now = datetime.now().strftime("%H %M")
    return EndSession(f"It's {now}")

app.run()
