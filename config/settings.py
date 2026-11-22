"""MYSTIQ settings. Secrets come from the environment / .env (never committed)."""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

_INSECURE_KEY = "dev-only-insecure-key-change-me"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", _INSECURE_KEY)
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
if not DEBUG and SECRET_KEY in (_INSECURE_KEY, "change-me", ""):
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Set a real DJANGO_SECRET_KEY when DJANGO_DEBUG=0.")
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")

INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "accounts", "cases", "game", "rag_engine", "nlp_engine",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"

# SQLite for the working version; set DATABASE_URL-style vars to move to PostgreSQL later.
if os.getenv("MYSTIQ_DB_ENGINE") == "postgres":
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql", "NAME": os.getenv("PGDATABASE", "mystiq"),
        "USER": os.getenv("PGUSER", "mystiq"), "PASSWORD": os.getenv("PGPASSWORD", ""),
        "HOST": os.getenv("PGHOST", "localhost"), "PORT": os.getenv("PGPORT", "5432")}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
X_CONTENT_TYPE_OPTIONS = "nosniff"
if not DEBUG:
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = os.getenv("DJANGO_HTTPS", "0") == "1"
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------- MYSTIQ NLP / RAG configuration ----------------
MYSTIQ = {
    "CASES_DIR": BASE_DIR / "data" / "cases",
    "EVAL_DIR": BASE_DIR / "data" / "evaluation",
    "VECTOR_DIR": BASE_DIR / "vector_store",
    # "auto" tries the pretrained models below and falls back to the local engines if they cannot load.
    "NLP_BACKEND": os.getenv("MYSTIQ_NLP_BACKEND", "auto"),          # auto | local | transformers
    "EMBEDDING_MODEL": os.getenv("MYSTIQ_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
    "NLI_MODEL": os.getenv("MYSTIQ_NLI_MODEL", "cross-encoder/nli-MiniLM2-L6-H768"),
    "RERANK_MODEL": os.getenv("MYSTIQ_RERANK_MODEL", ""),            # e.g. cross-encoder/ms-marco-MiniLM-L-6-v2
    "SPACY_MODEL": os.getenv("MYSTIQ_SPACY_MODEL", "en_core_web_sm"),
    "TOP_K": int(os.getenv("MYSTIQ_TOP_K", "5")),
    "MIN_SCORE": float(os.getenv("MYSTIQ_MIN_SCORE", "0.22")),       # below this => insufficient evidence
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
    "GEMINI_MODEL": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    "LLM_TIMEOUT": float(os.getenv("MYSTIQ_LLM_TIMEOUT", "20")),
}
