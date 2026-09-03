from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    dashboard,
    locations,
    weather,
    risk,
    events,
    engine,
    simulation,
    ingestion,
    system,
    ai,
    field,
    public,
    alerts,
    analytics,
    earth_observation,
    notifications,
    ml,
)

api_router = APIRouter()

api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard Intelligence"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])
api_router.include_router(weather.router, prefix="/weather", tags=["Weather & Environment"])
api_router.include_router(risk.router, prefix="/risk", tags=["Risk Intelligence"])
api_router.include_router(events.router, prefix="/events", tags=["Disaster Events"])
api_router.include_router(engine.router, prefix="/engine", tags=["Disaster Engine"])
api_router.include_router(simulation.router, prefix="/simulation", tags=["Simulation & Scenarios"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["Data Ingestion"])
api_router.include_router(system.router, prefix="/system", tags=["System & Providers"])
api_router.include_router(ai.router, prefix="/ai", tags=["Agentic AI Intelligence"])
api_router.include_router(field.router, prefix="/field", tags=["Field Operations & Rescue"])
api_router.include_router(public.router, prefix="/public", tags=["Public Disaster Alerts & Safety"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["CAP Feeds, SitReps & Multi-Channel Alerting"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Push Notifications & FCM Device Registry"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Historical Analytics, Playback & Calibration"])
api_router.include_router(earth_observation.router, prefix="/earth-observation", tags=["Earth Observation & Bhoonidhi"])
api_router.include_router(ml.router, prefix="/ml", tags=["Landslide ML Early Warning & Predictive Analytics"])


