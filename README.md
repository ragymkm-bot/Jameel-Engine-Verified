# Jameel-System (RAGY) 🧠

## Autonomous Multi-Agent Orchestration Engine

نظام متكامل لإدارة المهام والأتمتة بـ Multi-Agents، مبني على عزل صارم وتدقيق مشفر.

[![Status](https://img.shields.io/badge/Status-Operational-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.14-green.svg)]()
[![License](https://img.shields.io/badge/License-RAGY--Protocol-blue.svg)]()

> **ابدأ من هنا:** ▼

## 📚 الفهرس الرئيسي (للمهندس/الوكيل الجديد)
| الوثيقة | الغرض |
|---|---|
| **`RAGY_MASTER_BLUEPRINT_X.md`** | المراحل 1–23 + سجل الأخطاء + الحدود المعروفة |
| **`RAGY_AUDIT_2026-11-19.md`** | تقرير التدقيق الجنائي (D1–D5) |
| **`OPERATIONS_RUNBOOK.md`** | التشغيل اليومي + الاستعادة + التصعيد |
| **`DECISION_LOG.md`** | كل قرار + السبب + البديل المرفوض |
| **`SECURITY_MODEL.md`** | خريطة الثقة + الأسرار + التهديدات |
| **`RAGY_CLOUD_ARCHITECTURE.md`** | تصميم البنية السحابية |
| **`STATUS_REPORT_FULL.md`** | الحالة الشاملة |
| **`LINKS_AND_MCP.md`** | الروابط الحية + تشخيص MCP |
| **`cloud/README.md`** | تشغيل الـ Worker والـ poller |
| **`cloud/WHATSAPP_SETUP.md`** | تفعيل بوت واتساب |
| **`T3_DESIGN.md` / `T4_DESIGN.md` / `SEQ007_DISCOVERY_DESIGN.md`** | تصاميم الجسر والـ E2E |

## 🌐 الروابط الحية
| الخدمة | الرابط |
|---|---|
| الواجهة + اللوحة | `https://ragy-cloud-engine.aragy76.workers.dev/` |
| لوحة التحكم `/app` | `https://ragy-cloud-engine.aragy76.workers.dev/app` |
| GitHub | `https://github.com/ragymkm-bot/Jameel-Engine-Verified` |
| Cloudflare Pages | `https://jameel-ragy-command-center.pages.dev/` |

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
