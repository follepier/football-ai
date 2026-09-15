from app.services.db_cache import install_database_storage


# In locale/Codespaces DATABASE_URL puo' non essere impostato: in quel caso
# resta attiva la cache su filesystem. In hosting, Neon/PostgreSQL diventa lo
# storage condiviso e persistente per tutte le analisi.
install_database_storage()

from app.main import app  # noqa: E402,F401
