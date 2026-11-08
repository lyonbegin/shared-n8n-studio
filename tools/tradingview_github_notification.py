#!/usr/bin/env python3
"""Report finished TradingView crawl through GitHub's native issue notifications.

Runs in a workflow_run completion listener, not from a schedule.
Creates an assigned issue (not SMTP), and will not duplicate an issue mentioning
the same Actions run. GitHub email delivery follows repository notification settings.
"""
import json
import os
import pathlib
import subprocess

REPO = os.environ.get("GITHUB_REPOSITORY", "lyonbegin/shared-n8n-studio")
OWNER = REPO.split("/", 1)[0]
EVENT_FILE = pathlib.Path(os.environ["GITHUB_EVENT_PATH"])
EVENT = json.loads(EVENT_FILE.read_text(encoding="utf-8"))
RUN = EVENT["workflow_run"]
RUN_ID = str(RUN["id"])
RUN_URL = RUN["html_url"]
CONCLUSION = RUN.get("conclusion") or "unknown"
REPO = RUN.get("repository", {}).get("full_name") or REPO
OWNER = REPO.split("/",1)[0]

def gh(*args,check=True):
    p=subprocess.run(["gh",*args],text=True,capture_output=True,check=check)
    return p.stdout

# An earlier in-flight job may have created a native GitHub issue before this
# listener was added. Check issue bodies by Actions URL, avoiding duplicate notices.
existing = json.loads(gh("issue","list","-R",REPO,"--state","all",
                         "--limit","500","--json","number,title,body"))
for issue in existing:
    if RUN_URL in (issue.get("body") or ""):
        print("EXISTING_NATIVE_NOTIFICATION", issue["number"], flush=True)
        raise SystemExit(0)

report_file = pathlib.Path("recursive_result/manifest.json")
report = json.loads(report_file.read_text(encoding="utf-8")) if report_file.exists() else None
if report:
    counts=f"Strategy {report.get('strategies', '?')} / Indicator {report.get('indicators', '?')}"
    state=report.get("state") or "UNKNOWN"
    rows=[
        f"재귀 수집 작업 상태: **{state}**",
        f"GitHub Actions 결과: **{CONCLUSION}**",
        f"수집 건수: **{counts}**",
        f"처리한 제작자: **{report.get('authors_processed','?')}명**",
        f"신규 전략: **{report.get('new_strategies','?')}개**",
        f"신규 지표: **{report.get('new_indicators','?')}개**",
        f"남은 제작자 대기열: **{report.get('pending_authors','?')}명**",
        f"오류: **{report.get('error_count','?')}건**"
    ]
else:
    state="NO_MANIFEST"
    rows=["최종 manifest.json을 확보하지 못해 수집 건수를 검증할 수 없습니다.",
          f"GitHub Actions 결과: **{CONCLUSION}**"]
ok = CONCLUSION=="success" and state=="FRONTIER_EXHAUSTED"
title = (f"[TradingView] 신규 제작자 대기열 소진 - {counts}" if ok else
         f"[TradingView] 재귀 수집 미완료/실패 - run {RUN_ID}")
body=("\n".join(rows)+"\n\n실행 기록: "+RUN_URL+
      "\n\n수집 파일: "+RUN_URL+
      "\n\n이 알림은 GitHub 이슈 할당 기능으로 생성되었습니다. 메일 수신은 GitHub 알림 설정에 따릅니다.\n")
# Assigning the repository owner generates a GitHub native account notification.
print(gh("issue","create","-R",REPO,"--title",title,"--body",body,"--assignee",OWNER))
print("GITHUB_NATIVE_ISSUE_NOTIFICATION_CREATED",RUN_ID,flush=True)
