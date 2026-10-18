
import os
import logging
import joblib
import httpx

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal

from backend.alert_store import list_alerts, record_prediction, update_alert
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FactoryGuardBackend")

app = FastAPI(title="FactoryGuard AI")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8083",
        "http://127.0.0.1:8083",
        "http://localhost:8084",
        "http://127.0.0.1:8084",
        "http://localhost:8085",
        "http://127.0.0.1:8085",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

# Configuration
AMD_API_KEY = os.getenv("AMD_API_KEY")
LLM_API_ENDPOINT = os.getenv(
    "LLM_API_ENDPOINT", "http://localhost:8000/v1"
)
MODEL_PATH = os.getenv(
    "MODEL_PATH", "models/sensor_anomaly_model.pkl"
)

# Load the existing five-feature ML pipeline
ml_model = None

try:
    if os.path.exists(MODEL_PATH):
        ml_model = joblib.load(MODEL_PATH)
        logger.info("ML model loaded successfully from %s", MODEL_PATH)
    else:
        logger.warning(
            "Model file not found at %s. Running in fallback mode.",
            MODEL_PATH,
        )
except Exception:
    logger.exception("Failed to load ML model")


# Request schemas
class SensorDataRequest(BaseModel):
    temperature: float = Field(
        ..., description="Sensor temperature input"
    )
    vibration: float = Field(
        ..., description="Sensor vibration input"
    )
    pressure: float = Field(
        ..., description="Sensor pressure input"
    )


class FullWorkflowRequest(BaseModel):
    object_type: str = Field(..., min_length=1)
    authorized: bool
    sensor_data: SensorDataRequest


class AnalyzeRequest(BaseModel):
    machine_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    temperature: float
    rpm: float
    torque: float
    wear: float


class MachineFailureRequest(BaseModel):
    machine_id: str = Field(
        default="UNKNOWN", description="Machine identifier"
    )
    machine_name: str = Field(
        default="Unknown machine", description="Machine name"
    )
    air_temperature: float = Field(
        ..., description="Air temperature in Kelvin"
    )
    process_temperature: float = Field(
        ..., description="Process temperature in Kelvin"
    )
    rotational_speed: float = Field(
        ..., description="Rotational speed in rpm"
    )
    torque: float = Field(
        ..., description="Torque in Nm"
    )
    tool_wear: float = Field(
        ..., description="Tool wear in minutes"
    )


class AlertStatusRequest(BaseModel):
    status: Literal["Open", "Acknowledged", "Resolved"]


# Basic endpoints
@app.get("/")
def home():
    return {"message": "FactoryGuard AI backend is running!"}


@app.get("/health")
def health():
    return {
        "status": "online",
        "model_loaded": ml_model is not None,
        "amd_config": bool(AMD_API_KEY),
    }


# Sensor anomaly endpoint
# The current model expects five machine-failure features.
# It cannot correctly process this endpoint's three sensor inputs.
@app.post("/predict-anomaly")
def predict_anomaly(sensor_data: SensorDataRequest):
    logger.warning(
        "Anomaly prediction skipped: the loaded model expects "
        "five features, while this endpoint receives three."
    )

    return {
        "status": "UNKNOWN",
        "risk_score": None,
        "note": (
            "No anomaly prediction was made. A compatible model "
            "trained on temperature, vibration, and pressure is required."
        ),
    }


# Integrated workflow
@app.post("/workflow")
async def run_full_workflow(request: FullWorkflowRequest):
    """Combine authorization, sensor status, and guidance."""

    try:
        # A. Authorization check
        obj_type = request.object_type.strip().lower()

        if request.authorized:
            obj_status = "NORMAL"
        elif obj_type in ["wildlife", "unknown_person"]:
            obj_status = "ISOLATE"
        else:
            obj_status = "WARNING"

        # B. Sensor anomaly check
        # Do not pass three features into the five-feature model.
        sensor_status = "UNKNOWN"

        # C. Guidance integration with graceful fallback
        llm_guidance = (
            "Sensor analysis unavailable. Follow standard "
            "operating procedures and inspect the sensor readings."
        )

        if AMD_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        f"{LLM_API_ENDPOINT}/chat",
                        headers={
                            "Authorization": f"Bearer {AMD_API_KEY}"
                        },
                        json={
                            "prompt": (
                                f"Object status: {obj_status}. "
                                f"Sensor status: {sensor_status}. "
                                "Give cautious operational guidance. "
                                "Do not claim sensor analysis was completed."
                            )
                        },
                    )

                    if response.status_code == 200:
                        llm_guidance = response.json().get(
                            "guidance", llm_guidance
                        )

            except Exception:
                logger.exception(
                    "AMD Cloud API unavailable or timed out"
                )
                llm_guidance = (
                    "Guidance service unavailable. Follow standard "
                    "operating procedures and inspect the equipment."
                )

        # Do not report STABLE while sensor analysis is unavailable.
        if obj_status == "ISOLATE":
            overall_status = "CRITICAL"
        elif sensor_status == "UNKNOWN":
            overall_status = "REVIEW"
        else:
            overall_status = "STABLE"

        return {
            "object_status": obj_status,
            "sensor_status": sensor_status,
            "guidance": llm_guidance,
            "system_overall": overall_status,
        }

    except Exception:
        logger.exception("Workflow execution failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during workflow execution.",
        )


# Rule-based machine-health analysis
@app.post("/analyze")
def analyze_machine(request: AnalyzeRequest):
    """Analyze machine health using baseline thresholds."""

    alerts = []

    if request.temperature >= 90:
        alerts.append("Critical temperature")

    if request.wear >= 220:
        alerts.append("Critical wear level")

    if alerts:
        machine_status = "Critical"
        message = (
            f"{request.name} requires immediate inspection. "
            + ", ".join(alerts)
            + "."
        )

    elif request.temperature >= 75 or request.wear >= 170:
        machine_status = "Warning"
        reasons = []

        if request.temperature >= 75:
            reasons.append("elevated temperature")

        if request.wear >= 170:
            reasons.append("high wear level")

        message = (
            f"{request.name} needs attention due to "
            + " and ".join(reasons)
            + "."
        )

    else:
        machine_status = "Healthy"
        message = (
            f"{request.name} is within the initial "
            "temperature and wear thresholds."
        )

    return {
        "machine_id": request.machine_id,
        "machine_name": request.name,
        "status": machine_status,
        "message": message,
        "metrics": {
            "temperature": request.temperature,
            "rpm": request.rpm,
            "torque": request.torque,
            "wear": request.wear,
        },
        "analysis_method": "rule_based_baseline",
    }


# Saved alerts
@app.get("/api/alerts")
def get_saved_alerts():
    return list_alerts()


@app.patch("/api/alerts/{alert_id}")
def change_saved_alert_status(
    alert_id: str, request: AlertStatusRequest
):
    alert = update_alert(alert_id, request.status)

    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found.",
        )

    return alert


# ML-based machine failure prediction
# This endpoint uses the five named features expected by the model.
@app.post("/predict-machine-failure")
def predict_machine_failure(request: MachineFailureRequest):
    """Predict machine failure using the trained five-feature pipeline."""

    if ml_model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Machine failure model is not loaded.",
        )

    try:
        import pandas as pd

        input_data = pd.DataFrame(
            [
                {
                    "Air temperature [K]": request.air_temperature,
                    "Process temperature [K]": request.process_temperature,
                    "Rotational speed [rpm]": request.rotational_speed,
                    "Torque [Nm]": request.torque,
                    "Tool wear [min]": request.tool_wear,
                }
            ]
        )

        prediction = int(ml_model.predict(input_data)[0])
        probabilities = ml_model.predict_proba(input_data)[0]
        failure_probability = round(float(probabilities[1]), 4)

        record_prediction(
            machine_id=request.machine_id,
            machine_name=request.machine_name,
            prediction=prediction,
            probability=failure_probability,
            readings={
                "air_temperature": request.air_temperature,
                "process_temperature": request.process_temperature,
                "rotational_speed": request.rotational_speed,
                "torque": request.torque,
                "tool_wear": request.tool_wear,
            },
        )

        return {
            "prediction": prediction,
            "status": "failure" if prediction == 1 else "normal",
            "failure_probability": failure_probability,
            "model": "sensor_anomaly_model",
        }

    except Exception:
        logger.exception("Machine failure prediction failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process machine failure prediction.",
        )
