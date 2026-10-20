"""
Base settings shared by every environment. Nothing environment-specific
(DEBUG, ALLOWED_HOSTS) lives here -- see development.py / production.py.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# claimsense_project/settings/base.py -> up 3 levels to the project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load variables from a .env file at the project root (never committed --
# see .gitignore). .env.example documents the required keys with safe
# placeholder values.
load_dotenv(BASE_DIR / ".env")

# SECURITY WARNING: keep the secret key used in production secret!
# Pulled from the environment -- never hardcoded, never committed.
SECRET_KEY = os.environ.get("SECRET_KEY")

# Example of a second secret pulled the same way (real or dummy API key).
CLAIMS_EXTERNAL_API_KEY = os.environ.get("CLAIMS_EXTERNAL_API_KEY", "")

# P1-A6 text intelligence. The local model's weights download on first use.
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "Qwen/Qwen3-0.6B")  # see llm-test/ai_prototype.ipynb
LOCAL_LLM_MAX_NEW_TOKENS = 600
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
EXPLAIN_MODEL = os.environ.get("EXPLAIN_MODEL", "openai/gpt-oss-120b")  # any Groq chat model
EXPLAIN_TIMEOUT_SECONDS = 30
AI_RATE_LIMIT = int(os.environ.get("AI_RATE_LIMIT", "20"))  # model calls per user per 10 minutes

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "claims",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "claimsense_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Project-level templates (base.html) live here, in addition to
        # each app's own templates/<app_name>/ directory (APP_DIRS below).
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "claimsense_project.wsgi.application"
ASGI_APPLICATION = "claimsense_project.asgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DATABASE_PATH", str(BASE_DIR / "db.sqlite3")),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# where collectstatic puts everything (gitignored, we run it again on the server)
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# A5: allauth handles both password accounts and Google OAuth.
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
ACCOUNT_LOGIN_METHODS = {"username"}
ACCOUNT_SIGNUP_FIELDS = ["username*", "email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGOUT_ON_GET = False
SOCIALACCOUNT_LOGIN_ON_GET = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
GOOGLE_OAUTH_ENABLED = bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
        "APPS": ([{
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "key": "",
        }] if GOOGLE_OAUTH_ENABLED else []),
    }
}
TEMPLATES[0]["OPTIONS"]["context_processors"].append("claims.context_processors.oauth_status")
ACCOUNT_FORMS = {"login": "claims.account_forms.ClaimSenseLoginForm"}
