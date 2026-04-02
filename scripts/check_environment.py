import sys
import importlib
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


def check_python_version():
    print("=" * 50)
    print("检查 Python 版本")
    print("=" * 50)
    version = sys.version_info
    print(f"Python 版本: {version.major}.{version.minor}.{version.micro}")
    if version.major == 3 and version.minor >= 11:
        print("✓ Python 版本符合要求 (>= 3.11)")
        return True
    else:
        print("✗ Python 版本过低，需要 >= 3.11")
        return False


def check_dependencies():
    print("\n" + "=" * 50)
    print("检查依赖包")
    print("=" * 50)

    packages = {
        "fastapi": "FastAPI",
        "uvicorn": "uvicorn",
        "sqlalchemy": "SQLAlchemy",
        "pymysql": "PyMySQL",
        "pika": "pika",
        "cv2": "opencv-python",
        "numpy": "numpy",
        "PIL": "Pillow",
        "ultralytics": "ultralytics",
        "paddle": "paddlepaddle",
        "paddleocr": "paddleocr",
        "loguru": "loguru",
        "pydantic": "pydantic",
    }

    results = []
    for module, name in packages.items():
        try:
            if module == "cv2":
                import cv2
            elif module == "PIL":
                import PIL
            else:
                importlib.import_module(module)
            print(f"✓ {name} 已安装")
            results.append(True)
        except ImportError:
            print(f"✗ {name} 未安装")
            results.append(False)

    return all(results)


def check_database():
    print("\n" + "=" * 50)
    print("检查数据库连接")
    print("=" * 50)

    try:
        import pymysql
        from config.db_config import db_settings

        print(f"数据库地址: {db_settings.host}:{db_settings.port}")
        print(f"数据库名称: {db_settings.database}")

        connection = pymysql.connect(
            host=db_settings.host,
            port=db_settings.port,
            user=db_settings.username,
            password=db_settings.password,
            charset=db_settings.charset,
            connect_timeout=5
        )
        connection.close()
        print("✓ 数据库连接成功")
        return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False


def check_rabbitmq():
    print("\n" + "=" * 50)
    print("检查 RabbitMQ 连接")
    print("=" * 50)

    try:
        import pika
        from config.rabbitmq_config import rabbitmq_settings

        print(f"RabbitMQ 地址: {rabbitmq_settings.host}:{rabbitmq_settings.port}")

        credentials = pika.PlainCredentials(
            rabbitmq_settings.username,
            rabbitmq_settings.password
        )
        parameters = pika.ConnectionParameters(
            host=rabbitmq_settings.host,
            port=rabbitmq_settings.port,
            virtual_host=rabbitmq_settings.virtual_host,
            credentials=credentials,
            connection_attempts=1,
            socket_timeout=5
        )
        connection = pika.BlockingConnection(parameters)
        connection.close()
        print("✓ RabbitMQ 连接成功")
        return True
    except Exception as e:
        print(f"✗ RabbitMQ 连接失败: {e}")
        return False


def check_redis():
    print("\n" + "=" * 50)
    print("检查 Redis 连接")
    print("=" * 50)

    try:
        import redis
        from config.redis_config import redis_settings

        print(f"Redis 地址: {redis_settings.host}:{redis_settings.port}")

        client = redis.Redis(
            host=redis_settings.host,
            port=redis_settings.port,
            password=redis_settings.password,
            db=redis_settings.db,
            decode_responses=redis_settings.decode_responses,
            socket_connect_timeout=5
        )
        client.ping()
        print("✓ Redis 连接成功")
        return True
    except Exception as e:
        print(f"✗ Redis 连接失败: {e}")
        return False


def check_model_files():
    print("\n" + "=" * 50)
    print("检查模型文件")
    print("=" * 50)

    weights_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "weights")

    if not os.path.exists(weights_dir):
        print(f"✗ weights 目录不存在: {weights_dir}")
        return False

    model_files = [f for f in os.listdir(weights_dir) if f.endswith('.pt')]
    if not model_files:
        print("✗ 未找到模型权重文件")
        print(f"  请运行: python scripts/download_models.py")
        return False
    else:
        for f in model_files:
            print(f"✓ 找到模型: {f}")
        return True


def check_project_structure():
    print("\n" + "=" * 50)
    print("检查项目结构")
    print("=" * 50)

    required_dirs = ["config", "api", "core", "models", "utils", "static", "logs", "scripts", "weights", "PRD"]
    required_files = ["run.py", "init_db.py", "environment.yml", "requirements.txt"]

    base_dir = os.path.dirname(os.path.dirname(__file__))

    results = []
    for d in required_dirs:
        path = os.path.join(base_dir, d)
        if os.path.isdir(path):
            print(f"✓ 目录存在: {d}/")
        else:
            print(f"✗ 目录缺失: {d}/")
            results.append(False)

    for f in required_files:
        path = os.path.join(base_dir, f)
        if os.path.isfile(path):
            print(f"✓ 文件存在: {f}")
        else:
            print(f"✗ 文件缺失: {f}")
            results.append(False)

    return all(results) if results else True


def main():
    print("\n" + "=" * 50)
    print("ABRS 环境检查")
    print("=" * 50)

    results = {
        "Python 版本": check_python_version(),
        "依赖包": check_dependencies(),
        "项目结构": check_project_structure(),
        "模型文件": check_model_files(),
        "数据库": check_database(),
        "RabbitMQ": check_rabbitmq(),
        "Redis": check_redis(),
    }

    print("\n" + "=" * 50)
    print("检查结果汇总")
    print("=" * 50)

    for name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")

    all_passed = all(results.values())
    print("\n" + "=" * 50)
    if all_passed:
        print("✓ 所有检查通过，环境可用！")
    else:
        print("✗ 部分检查失败，请修复后再继续")
    print("=" * 50)

    return all_passed


if __name__ == "__main__":
    main()
