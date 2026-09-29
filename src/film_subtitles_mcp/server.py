"""film-subtitles-mcp：影片／音檔轉逐字稿與繁體中文字幕的 MCP server。

轉字幕是長時間工作（一小時影片約數分鐘），所以拆成 start / status 兩段：
start 立刻回 job_id，實際工作在背景跑，用 status 查進度。
"""

from __future__ import annotations

import os
import shutil

from mcp.server.fastmcp import FastMCP

from . import jobs
from .translators import DEFAULT_GROQ_MODEL

mcp = FastMCP("film-subtitles-mcp")


def _groq_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise ValueError(
            "沒有 Groq 金鑰。到 https://console.groq.com/keys 免費申請，"
            "再把 GROQ_API_KEY 寫進 MCP 設定檔的 env 區塊。")
    return key


@mcp.tool()
def transcribe_start(
    paths: list[str],
    language: str = "en",
    translate: bool = True,
    translator: str = "groq",
    model: str = "",
    context: str = "",
    force: bool = False,
) -> dict:
    """把影片或音檔轉成字幕／逐字稿（開背景工作，立刻回傳 job_id）。

    用在：影片上字幕、音檔轉文字、錄音轉逐字稿、演講/會議/課程影片轉文字、翻譯成中文字幕。

    參數：
      paths      -- 影片或音檔的完整路徑，可給多個；也可以給整個資料夾。
      language   -- 音源語言。"en"＝英文（產生英文逐字稿再翻成繁中字幕）；
                    "zh"＝中文（直接產生繁中字幕，會轉台灣繁體並校對錯字標點）。
      translate  -- True＝要中文字幕；False＝只要原文逐字稿。
      translator -- "groq"（預設，只要 Groq 金鑰）或任何吃 `-p/--model` 的 CLI agent（例如 "agy"）。
      model      -- 翻譯模型，留空用預設。
      context    -- 本片的專有名詞或背景，例如 "Revit, Dynamo, MCP"，會讓譯名穩定。
      force      -- 字幕已存在也重做。

    產出會放在原檔案旁邊：<檔名>.en.srt（或 .zh.srt）與 <檔名>.zh-TW.srt。
    回傳 job_id，用 transcribe_status 查進度。
    """
    if not paths:
        raise ValueError("要至少給一個影片或音檔路徑")
    job_id = jobs.start(
        paths, groq_key=_groq_key(), language=language, translate=translate,
        translator=translator, model=model or None, context=context, force=force,
    )
    return {"job_id": job_id,
            "hint": "用 transcribe_status(job_id) 查進度；長片約數分鐘。"}


@mcp.tool()
def transcribe_status(job_id: str, log_lines: int = 30) -> dict:
    """查某支轉字幕工作的進度、產出的字幕檔路徑，以及最近的執行訊息。"""
    state = jobs.read_state(job_id)
    if state is None:
        raise ValueError(f"查不到這支工作：{job_id}（用 transcribe_list 看有哪些）")
    return {**state, "log": jobs.tail_log(job_id, log_lines)}


@mcp.tool()
def transcribe_list(limit: int = 20) -> list[dict]:
    """列出最近的轉字幕工作與各自狀態。"""
    return jobs.list_jobs(limit)


@mcp.tool()
def check_setup() -> dict:
    """檢查這台電腦的環境是否齊備（ffmpeg、Groq 金鑰、翻譯後端）。裝完先跑這個。"""
    ok_ffmpeg = bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe"))
    has_key = bool(os.environ.get("GROQ_API_KEY"))
    problems = []
    if not ok_ffmpeg:
        problems.append("缺 ffmpeg／ffprobe：Windows 用 `winget install Gyan.FFmpeg`，"
                        "macOS 用 `brew install ffmpeg`，裝完重開。")
    if not has_key:
        problems.append("缺 GROQ_API_KEY：到 https://console.groq.com/keys 免費申請，"
                        "寫進 MCP 設定檔的 env 區塊。")
    return {
        "ffmpeg": ok_ffmpeg,
        "groq_key": has_key,          # 只回報有沒有，不回傳金鑰內容
        "default_model": DEFAULT_GROQ_MODEL,
        "ready": not problems,
        "problems": problems,
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
