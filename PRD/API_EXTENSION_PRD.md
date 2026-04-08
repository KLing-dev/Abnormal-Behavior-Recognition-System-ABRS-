# ABRS 后端 API 扩展需求文档

**文档版本**: V1.0  
**创建日期**: 2026-04-07  
**文档目的**: 补充前端所需的辅助接口，确保与已有接口兼容  

---

## 1. 扩展原则

### 1.1 兼容性保证
- 所有已有接口保持**完全不变**，包括 URL 路径、请求参数、响应格式
- 新增接口使用独立的 URL 路径，不与已有接口冲突
- 数据库表结构扩展时，新增字段必须允许 NULL 或有默认值

### 1.2 接口命名规范
- 遵循已有命名规范：`/模块/功能/动作`
- 查询接口使用 GET，操作接口使用 POST
- 批量操作使用 `/batch` 后缀

### 1.3 响应格式统一
```json
{
  "message": "操作成功",
  "data": {},
  "code": 200
}
```

---

## 2. 全局告警接口扩展

### 2.1 告警详情查询
**接口**: `GET /api/v1/alarm/detail`  
**功能**: 查询单条告警详情  
**请求参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| alarm_id | string | 是 | 告警记录ID |

**响应示例**:
```json
{
  "alarm_id": "123",
  "alarm_time": "2026-04-07 10:00:00",
  "event_id": "04",
  "alarm_type": "聚集告警",
  "content": {
    "area_id": "B01",
    "gathering_count": 12,
    "level": "中度"
  },
  "source_type": "camera",
  "source_id": "CAM01",
  "status": 0
}
```

### 2.2 告警标记处理
**接口**: `POST /api/v1/alarm/mark`  
**功能**: 批量标记告警为已处理  
**请求体**:
```json
{
  "alarm_ids": ["123", "124", "125"]
}
```

**响应示例**:
```json
{
  "message": "标记成功",
  "updated_count": 3
}
```

### 2.3 告警导出
**接口**: `GET /api/v1/alarm/export`  
**功能**: 导出告警记录为 Excel/CSV  
**请求参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| start_time | string | 否 | 开始时间 |
| end_time | string | 否 | 结束时间 |
| event_id | string | 否 | 事件类型 |
| format | string | 否 | xlsx/csv，默认xlsx |

**响应**: 文件流 (blob)

### 2.4 告警类型列表
**接口**: `GET /api/v1/alarm/types`  
**功能**: 获取所有告警类型  
**响应示例**:
```json
{
  "types": [
    {"event_id": "01", "name": "横幅识别", "alarm_types": ["违规横幅"]},
    {"event_id": "02", "name": "离岗识别", "alarm_types": ["离岗首次告警", "离岗持续告警", "离岗告警解除"]},
    {"event_id": "03", "name": "徘徊警告", "alarm_types": ["徘徊告警", "徘徊告警解除"]},
    {"event_id": "04", "name": "聚集警告", "alarm_types": ["聚集告警", "聚集告警解除"]}
  ]
}
```

---

## 3. 模块状态接口扩展

### 3.1 聚集模块状态
**接口**: `GET /api/v1/gathering/status`  
**功能**: 获取聚集检测实时状态  
**响应示例**:
```json
{
  "is_running": true,
  "source_id": "CAM01",
  "source_type": "camera",
  "areas_count": 2,
  "current_alarms": [
    {
      "area_id": "B01",
      "area_name": "广场区域",
      "person_count": 12,
      "level": "中度",
      "duration_min": 5
    }
  ]
}
```

### 3.2 聚集模块设置
**接口**: `GET /api/v1/gathering/setting/query`  
**功能**: 查询聚集检测全局设置  
**响应示例**:
```json
{
  "trigger_duration_sec": 180,
  "clear_duration_sec": 300,
  "level_thresholds": {
    "light": 5,
    "medium": 10,
    "urgent": 20
  }
}
```

**接口**: `POST /api/v1/gathering/setting/update`  
**功能**: 更新聚集检测全局设置  
**请求体**:
```json
{
  "trigger_duration_sec": 180,
  "clear_duration_sec": 300,
  "level_thresholds": {
    "light": 5,
    "medium": 10,
    "urgent": 20
  }
}
```

### 3.3 徘徊模块状态
**接口**: `GET /api/v1/loitering/status`  
**功能**: 获取徘徊检测实时状态  
**响应示例**:
```json
{
  "is_running": true,
  "source_id": "CAM01",
  "source_type": "camera",
  "areas_count": 1,
  "current_alarms": [
    {
      "area_id": "A01",
      "area_name": "北门区域",
      "loitering_count": 2,
      "threshold_min": 10
    }
  ]
}
```

### 3.4 徘徊模块设置
**接口**: `GET /api/v1/loitering/setting/query`  
**响应示例**:
```json
{
  "default_threshold_min": 10,
  "min_duration_filter_sec": 60
}
```

**接口**: `POST /api/v1/loitering/setting/update`  
**请求体**:
```json
{
  "default_threshold_min": 10,
  "min_duration_filter_sec": 60
}
```

### 3.5 横幅模块状态
**接口**: `GET /api/v1/banner/status`  
**已有接口，无需修改**  
**响应示例**:
```json
{
  "is_running": true,
  "alert_count": 5,
  "areas_count": 1,
  "illegal_words_count": 10
}
```

### 3.6 离岗模块状态
**接口**: `GET /api/v1/absent/status`  
**已有接口，无需修改**  

### 3.7 离岗模块设置
**接口**: `GET /api/v1/absent/setting/query`  
**响应示例**:
```json
{
  "default_max_absent_min": 5,
  "check_interval_sec": 10
}
```

**接口**: `POST /api/v1/absent/setting/update`  
**请求体**:
```json
{
  "default_max_absent_min": 5,
  "check_interval_sec": 10
}
```

---

## 4. 系统接口扩展

### 4.1 系统信息
**接口**: `GET /api/v1/system/info`  
**功能**: 获取系统基本信息  
**响应示例**:
```json
{
  "app_name": "ABRS",
  "version": "1.0.0",
  "start_time": "2026-04-07 08:00:00",
  "uptime_seconds": 7200,
  "modules": ["banner", "absent", "loitering", "gathering"]
}
```

### 4.2 服务状态查询
**接口**: `GET /api/v1/system/redis/status`  
**响应示例**:
```json
{
  "status": "connected",
  "latency_ms": 2
}
```

**接口**: `GET /api/v1/system/mysql/status`  
**响应示例**:
```json
{
  "status": "connected",
  "latency_ms": 5
}
```

**接口**: `GET /api/v1/system/rabbitmq/status`  
**响应示例**:
```json
{
  "status": "connected",
  "queues": [
    {"name": "warning_banner", "messages": 0},
    {"name": "warning_absent", "messages": 0},
    {"name": "warning_loitering", "messages": 0},
    {"name": "warning_gathering", "messages": 0}
  ]
}
```

### 4.3 系统日志
**接口**: `GET /api/v1/system/logs`  
**功能**: 查询系统日志  
**请求参数**:
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| level | string | 否 | 日志级别：DEBUG/INFO/WARNING/ERROR |
| module | string | 否 | 模块名 |
| start_time | string | 否 | 开始时间 |
| end_time | string | 否 | 结束时间 |
| limit | int | 否 | 返回条数，默认100 |

**响应示例**:
```json
{
  "logs": [
    {
      "time": "2026-04-07 10:00:00",
      "level": "INFO",
      "module": "gathering",
      "message": "检测启动成功"
    }
  ],
  "total": 1000
}
```

### 4.4 模型参数
**接口**: `GET /api/v1/system/model/params`  
**响应示例**:
```json
{
  "yolo_confidence": 0.5,
  "yolo_iou": 0.45,
  "fps": 10,
  "resolution": "1080p"
}
```

**接口**: `POST /api/v1/system/model/params/update`  
**请求体**:
```json
{
  "yolo_confidence": 0.5,
  "yolo_iou": 0.45,
  "fps": 10,
  "resolution": "1080p"
}
```

---

## 5. 数据库扩展

### 5.1 新增表：系统设置表
```sql
CREATE TABLE `t_system_setting` (
  `id` int NOT NULL AUTO_INCREMENT,
  `setting_key` varchar(50) NOT NULL COMMENT '设置键',
  `setting_value` text COMMENT '设置值（JSON格式）',
  `module` varchar(20) NOT NULL COMMENT '所属模块：global/gathering/loitering/absent/banner',
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_key_module` (`setting_key`, `module`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统设置表';
```

### 5.2 初始化数据
```sql
-- 聚集模块设置
INSERT INTO `t_system_setting` (`setting_key`, `setting_value`, `module`) VALUES
('trigger_duration_sec', '180', 'gathering'),
('clear_duration_sec', '300', 'gathering'),
('level_thresholds', '{"light":5,"medium":10,"urgent":20}', 'gathering');

-- 徘徊模块设置
INSERT INTO `t_system_setting` (`setting_key`, `setting_value`, `module`) VALUES
('default_threshold_min', '10', 'loitering'),
('min_duration_filter_sec', '60', 'loitering');

-- 离岗模块设置
INSERT INTO `t_system_setting` (`setting_key`, `setting_value`, `module`) VALUES
('default_max_absent_min', '5', 'absent'),
('check_interval_sec', '10', 'absent');

-- 全局模型参数
INSERT INTO `t_system_setting` (`setting_key`, `setting_value`, `module`) VALUES
('model_params', '{"yolo_confidence":0.5,"yolo_iou":0.45,"fps":10,"resolution":"1080p"}', 'global');
```

---

## 6. 实现优先级

| 优先级 | 接口 | 说明 |
|--------|------|------|
| P0 | `/alarm/detail`, `/alarm/mark` | 告警管理核心功能 |
| P0 | `/gathering/status`, `/loitering/status` | 实时监控必需 |
| P1 | `/system/redis/status`, `/system/mysql/status`, `/system/rabbitmq/status` | Dashboard 展示 |
| P1 | `/alarm/types`, `/alarm/export` | 告警管理完善 |
| P2 | `/gathering/setting/*`, `/loitering/setting/*`, `/absent/setting/*` | 配置管理 |
| P2 | `/system/info`, `/system/logs` | 系统监控 |
| P2 | `/system/model/params/*` | 模型调优 |

---

## 7. 兼容性验证清单

- [ ] 所有已有接口返回格式不变
- [ ] 新增接口 URL 不冲突
- [ ] 数据库新增字段允许 NULL
- [ ] 单元测试全部通过
- [ ] 前端页面无报错
