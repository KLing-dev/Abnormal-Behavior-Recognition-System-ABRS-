import pymysql
from config.db_config import db_settings


def create_database():
    connection = pymysql.connect(
        host=db_settings.host,
        port=db_settings.port,
        user=db_settings.username,
        password=db_settings.password,
        charset=db_settings.charset
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_settings.database}")
        connection.commit()
        print(f"Database '{db_settings.database}' created successfully")
    finally:
        connection.close()


def create_tables():
    from models.base import Base
    from models import video_source, banner, absent, loitering, gathering

    from models.base import engine
    Base.metadata.create_all(bind=engine)
    print("All tables created successfully")


if __name__ == "__main__":
    create_database()
    create_tables()
