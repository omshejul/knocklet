import os
from pathlib import Path


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

INSTALLED_APPS = [
    "corsheaders",
    "login_api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "linkedin_api.urls"
DATA_DIR = Path(
    os.environ.get("LINKEDIN_DATA_DIR", Path.home() / ".linkedin-cli")
).expanduser()
DATABASE_PATH = Path(
    os.environ.get("LINKEDIN_DATABASE_PATH", DATA_DIR / "linkedin.sqlite3")
).expanduser()
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
        "OPTIONS": {"timeout": 20},
        "TEST": {"NAME": ":memory:"},
    }
}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("WEB_ORIGIN", "http://localhost:3000").split(",")
    if origin.strip()
]
