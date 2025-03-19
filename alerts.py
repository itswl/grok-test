import os
from openai import OpenAI
import json
import requests
import time
import hmac
import hashlib
import base64
import urllib.parse
import smtplib
import sqlite3
from email.mime.text import MIMEText
from flask import Flask, request, jsonify


# 从环境变量获取数据库路径
DB_PATH = os.environ.get("ALERTS_DB_PATH", "alerts.db")

def init_db():
    """ 初始化 SQLite 数据库 """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_name TEXT NOT NULL,
            severity TEXT NOT NULL,
            summary TEXT NOT NULL,
            description TEXT,
            ai_analysis TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

# 在应用启动时创建数据库
init_db()


app = Flask(__name__)


# OpenAI客户端配置
client = OpenAI(
    api_key="xai-xxx",
    base_url="https://api.x.ai/v1",
)

def send_notifications(message):
    """ 发送通知 """
    pass

def process_alert_with_ai(alerts):
    """ 调用 OpenAI API 处理告警信息 """
    prompt = "以下是 Prometheus 的告警信息，请分析告警影响并提供处理建议：\n\n"
    
    for alert in alerts:
        summary = alert.get("annotations", {}).get("summary", "No summary")
        description = alert.get("annotations", {}).get("description", "No description")
        severity = alert.get("labels", {}).get("severity", "unknown")
        prompt += f"- **告警级别**: {severity}\n- **事件**: {summary}\n- **详情**: {description}\n\n"
        print(prompt)
    response = client.chat.completions.create(
        model="grok-2-latest",
        messages=[{"role": "system", "content": "你是一个专业的 SRE 工程师，帮助分析告警, 请以markdown格式输出。尽量简洁"},
                  {"role": "user", "content": prompt}]
    )
    print(response)
    return response.choices[0].message.content

def save_alert_to_db(alert_name, severity, summary, description, ai_analysis):
    """ 存入 SQLite """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO alerts (alert_name, severity, summary, description, ai_analysis) VALUES (?, ?, ?, ?, ?)",
        (alert_name, severity, summary, description, ai_analysis)
    )
    conn.commit()
    cur.close()
    conn.close()

@app.route("/api/alerts", methods=["POST"])
def receive_alert():
    # 尝试从Header获取API key
    request_api_key = request.headers.get("X-API-KEY")
    # 如果Header中没有API key，则从URL参数获取
    if not request_api_key:
        request_api_key = request.args.get("api_key")
        
    if request_api_key != "1234567890":
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json
    alerts = data.get("alerts", [])
    if not alerts:
        return jsonify({"message": "No alerts received"}), 200

    for alert in alerts:
        alert_name = alert["labels"].get("alertname", "Unknown")
        severity = alert["labels"].get("severity", "unknown")
        summary = alert["annotations"].get("summary", "No summary")
        description = alert["annotations"].get("description", "")

        # AI 处理
        ai_analysis = process_alert_with_ai([alert])

        # 存入数据库
        save_alert_to_db(alert_name, severity, summary, description, ai_analysis)

        # # 发送通知
        original_alert = f"## 原始告警信息\n\n- **告警名称**: {alert_name}\n- **告警级别**: {severity}\n- **概述**: {summary}\n- **详情**: {description}\n\n"
        message = f"🚨 **AI 处理告警** 🚨\n\n{original_alert}## AI 分析结果\n\n{ai_analysis}"
        # print(message)
        send_notifications(message)

    return jsonify({"message": "Alerts processed",  "original_alert": {
        "alert_name": alert_name,
        "severity": severity,
        "summary": summary,
        "description": description
    },"ai_analysis": ai_analysis})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000, debug=True)