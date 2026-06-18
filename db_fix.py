import sqlalchemy as sa
from core_app.database import engine  # Проверь, что путь правильный для твоего проекта

def fix_version():
    with engine.begin() as conn:
        # Принудительно ставим в базу хэш единственной миграции, которая у нас осталась
        conn.execute(sa.text("UPDATE alembic_version SET version_num = 'cfb652645e85';"))
    print("Готово! База синхронизирована с кодом.")

if __name__ == "__main__":
    fix_version()