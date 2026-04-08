"""
数据库初始化脚本
支持增量创建表，不会重复建表
"""
import pymysql
import sys


def get_connection(need_database=True):
    """获取数据库连接"""
    from config.db_config import db_settings

    params = {
        "host": db_settings.host,
        "port": db_settings.port,
        "user": db_settings.username,
        "password": db_settings.password,
        "charset": db_settings.charset
    }

    if need_database:
        params["database"] = db_settings.database

    return pymysql.connect(**params)


def create_database():
    """创建数据库（如果不存在）"""
    print("\n[1/3] Checking database...")
    try:
        from config.db_config import db_settings
        conn = get_connection(need_database=False)
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_settings.database} DEFAULT CHARACTER SET utf8mb4")
            conn.commit()
            print(f"  [OK] Database '{db_settings.database}' ready")
        finally:
            conn.close()
    except Exception as e:
        print(f"  [WARN] Database check: {e}")


def check_tables_exist():
    """检查已存在的表"""
    print("\n[2/3] Checking existing tables...")
    try:
        conn = get_connection(need_database=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                existing_tables = [row[0] for row in cursor.fetchall()]
                if existing_tables:
                    print(f"  [INFO] Existing tables: {', '.join(existing_tables)}")
                else:
                    print("  [INFO] No existing tables")
                return existing_tables
        finally:
            conn.close()
    except Exception as e:
        print(f"  [WARN] Table check: {e}")
        return []


def create_tables():
    """创建所有表（幂等操作）"""
    print("\n[3/3] Creating/updating table structure...")
    try:
        from models.base import Base
        from models import video_source, banner, absent, loitering, gathering, system_setting
        from models.base import engine

        Base.metadata.create_all(bind=engine)

        conn = get_connection(need_database=True)
        try:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                all_tables = [row[0] for row in cursor.fetchall()]
                print(f"  [OK] Table structure ready ({len(all_tables)} tables)")
                for t in all_tables:
                    print(f"     - {t}")
        finally:
            conn.close()

        # 初始化系统设置
        init_system_settings()

        return True
    except Exception as e:
        print(f"  [WARN] Create table: {e}")
        return False


def init_system_settings():
    """初始化系统默认设置"""
    print("\n[4/4] Initializing system settings...")
    try:
        from models.base import SessionLocal
        from models.system_setting import SystemSetting
        import json

        db = SessionLocal()
        try:
            # 检查是否已有设置
            existing = db.query(SystemSetting).first()
            if existing:
                print("  [OK] System settings already initialized")
                return

            # 聚集模块设置
            gathering_settings = [
                ("trigger_duration_sec", "180", "gathering"),
                ("clear_duration_sec", "300", "gathering"),
                ("level_thresholds", json.dumps({"light": 5, "medium": 10, "urgent": 20}), "gathering")
            ]

            # 徘徊模块设置
            loitering_settings = [
                ("default_threshold_min", "10", "loitering"),
                ("min_duration_filter_sec", "60", "loitering")
            ]

            # 离岗模块设置
            absent_settings = [
                ("default_max_absent_min", "5", "absent"),
                ("check_interval_sec", "10", "absent")
            ]

            # 全局模型参数
            global_settings = [
                ("model_params", json.dumps({"yolo_confidence": 0.5, "yolo_iou": 0.45, "fps": 10, "resolution": "1080p"}), "global")
            ]

            all_settings = gathering_settings + loitering_settings + absent_settings + global_settings

            for key, value, module in all_settings:
                setting = SystemSetting(
                    setting_key=key,
                    setting_value=value,
                    module=module
                )
                db.add(setting)

            db.commit()
            print(f"  [OK] System settings initialized ({len(all_settings)} items)")
        finally:
            db.close()
    except Exception as e:
        print(f"  [WARN] Init settings: {e}")


def init_database(reset=False):
    """
    初始化数据库

    Args:
        reset: 是否重置（删除后重建）
    """
    print("\n" + "="*60)
    print("   ABRS Database Initialization")
    print("="*60)

    create_database()
    existing = check_tables_exist()

    if reset:
        print("\n[WARN] Reset mode: Will delete all data!")
        confirm = input("   Confirm reset? Enter 'YES' to continue: ")
        if confirm != "YES":
            print("   Cancelled")
            return

        print("\n   Deleting old tables...")
        try:
            conn = get_connection(need_database=True)
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                    cursor.execute("SHOW TABLES")
                    tables = cursor.fetchall()
                    for (table_name,) in tables:
                        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                        print(f"   - Deleted: {table_name}")
                    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                conn.commit()
            finally:
                conn.close()
            print("   [OK] Old tables deleted")
        except Exception as e:
            print(f"   [WARN] Delete table error: {e}")

    print("\n" + "-"*60)
    success = create_tables()
    print("\n" + "="*60)
    if success:
        print("   [OK] Database initialization complete!")
    else:
        print("   [WARN] Database initialization complete (with warnings)")
    print("="*60)


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv

    if reset_flag:
        init_database(reset=True)
    else:
        init_database(reset=False)