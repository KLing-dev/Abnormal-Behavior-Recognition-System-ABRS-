"""
插入测试用的横幅告警数据
用于测试批量处理功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
import random
import uuid
from models.base import SessionLocal
from models.banner import AlarmBanner


def insert_test_alarms(count: int = 1000):
    """插入指定数量的测试告警数据"""
    db = SessionLocal()
    try:
        # 违规词列表
        illegal_words = ['反动', '暴力', '恐怖', '赌博', '毒品', '色情', '诈骗', '黑客', '攻击', '威胁']

        # 检测文字列表
        detected_texts = [
            '这是一段包含违规词的文字',
            '横幅内容测试',
            '宣传标语示例',
            '广告文字内容',
            '活动通知横幅',
            '安全警示标语',
            '欢迎横幅内容',
            '节日庆祝标语',
            '会议通知横幅',
            '展览宣传内容'
        ]

        # 区域ID列表
        area_ids = ['banner_001', 'banner_002', 'banner_003', 'banner_004', 'banner_005']

        # 源类型
        source_types = ['file', 'camera', 'stream']

        print(f"开始插入 {count} 条测试告警数据...")

        alarms = []
        base_time = datetime.now() - timedelta(days=7)  # 从7天前开始

        for i in range(count):
            # 生成随机时间（过去7天内）
            alarm_time = base_time + timedelta(
                days=random.randint(0, 7),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59)
            )

            # 随机选择违规词和检测文字
            illegal_word = random.choice(illegal_words)
            detected_text = f"{random.choice(detected_texts)} - {illegal_word}"

            # 随机状态（80%未处理，20%已处理）
            status = 1 if random.random() < 0.2 else 0

            alarm = AlarmBanner(
                alarm_time=alarm_time,
                event_id="01",
                alarm_type="横幅违规告警",
                content={
                    "track_id": str(random.randint(1, 100)),
                    "detected_text": detected_text,
                    "illegal_word": illegal_word,
                    "bbox": [random.randint(100, 500), random.randint(100, 300),
                             random.randint(600, 1000), random.randint(400, 700)],
                    "source_type": random.choice(source_types),
                    "source_id": random.choice(area_ids)
                },
                source_type=random.choice(source_types),
                source_id=random.choice(area_ids),
                message_id=str(uuid.uuid4()),
                status=status
            )
            alarms.append(alarm)

            # 每100条提交一次，避免内存占用过大
            if len(alarms) >= 100:
                db.add_all(alarms)
                db.commit()
                print(f"已插入 {i + 1}/{count} 条数据...")
                alarms = []

        # 提交剩余的数据
        if alarms:
            db.add_all(alarms)
            db.commit()

        print(f"✅ 成功插入 {count} 条测试告警数据！")

        # 统计信息
        total = db.query(AlarmBanner).count()
        unprocessed = db.query(AlarmBanner).filter(AlarmBanner.status == 0).count()
        processed = db.query(AlarmBanner).filter(AlarmBanner.status == 1).count()

        print(f"\n当前数据库统计：")
        print(f"  总计: {total} 条")
        print(f"  未处理: {unprocessed} 条")
        print(f"  已处理: {processed} 条")

    except Exception as e:
        db.rollback()
        print(f"❌ 插入数据失败: {e}")
        raise
    finally:
        db.close()


def clear_test_alarms():
    """清空所有测试告警数据"""
    db = SessionLocal()
    try:
        count = db.query(AlarmBanner).delete()
        db.commit()
        print(f"✅ 已清空 {count} 条告警数据")
    except Exception as e:
        db.rollback()
        print(f"❌ 清空数据失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='插入测试用的横幅告警数据')
    parser.add_argument('--count', type=int, default=1000, help='插入的数据条数（默认1000）')
    parser.add_argument('--clear', action='store_true', help='清空所有数据')

    args = parser.parse_args()

    if args.clear:
        confirm = input("确定要清空所有告警数据吗？输入 'yes' 确认: ")
        if confirm.lower() == 'yes':
            clear_test_alarms()
        else:
            print("已取消操作")
    else:
        insert_test_alarms(args.count)
