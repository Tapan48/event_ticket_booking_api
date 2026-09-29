from django.conf import settings

from config import celery_app


def test_celery_reads_django_settings():
    assert celery_app.conf.broker_url == settings.REDIS_URL
    assert celery_app.conf.task_always_eager  # from config.settings.test
