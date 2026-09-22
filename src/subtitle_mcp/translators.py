"""翻譯後端：把一批編號句子送去翻譯／校對，回傳原始文字給 subtitle 解析。

所有後端共用 subtitle.translate_batch 要的簽章 (prompt, translator, model) -> str，
所以 subtitle.py 不需要知道後端是誰，只管把 agent 換掉。

* groq  ── 打 Groq chat completions，只要一把 GROQ_API_KEY（預設，分享給別人用最省事）
* CLI   ── 任何吃 `-p <prompt> --model <model>` 的指令（agy / claude / ...），沿用既有行為
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Callable

from .subtitle import SubtitleError, _ssl_context, call_agent

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

# 這條 pipeline 的硬約束是「回傳剛好 N 個字串的 JSON 陣列」，指令遵循失敗的代價最高，
# 所以預設挑指令遵循最穩的；中文語感偏好 qwen 的人可以自己換。
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

MAX_ATTEMPTS = 6


def groq_chat(prompt: str, api_key: str, model: str = DEFAULT_GROQ_MODEL,
              log: Callable[[str], None] = print) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode("utf-8")
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json",
               "User-Agent": "subtitle-mcp"}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(GROQ_CHAT_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300, context=_ssl_context()) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code == 401:
                raise SubtitleError("Groq 金鑰無效（401），請確認 GROQ_API_KEY") from exc
            if exc.code in (429, 500, 502, 503, 504):
                # 免費層是每分鐘 token 數在卡，不是請求數，等久一點比較實際
                wait = int(exc.headers.get("retry-after") or 0) or 20 * attempt
                log(f"    Groq {exc.code}，{wait} 秒後重試（第 {attempt} 次）")
                time.sleep(wait)
                continue
            raise SubtitleError(f"Groq 錯誤 {exc.code}：{detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            log(f"    連線問題（{exc}），20 秒後重試（第 {attempt} 次）")
            time.sleep(20)
    raise SubtitleError("Groq 連續失敗 6 次，稍後重跑即可從這裡接續（已完成的批次會跳過）")


def make_agent(backend: str, api_key: str | None,
               log: Callable[[str], None] = print) -> Callable[[str, str, str], str]:
    """回傳 subtitle.translate_batch 要的 agent。backend="groq" 或任何 CLI 指令名。"""
    if backend != "groq":
        return call_agent

    if not api_key:
        raise SubtitleError("翻譯後端是 groq，但沒有 Groq 金鑰（環境變數 GROQ_API_KEY）")

    def agent(prompt: str, translator: str, model: str) -> str:
        return groq_chat(prompt, api_key, model or DEFAULT_GROQ_MODEL, log)

    return agent
