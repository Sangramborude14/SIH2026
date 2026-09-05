from typing import List, Union, Dict, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "DISASTRA - Disaster Intelligence Engine (NER Landslide)"
    VERSION: str = "1.0.0"
    ENGINE_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Database: defaults to SQLite for local runs; overridden by PostgreSQL URL in production/docker
    DATABASE_URL: str = "sqlite+aiosqlite:///./sih_disaster.db"
    DIRECT_URL: Optional[str] = None
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_TIMEOUT: float = 30.0
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False
    DB_SSL_MODE: str = "prefer"  # "disable", "prefer", "require"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Ensures the database connection URL uses an async dialect and safely handles unreplaced placeholders."""
        url = self.DATABASE_URL
        if any(token in url for token in ["YOUR-PROJECT-REF", "YOUR-PASSWORD", "[REGION]", "[YOUR-", "[YOUR_"]):
            if self.ENVIRONMENT == "production":
                from backend.app.core.logging import logger
                logger.error("CRITICAL: Unreplaced placeholder detected in DATABASE_URL in production environment.")
            else:
                from backend.app.core.logging import logger
                logger.warning("Unreplaced placeholder detected in DATABASE_URL. Falling back to local SQLite database.")
                return "sqlite+aiosqlite:///./sih_disaster.db"
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url



    # Redis / Upstash Redis Configuration
    REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    UPSTASH_REDIS_REST_URL: Optional[str] = None
    UPSTASH_REDIS_REST_TOKEN: Optional[str] = None
    REDIS_CACHE_ENABLED: bool = True
    REDIS_TIMEOUT_SECONDS: float = 3.0

    # Ingestion & Data Mode: "LIVE" (Open-Meteo with fallback) or "SIMULATION" (deterministic scenarios)
    DATA_MODE: str = "LIVE"

    # Scheduling Cadence Separation (Seconds)
    ENGINE_ASSESSMENT_INTERVAL_SECONDS: int = 30
    LIVE_INGESTION_INTERVAL_SECONDS: int = 900

    # External Provider Configuration (Open-Meteo - Free Public API)
    OPEN_METEO_API_URL: str = "https://api.open-meteo.com/v1/forecast"

    WEATHER_REQUEST_TIMEOUT_SECONDS: float = 7.0
    WEATHER_MAX_RETRIES: int = 2
    WEATHER_BACKOFF_FACTOR: float = 0.5
    
    # Granular Cache TTL Strategy (Seconds)
    WEATHER_CACHE_TTL_SECONDS: int = 300            # 5 mins for live weather observation
    WEATHER_FORECAST_CACHE_TTL_SECONDS: int = 900   # 15 mins for forecast timelines
    BHOONIDHI_CACHE_TTL_SECONDS: int = 1800         # 30 mins for satellite metadata
    HISTORICAL_CACHE_TTL_SECONDS: int = 43200       # 12 hours for historical incident records
    TERRAIN_CACHE_TTL_SECONDS: int = 86400          # 24 hours for static DEM & susceptibility

    # --- Earth Observation & Bhoonidhi (ISRO / NRSC) Configuration ---
    BHOONIDHI_API_URL: str = "https://bhoonidhi.nrsc.gov.in/api"
    BHOONIDHI_USER_ID: Optional[str] = None
    BHOONIDHI_PASSWORD: Optional[str] = None
    BHOONIDHI_PROVIDER_MODE: str = "MOCK"  # "LIVE" or "MOCK"

    # Data Freshness Thresholds (Minutes)
    DATA_FRESHNESS_WEATHER_MINUTES: int = 60
    DATA_FRESHNESS_SOIL_MOISTURE_MINUTES: int = 180

    AI_EXPLANATION_CACHE_TTL_SECONDS: int = 900     # 15 mins for AI risk explanation briefings

    # --- Agentic AI & Google Gemini Configuration ---
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.6-flash"
    LLM_PROVIDER: str = "gemini"  # "mock", "gemini", "openai"
    LLM_MODEL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    AI_MODE: str = "LIVE"  # "MOCK" or "LIVE"
    AGENT_MAX_STEPS: int = 6
    AGENT_TIMEOUT_SECONDS: float = 20.0

    @property
    def EFFECTIVE_GEMINI_KEY(self) -> Optional[str]:
        return self.GEMINI_API_KEY or self.LLM_API_KEY

    @property
    def EFFECTIVE_GEMINI_MODEL(self) -> str:
        return self.GEMINI_MODEL or self.LLM_MODEL or "gemini-3.6-flash"

    # --- Firebase Cloud Messaging (FCM) Configuration ---
    FIREBASE_PROJECT_ID: str = "studio-4032992257-84f15"
    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None
    FIREBASE_PROVIDER_MODE: str = "MOCK"  # "LIVE" or "MOCK"
    FIREBASE_APP_NAME: str = "sih-landslide-fcm"

    # --- Resend Email Notification Configuration ---
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: str = "onboarding@resend.dev"
    RESEND_PROVIDER_MODE: str = "MOCK"  # "LIVE" or "MOCK"
    APP_BASE_URL: str = "http://localhost:3000"

    # --- Authentication & JWT Security ---
    JWT_SECRET_KEY: str = "disastra-super-secret-production-hardened-jwt-key-sih26001-ner-987456"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_COOKIE_NAME: str = "disastra_refresh_token"
    REFRESH_COOKIE_SECURE: bool = False  # Set to True in HTTPS production
    REFRESH_COOKIE_SAMESITE: str = "lax"
    ADMIN_BOOTSTRAP_TOKEN: Optional[str] = "disastra-admin-bootstrap-sih2026-ner"

    # --- SSRF Protection & Allowed External Hosts ---
    ALLOWED_EXTERNAL_HOSTS: List[str] = [
        "api.open-meteo.com",
        "archive-api.open-meteo.com",
        "bhoonidhi.nrsc.gov.in",
        "fcm.googleapis.com",
        "api.resend.com",
    ]

    # --- Rate Limiting Configuration ---
    RATE_LIMIT_ENABLED: bool = True

    # CORS origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # --- Landslide Risk Factor Weights (Centralized & Normalized 0-1) ---
    RISK_WEIGHTS: Dict[str, float] = {
        "rainfall_intensity": 0.20,
        "rainfall_anomaly": 0.15,
        "rainfall_persistence": 0.15,
        "soil_moisture": 0.15,
        "soil_moisture_trend": 0.10,
        "terrain": 0.15,
        "historical": 0.10,
    }

    # Backward compatibility individual weight getters
    @property
    def WEIGHT_RAINFALL_INTENSITY(self) -> float:
        return self.RISK_WEIGHTS["rainfall_intensity"]

    @property
    def WEIGHT_RAINFALL_ANOMALY(self) -> float:
        return self.RISK_WEIGHTS["rainfall_anomaly"]

    @property
    def WEIGHT_RAINFALL_PERSISTENCE(self) -> float:
        return self.RISK_WEIGHTS["rainfall_persistence"]

    @property
    def WEIGHT_SOIL_MOISTURE(self) -> float:
        return self.RISK_WEIGHTS["soil_moisture"]

    @property
    def WEIGHT_SOIL_MOISTURE_TREND(self) -> float:
        return self.RISK_WEIGHTS["soil_moisture_trend"]

    @property
    def WEIGHT_SLOPE_ELEVATION(self) -> float:
        return self.RISK_WEIGHTS["terrain"]

    @property
    def WEIGHT_HISTORICAL_SUSCEPTIBILITY(self) -> float:
        return self.RISK_WEIGHTS["historical"]

    # --- Risk Level Score Thresholds (0-100) ---
    THRESHOLD_WATCH: float = 25.0
    THRESHOLD_ELEVATED: float = 40.0
    THRESHOLD_HIGH: float = 50.0
    THRESHOLD_CRITICAL: float = 75.0
    THRESHOLD_MODERATE: float = 25.0

    # --- Event State Hysteresis & Debounce ---
    HYSTERESIS_DOWNGRADE_BUFFER: float = 4.0   # Must drop 4 points below threshold to de-escalate
    DEBOUNCE_CONFIRMATION_STEPS: int = 1      # Consecutive evaluations required

    # --- Anomaly Detection Parameters ---
    ANOMALY_Z_THRESHOLD: float = 2.0
    MIN_OBSERVATIONS_FOR_BASELINE: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
