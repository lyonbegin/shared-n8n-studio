#!/usr/bin/env python3
"""Send completion email on actual clean frontier exhaustion, requiring SMTP secrets."""
import json,os,smtplib,ssl
from email.message import EmailMessage
from pathlib import Path
path=Path(os.getenv("TV_MANIFEST","tradingview_recursive_output/manifest.json"))
if not path.is_file():
 print("MAIL_SKIP_NO_MANIFEST",flush=True)
 raise SystemExit(0)
m=json.loads(path.read_text(encoding="utf-8"))
if m.get("state")!="FRONTIER_EXHAUSTED":
 print("MAIL_SKIP_NOT_COMPLETE",m.get("state"),flush=True)
 raise SystemExit(0)
required=("TV_SMTP_HOST","TV_SMTP_USER","TV_SMTP_PASSWORD","TV_REPORT_EMAIL")
missing=[x for x in required if not os.getenv(x)]
if missing:
 print("MAIL_NOT_CONFIGURED",",".join(missing),flush=True)
 raise SystemExit(0)
msg=EmailMessage()
msg["Subject"]=f"[TradingView] 재귀 수집 완료 - Strategy {m['strategies']} / Indicator {m['indicators']}"
msg["From"]=os.environ["TV_SMTP_USER"]
msg["To"]=os.environ["TV_REPORT_EMAIL"]
msg.set_content(
  f"TradingView 제작자 재귀 수집 결과입니다.\n"
  f"Strategy {m['strategies']}건 / Indicator {m['indicators']}건\n"
  f"이번 실행 제작자 {m['authors_processed']}명, 신규 Strategy {m['new_strategies']}건, 신규 Indicator {m['new_indicators']}건\n"
  f"오류 {m['error_count']}건, 남은 제작자 대기열 0명\n"
  f"GitHub Actions: https://github.com/lyonbegin/shared-n8n-studio/actions/runs/{os.getenv('GITHUB_RUN_ID','')}\n"
  "단, 공개 사이트 전체 개수와 일치함을 증명하는 것은 아닙니다.\n")
port=int(os.getenv("TV_SMTP_PORT") or "465")
if port==465:
 with smtplib.SMTP_SSL(os.environ["TV_SMTP_HOST"],port,context=ssl.create_default_context(),timeout=30) as smtp:
  smtp.login(os.environ["TV_SMTP_USER"],os.environ["TV_SMTP_PASSWORD"])
  smtp.send_message(msg)
else:
 with smtplib.SMTP(os.environ["TV_SMTP_HOST"],port,timeout=30) as smtp:
  smtp.starttls(context=ssl.create_default_context())
  smtp.login(os.environ["TV_SMTP_USER"],os.environ["TV_SMTP_PASSWORD"])
  smtp.send_message(msg)
print("MAIL_SENT",flush=True)
