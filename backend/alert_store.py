import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

STORE_PATH = Path(__file__).resolve().parent.parent / "data" / "alert_history.json"
LOCK = threading.Lock()

def _read():
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        return []
    try:
        return json.loads(STORE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return []

def list_alerts():
    with LOCK:
        return sorted(_read(), key=lambda item: item["timestamp"], reverse=True)

def record_prediction(machine_id, machine_name, prediction, probability, readings):
    if prediction != 1:
        return None

    with LOCK:
        alerts = _read()
        alert = {
            "id": f"ALT-{uuid4().hex[:8].upper()}",
            "machineId": machine_id,
            "machineName": machine_name,
            "severity": "Critical",
            "description": (
                f"Trained ML model predicted failure "
                f"({probability * 100:.1f}% probability). "
                "Inspect this machine."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "Open",
            "source": "trained-ml",
            "failureProbability": probability,
            "readings": readings,
        }
        alerts.append(alert)
        STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STORE_PATH.write_text(json.dumps(alerts, indent=2))
        return alert

def update_alert(alert_id, new_status):
    with LOCK:
        alerts = _read()
        for alert in alerts:
            if alert["id"] == alert_id:
                alert["status"] = new_status
                STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
                STORE_PATH.write_text(json.dumps(alerts, indent=2))
                return alert
        return None
