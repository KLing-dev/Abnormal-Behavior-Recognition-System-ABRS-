"""
ABRS 一键启动脚本
启动顺序：Docker服务 → 数据库初始化 → API服务
"""
import subprocess
import sys
import time
import os


def run_command(cmd, description, check=True):
    """执行Shell命令"""
    print(f"\n{'='*60}")
    print(f"[{description}]")
    print(f"执行: {cmd}")
    print('='*60)
    result = subprocess.run(cmd, shell=True, capture_output=False)
    if check and result.returncode != 0:
        print(f"❌ {description} 失败!")
        return False
    print(f"✅ {description} 完成")
    return True


def start_docker_services():
    """启动Docker服务"""
    print("\n" + "="*60)
    print("步骤1: 启动Docker服务 (RabbitMQ + Redis)")
    print("="*60)

    docker_containers = {
        "RabbitMQ": "deeee04007b2",
        "Redis": "860458aef4e2"
    }

    for name, container_id in docker_containers.items():
        cmd = f"docker start {container_id}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ {name} ({container_id}) 已启动")
        else:
            if "already started" in result.stderr or "is already running" in result.stderr:
                print(f"  ℹ️ {name} ({container_id}) 已在运行")
            else:
                print(f"  ⚠️ {name} ({container_id}) 启动失败: {result.stderr.strip()}")


def init_database():
    """初始化数据库"""
    print("\n" + "="*60)
    print("步骤2: 初始化数据库")
    print("="*60)

    cmd = f'"{sys.executable}" init_db.py'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"  ⚠️ 数据库初始化警告: {result.stderr}")
        if "already exists" not in result.stdout.lower():
            return False
    print("  ✅ 数据库初始化完成")
    return True


def start_api():
    """启动API服务"""
    print("\n" + "="*60)
    print("步骤3: 启动API服务")
    print("="*60)

    cmd = f'"{sys.executable}" run.py'

    print("\n  按 Ctrl+C 停止服务\n")
    print("-"*60)

    subprocess.run(cmd, shell=True)


def check_service_health():
    """检查服务健康状态"""
    import requests
    import urllib3
    urllib3.disable_warnings()

    try:
        resp = requests.get("http://localhost:8000/health", timeout=5)
        if resp.status_code == 200:
            print(f"\n  ✅ API服务健康: {resp.json()}")
            return True
    except Exception as e:
        print(f"\n  ⚠️ API服务未就绪: {e}")
    return False


def main():
    print("\n" + "="*60)
    print("   ABRS 异常行为识别系统 - 一键启动")
    print("="*60)

    print("\n[前置检查]")

    docker_check = subprocess.run(
        "docker ps",
        shell=True,
        capture_output=True,
        text=True
    )
    if docker_check.returncode != 0:
        print("  ⚠️ Docker未运行，请先启动Docker Desktop")
        sys.exit(1)
    print("  ✅ Docker运行中")

    start_docker_services()

    print("\n[等待服务启动...]")
    time.sleep(3)

    if not init_database():
        print("  ⚠️ 数据库初始化可能有问题，继续尝试启动...")

    print("\n" + "="*60)
    print("   所有服务准备就绪，启动API...")
    print("="*60)

    start_api()


if __name__ == "__main__":
    main()