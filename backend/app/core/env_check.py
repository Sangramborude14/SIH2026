import sys
from backend.app.core.config import settings


def run_environment_check() -> bool:
    """
    Validates deployment environment variables without printing any secret values or credentials.
    """
    print("==================================================================")
    print("DISASTRA Disaster Intelligence Command Center Environment Check")
    print("==================================================================")
    print(f"ENVIRONMENT: {settings.ENVIRONMENT}")
    print(f"DATA_MODE: {settings.DATA_MODE}")
    print(f"ENGINE_VERSION: {settings.ENGINE_VERSION}")
    print("------------------------------------------------------------------")

    db_url = settings.ASYNC_DATABASE_URL
    is_postgres = "postgres" in db_url.lower()
    db_status = "configured (PostgreSQL)" if is_postgres else "default (local SQLite)"
    print(f"DATABASE_URL: {db_status}")

    redis_configured = bool(settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN)
    redis_status = "configured (Upstash Cloud REST)" if redis_configured else "not_configured (In-Memory Fallback)"
    print(f"REDIS: {redis_status}")

    bhoonidhi_configured = bool(settings.BHOONIDHI_USER_ID and settings.BHOONIDHI_PASSWORD)
    bhoonidhi_status = "configured (ISRO Bhoonidhi)" if bhoonidhi_configured else "not_configured (Mock Mode)"
    print(f"BHOONIDHI: {bhoonidhi_status}")

    gemini_configured = bool(getattr(settings, "GEMINI_API_KEY", None))
    gemini_status = "configured (Google Gemini)" if gemini_configured else "not_configured (Mock Mode)"
    print(f"GEMINI: {gemini_status}")

    resend_configured = bool(getattr(settings, "RESEND_API_KEY", None))
    resend_status = "configured (Resend Email)" if resend_configured else "not_configured (Mock Mode)"
    print(f"RESEND: {resend_status}")

    print("------------------------------------------------------------------")

    if settings.ENVIRONMENT == "production":
        errors = []
        if not is_postgres:
            errors.append("Production requires a valid PostgreSQL DATABASE_URL (Supabase).")
        if not redis_configured:
            errors.append("Production requires UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN.")

        if errors:
            print("ENVIRONMENT CHECK RESULT: FAIL")
            for err in errors:
                print(f"  - ERROR: {err}")
            print("==================================================================")
            return False
        else:
            print("ENVIRONMENT CHECK RESULT: PASS (All production requirements satisfied)")
            print("==================================================================")
            return True
    else:
        print("ENVIRONMENT CHECK RESULT: PASS (Development/Local environment)")
        print("==================================================================")
        return True


if __name__ == "__main__":
    success = run_environment_check()
    sys.exit(0 if success else 1)
