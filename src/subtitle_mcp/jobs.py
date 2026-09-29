"""背景 job：轉字幕動輒好幾分鐘，MCP 呼叫不能站在那裡等。

一支 job 一個資料夾（~/.subtitle-mcp/jobs/<id>/），裡面是 state.json 與 log.txt。
狀態寫在檔案裡而不是只存在記憶體，server 重啟後還查得到上次跑到哪。
"""

from __future__ import annotations

import json
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path

from . import subtitle
from .translators import DEFAULT_GROQ_MODEL, make_agent

JOBS_DIR = Path.home() / ".subtitle-mcp" / "jobs"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def _write_state(job_id: str, **fields) -> None:
    d = job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "state.json"
    state = {}
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    state.update(fields)
    state["job_id"] = job_id
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def read_state(job_id: str) -> dict | None:
    path = job_dir(job_id) / "state.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def list_jobs(limit: int = 20) -> list[dict]:
    if not JOBS_DIR.exists():
        return []
    out = []
    for d in sorted(JOBS_DIR.iterdir(), key=lambda p: p.name, reverse=True)[:limit]:
        st = read_state(d.name)
        if st:
            out.append(st)
    return out


def tail_log(job_id: str, lines: int = 30) -> str:
    path = job_dir(job_id) / "log.txt"
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(text[-lines:])


def start(paths: list[str], *, groq_key: str, language: str = "en", translate: bool = True,
          translator: str = "groq", model: str | None = None, context: str = "",
          force: bool = False) -> str:
    """開一支背景 job，立刻回傳 job_id。"""
    job_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)
    log_path = d / "log.txt"

    use_model = model or (DEFAULT_GROQ_MODEL if translator == "groq" else subtitle.DEFAULT_MODEL)
    _write_state(job_id, status="queued", paths=paths, language=language,
                 translate=translate, translator=translator, model=use_model,
                 started_at=_now(), finished_at=None, error=None, outputs=[])

    def log(msg: str) -> None:
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(str(msg) + "\n")

    def work() -> None:
        _write_state(job_id, status="running")
        try:
            opts = subtitle.SrtOptions(
                groq_key=groq_key, model=use_model, translator=translator,
                context=context, language=language, translate=translate, force=force,
                agent=make_agent(translator, groq_key, log) if translate else None,
            )
            rc, outputs = subtitle.run(paths, opts, log)
            _write_state(job_id, status="done" if rc == 0 else "partial",
                         finished_at=_now(), outputs=outputs)
        except Exception as exc:  # 背景執行緒吞掉例外等於靜默失敗，一律寫進狀態
            log(f"FAILED: {exc}")
            log(traceback.format_exc())
            _write_state(job_id, status="failed", finished_at=_now(), error=str(exc), outputs=[])

    threading.Thread(target=work, daemon=True, name=f"subtitle-{job_id}").start()
    return job_id
