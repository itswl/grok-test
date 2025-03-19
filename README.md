# Grok AI告警分析系统

这是一个基于Grok AI模型的告警处理和AI聊天系统，可以自动分析Prometheus告警并提供处理建议。

## 功能特点

1. **AI告警分析**：自动分析Prometheus告警并提供处理建议
2. **聊天功能**：提供交互式AI聊天界面
3. **数据持久化**：所有告警和聊天记录保存到SQLite数据库
4. **Docker支持**：提供完整的Docker配置，方便部署

## 快速开始

### Docker部署

参见 [Docker使用说明](docker.md)

### 配置Alertmanager

1. 修改你的Alertmanager配置，添加webhook接收器指向Flask服务：

```yaml
receivers:
- name: "ai-alert-webhook"
  webhook_configs:
  - url: "http://your-flask-server:6000/api/alerts"
    send_resolved: true
    http_config:
      headers:
        X-API-KEY: "1234567890"

route:
  # 其他配置...
  receiver: "ai-alert-webhook"  # 默认使用AI分析服务
  # 特殊告警仍然使用原来的接收器
  routes:
  - matchers:
    - alertname =~ "InfoInhibitor|Watchdog"
    receiver: "null"
```

2. 重新加载Alertmanager配置

```bash
# 如果使用Prometheus Operator
kubectl apply -f alertmanager.yml

# 或者直接发送HTTP请求重新加载
curl -X POST http://alertmanager:9093/-/reload
```

## API接口

### 告警接收接口

- **URL**: `/api/alerts`
- **方法**: `POST`
- **认证**: 需要在请求头中包含 `X-API-KEY: 1234567890`
- **请求体**: Alertmanager标准告警格式

## 访问Web界面

- 告警分析API: http://your-server:6000/api/alerts

## 后续开发计划

1. 告警分析Web界面
2. 告警统计和报表功能
3. 告警处理建议改进
4. 聊天Web界面 