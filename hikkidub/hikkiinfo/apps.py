from django.apps import AppConfig


class HikkiinfoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hikkiinfo'
    
    def ready(self):
        import hikkiinfo.signals  # noqa: F401 — регистрация сигналов
