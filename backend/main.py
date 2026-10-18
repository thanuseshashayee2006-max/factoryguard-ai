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

# Load environment variables (.env file)
load_dotenv()

# Configure logging (hides sensitive internal errors from client responses)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FactoryGuardBackend")

app = FastAPI(title="FactoryGuard AI")

# Allow CORS requests from frontend (Streamlit / Web)
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

# Configuration & Variables
AMD_API_KEY = os.getenv("AMD_API_KEY")
LLM_API_ENDPOINT = os.getenv("LLM_API_ENDPOINT", "http://localhost:8000/v1")
MODEL_PATH = os.getenv("MODEL_PATH", "models/sensor_anomaly_model.pkl")

# Safe ML Model Loading
ml_model = None
try:
    if os.path.exists(MODEL_PATH):
        ml_model = joblib.load(MODEL_PATH)
        logger.info(f"ML Model loaded successfully from {MODEL_PATH}")
    else:
        logger.warning(f"Model file not found at {MODEL_PATH}. Running in fallback mode.")
except Exception as e:
    logger.error(f"Failed to load ML Model: {str(e)}")


# Schemas
class SensorDataRequest(BaseModel):
    temperature: float = Field(..., description="Sensor temperature input")
    vibration: float = Field(..., description="Sensor vibration input")
    pressure: float = Field(..., description="Sensor pressure input")


class FullWorkflowRequest(BaseModel):
    object_type: str = Field(..., min_length=1)
    authorized: bool
    sensor_data: SensorDataRequest


# Endpoints
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


@app.post("/predict-anomaly")
def predict_anomaly(sensor_data: SensorDataRequest):
    """Handles ML model predictions safely without crashing if model is missing."""
    if ml_model is None:
        return {
            "status": "UNKNOWN",
            "risk_score": 0.0,
            "note": "Model not loaded, using safe baseline.",
        }

    try:
        features = [
            [
                sensor_data.temperature,
                sensor_data.vibration,
                sensor_data.pressure,
            ]
        ]
        prediction = ml_model.predict(features)[0]
        return {
            "status": "ANOMALY" if prediction == 1 else "NORMAL",
            "prediction": int(prediction),
        }
    except Exception as e:
        logger.error(f"Error during model prediction: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing sensor prediction.",
        )


@app.post("/workflow")
async def run_full_workflow(request: FullWorkflowRequest):
    """Full integrated workflow from dashboard inputs to final guidance."""
    try:
        # A. Authorization check
        obj_type = request.object_type.strip().lower()
        if request.authorized:
            obj_status = "NORMAL"
        elif obj_type in ["wildlife", "unknown_person"]:
            obj_status = "ISOLATE"
        else:
            obj_status = "WARNING"

        # B. Sensor Anomaly ML Model Check
        sensor_status = "NORMAL"
        if ml_model is not None:
            features = [
                [
                    request.sensor_data.temperature,
                    request.sensor_data.vibration,
                    request.sensor_data.pressure,
                ]
            ]
            pred = ml_model.predict(features)[0]
            if pred == 1:
                sensor_status = "ANOMALY_DETECTED"

        # C. AMD / LLM API Integration with Graceful Fallback
        llm_guidance = "Standard monitoring recommended."
        if AMD_API_KEY:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        f"{LLM_API_ENDPOINT}/chat",
                        headers={"Authorization": f"Bearer {AMD_API_KEY}"},
                        json={
                            "prompt": f"Status: {obj_status}, Sensor: {sensor_status}. Suggest response."
                        },
                    )
                    if response.status_code == 200:
                        llm_guidance = response.json().get(
                            "guidance", llm_guidance
                        )
            except Exception as api_err:
                logger.warning(
                    f"AMD Cloud API offline or timed out: {str(api_err)}"
                )
                llm_guidance = (
                    "RAG service offline. Follow standard operating protocol."
                )

        return {
            "object_status": obj_status,
            "sensor_status": sensor_status,
            "guidance": llm_guidance,
            "system_overall": (
                "CRITICAL"
                if "ISOLATE" in [obj_status, sensor_status]
                else "STABLE"
            ),
        }

    except Exception as e:
        logger.error(f"Workflow execution error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during workflow execution.",
        )
        # Machine-health analysis endpoint
# Initial rule-based baseline; not a trained ML prediction.

class AnalyzeRequest(BaseModel):
    machine_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    temperature: float
    rpm: float
    torque: float
    wear: float


@app.post("/analyze")
def analyze_machine(request: AnalyzeRequest):
    """Analyze machine health using an initial rule-based baseline."""

    alerts = []

    # Critical conditions
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

    # Warning conditions
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

# AI-powered machine failure prediction using the trained ML model

class MachineFailureRequest(BaseModel):
    machine_id: str = Field(default='UNKNOWN', description='Machine identifier')
    machine_name: str = Field(default='Unknown machine', description='Machine name')
    air_temperature: float = Field(..., description="Air temperature in Kelvin")
    process_temperature: float = Field(..., description="Process temperature in Kelvin")
    rotational_speed: float = Field(..., description="Rotational speed in rpm")
    torque: float = Field(..., description="Torque in Nm")
    tool_wear: float = Field(..., description="Tool wear in minutes")


class AlertStatusRequest(BaseModel):
    status: Literal['Open', 'Acknowledged', 'Resolved']


@app.get('/api/alerts')
def get_saved_alerts():
    return list_alerts()


@app.patch('/api/alerts/{alert_id}')
def change_saved_alert_status(alert_id: str, request: AlertStatusRequest):
    alert = update_alert(alert_id, request.status)
    if alert is None:
        raise HTTPException(status_code=404, detail='Alert not found.')
    return alert


@app.post("/predict-machine-failure")
def predict_machine_failure(request: MachineFailureRequest):
    """Predict machine failure using the trained five-feature ML pipeline."""

    if ml_model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Machine failure model is not loaded.",
        )

    try:
        import pandas as pd

        input_data = pd.DataFrame([{
            "Air temperature [K]": request.air_temperature,
            "Process temperature [K]": request.process_temperature,
            "Rotational speed [rpm]": request.rotational_speed,
            "Torque [Nm]": request.torque,
            "Tool wear [min]": request.tool_wear,
        }])

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
