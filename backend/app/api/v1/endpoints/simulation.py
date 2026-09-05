from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_db, require_role
from backend.app.models.user import User
from backend.app.schemas.simulation import SimulationScenarioRequest, SimulationScenarioResponse
from backend.app.services.simulation_service import SimulationService
from backend.app.core.logging import logger

router = APIRouter()


@router.post("/scenario", response_model=SimulationScenarioResponse)
async def simulate_scenario(
    request: SimulationScenarioRequest,
    current_user: User = Depends(require_role(["EXPERT", "ADMIN"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Injects realistic simulated meteorological time-series for a target scenario:
    - `normal`: Low rainfall, normal soil moisture, stable baseline (Score ~ 5-20)
    - `heavy_rain`: Intensifying rainfall bursts, rising moisture (Score ~ 35-50)
    - `persistent_rain`: Sustained continuous rainfall > 150mm (Score ~ 55-70)
    - `landslide_risk_increasing`: Escalating multi-factor threat (Score ~ 65-75)
    - `critical`: Extreme cumulative rainfall + saturated soil + pressure drop (Score > 75)
    - `recovery`: Cessation of rain, moisture drainage, risk subsiding towards safe baseline
    """
    valid_scenarios = [
        "normal",
        "heavy_rain",
        "persistent_rain",
        "abnormal_rainfall",
        "abnormal_soil_moisture",
        "landslide_risk_increasing",
        "critical",
        "recovery"
    ]

    if request.scenario.lower() not in valid_scenarios:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scenario '{request.scenario}'. Must be one of: {', '.join(valid_scenarios)}"
        )

    try:
        response = await SimulationService.run_scenario(db, request)
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error during simulation scenario execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during scenario simulation."
        )
