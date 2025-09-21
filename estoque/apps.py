from django.apps import AppConfig

class EstoqueConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estoque'

    def ready(self):
        # Importa os sinais quando a aplicação estiver pronta
        import estoque.signals