"""
数据库初始化脚本
用于项目首次部署或数据库结构更新时初始化数据库
"""
import pymysql
from config.db_config import db_settings


def create_database():
    """创建数据库（如果不存在）"""
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


def drop_tables():
    """删除所有表（用于开发测试时更新表结构）"""
    connection = pymysql.connect(
        host=db_settings.host,
        port=db_settings.port,
        user=db_settings.username,
        password=db_settings.password,
        database=db_settings.database,
        charset=db_settings.charset
    )
    
    try:
        with connection.cursor() as cursor:
            # 获取所有表名
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            # 禁用外键检查
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # 删除所有表
            for table in tables:
                table_name = table[0]
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                print(f"Dropped table: {table_name}")
            
            # 启用外键检查
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
        connection.commit()
        print("All tables dropped successfully")
    finally:
        connection.close()


def create_tables():
    """创建所有表"""
    from models.base import Base
    from models import video_source, banner, absent, loitering, gathering

    from models.base import engine
    Base.metadata.create_all(bind=engine)
    print("All tables created successfully")


def init_database(reset=False):
    """
    初始化数据库
    
    Args:
        reset: 如果为True，则删除所有表并重新创建（用于开发测试）
    """
    # 创建数据库
    create_database()
    
    # 如果需要重置，先删除所有表
    if reset:
        print("\nResetting database...")
        drop_tables()
    
    # 创建表
    create_tables()
    print("\nDatabase initialization completed!")


if __name__ == "__main__":
    import sys
    
    # 检查是否有 --reset 参数
    reset_flag = "--reset" in sys.argv
    
    if reset_flag:
        print("=" * 60)
        print("WARNING: This will DELETE all existing data!")
        print("=" * 60)
        confirm = input("Are you sure? Type 'yes' to continue: ")
        if confirm.lower() == "yes":
            init_database(reset=True)
        else:
            print("Cancelled.")
            init_database(reset=False)
    else:
        init_database(reset=False)
