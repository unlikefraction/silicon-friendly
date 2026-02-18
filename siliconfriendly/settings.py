import os
import sys
from pathlib import Path
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import env

SECRET_KEY = env.DJANGO_SECRET
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
APPEND_SLASH = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'accounts',
    'websites',
    'search',
    'payments',
    'chat',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'core.middleware.AllowAnyOriginCorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'accounts.middleware.AuthTokenMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'siliconfriendly.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.carbon_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'siliconfriendly.wsgi.application'

DB_HOST = getattr(env, 'DB_HOST', 'localhost')
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': getattr(env, 'DB_NAME', 'siliconfriendly'),
        'USER': getattr(env, 'DB_USER', ''),
        'PASSWORD': getattr(env, 'DB_PASSWORD', ''),
        'HOST': DB_HOST,
        'PORT': getattr(env, 'DB_PORT', '5432'),
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.SiliconTokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

CELERY_BEAT_SCHEDULE = {
    "websites-daily-verification-crunch-1956utc": {
        "task": "websites.tasks.daily_verification_crunch",
        "schedule": crontab(hour=19, minute=56),
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://localhost:8111',
    'http://127.0.0.1:8111',
    'https://siliconfriendly.com',
    'https://www.siliconfriendly.com',
]

# Security settings for production
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
