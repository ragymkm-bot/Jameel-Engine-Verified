# Jameel-System (RAGY) 🧠

## Autonomous Multi-Agent Orchestration Engine

نظام متكامل لإدارة المهام والأتمتة بـ Multi-Agents، مبني على عزل صارم وتدقيق مشفر.

[![Status](https://img.shields.io/badge/Status-Operational-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.14-green.svg)]()
[![License](https://img.shields.io/badge/License-RAGY--Protocol-blue.svg)]()

---

## 🏗️ المعمارية

```
User / Claude / Hermes
        ↓ (MCP)
RAGY MCP Server  →  tools: list_files, read_file (safe zone only)
        ↓
Core Orchestrator  →  State Machine  →  Task Manager
        ↓
Agents: Research · Developer · QA · Security · Automation
        ↓
Audit Log (SHA-256 hash chain)  +  SQLite  +  Webhook / Vault
```

---

## 🔒 الأمان

- **Safe Zone:** الـ MCP يقرأ فقط من `C:/AI-Agents-Lab` — أي طلب لخارجها يُرفض.
- **Audit Chain:** كل حدث له بصمة SHA-256 مرتبطة باللي قبله (tamper-evident).
- **Vault:** المفاتيح تُخزَّن محلياً في `secrets/.vault` ولا تُرسل للشات أبداً.
- **Least Privilege:** كل وكيل بصلاحية المهمة فقط.

---

## 🔌 ربط Claude Code (MCP)

الملف `.mcp.json` في جذر المشروع بيعرّف الخادم تلقائياً:

```json
{
  "mcpServers": {
    "ragy-stdio": {
      "command": "python",
      "args": ["C:/AI-Agents-Lab/mcp_stdio_server.py"]
    }
  }
}
```

بعد فتح المشروع في Claude Code، اكتب `/mcp` عشان تتأكد إن `ragy-stdio` متصل.

---

## 🚀 التشغيل

```bash
python main.py                          # المنسق
python mcp_stdio_server.py              # خادم MCP
python ragy_agents/webhook_server.py    # Webhook + Vault
```

أو عبر Docker: `docker-compose up -d`

---

## ✅ الحالة

| المكوّن | الحالة |
|---|---|
| GitHub Repo | متصل ومُحدَّث |
| MCP Server | شغال ومُختبَر |
| Audit Log | شغال (hash chain) |
| CI/CD | GitHub Actions |
| Cloudflare Tunnel | متوقف (محتاج دومين/شهادة) |

---

**المطور:** ragymkm-bot · 📧 etaj.me@gmail.com
