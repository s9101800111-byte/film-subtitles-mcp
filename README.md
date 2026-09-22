# subtitle-mcp

把**影片或音檔**轉成逐字稿與繁體中文字幕的 MCP server。

兩條路線：

| 音源 | 參數 | 產出 |
|---|---|---|
| 英文 | `language="en"`（預設） | `<檔名>.en.srt`（英文逐字稿）＋ `<檔名>.zh-TW.srt`（繁中字幕） |
| 中文 | `language="zh"` | `<檔名>.zh.srt`（原始轉錄）＋ `<檔名>.zh-TW.srt`（轉台灣繁體、校對錯字標點、拆長句） |

轉錄用 Groq Whisper，翻譯／校對預設也走 Groq——**只要一把免費的 Groq 金鑰就能全部跑完**，不必另外安裝任何 CLI。

## 設計原則

* 翻譯後端**永遠看不到時間軸**，只拿到一串編號句子，回傳同樣數量的譯文。數量對不上就重試、再不行拆小批重試，絕不「少一句也沒關係」。
* 組回字幕時用的是逐字稿原本的時間軸；寫檔後再讀回來逐條比對，時間軸一個字元都不能變。
* 中途斷掉（網路、配額、關機）直接重跑，已完成的切片與翻譯批次會跳過。

## 需要什麼

1. **ffmpeg / ffprobe**
   - Windows：`winget install Gyan.FFmpeg`
   - macOS：`brew install ffmpeg`
   - 裝完重開終端機。
2. **Groq 金鑰**（免費）：到 <https://console.groq.com/keys> 申請，等一下填進設定檔。

裝好之後可以先叫 `check_setup` 這支 tool 自我檢查。

## 安裝

不用 clone，直接讓 `uvx` 跑（需要 [uv](https://docs.astral.sh/uv/)）。把下面這段加進你的 MCP 設定檔：

```json
{
  "mcpServers": {
    "subtitle": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/s9101800111-byte/subtitle-mcp@v0.1.0", "subtitle-mcp"],
      "env": { "GROQ_API_KEY": "把你自己的金鑰貼在這裡" }
    }
  }
}
```

> `@v0.1.0` 是版本標籤，**建議釘住**。不釘版本的話上游一更新就可能整支掛掉。

設定檔位置：
- Claude Desktop（Windows）：`%APPDATA%\Claude\claude_desktop_config.json`
- Claude Code：專案或使用者層級的 `.mcp.json`

要改程式碼就照一般方式 clone 下來：

```bash
git clone https://github.com/s9101800111-byte/subtitle-mcp
cd subtitle-mcp
uv sync
uv run subtitle-mcp
```

## 工具

| Tool | 用途 |
|---|---|
| `transcribe_start(paths, language, translate, translator, model, context, force)` | 開始轉字幕，**立刻回傳 `job_id`**（實際工作在背景跑） |
| `transcribe_status(job_id)` | 查進度、產出的字幕檔路徑、最近的執行訊息 |
| `transcribe_list()` | 列出最近的工作 |
| `check_setup()` | 檢查 ffmpeg 與金鑰是否齊備 |

轉字幕是長時間工作（一小時影片約數分鐘），所以拆成 start／status 兩段，不會卡住對話。

### 用起來像這樣

> 「把 `D:\錄音\會議.m4a` 轉成逐字稿」
> 「這支英文影片上中文字幕，專有名詞有 Revit 和 Dynamo」

`context` 參數填上專有名詞（例如 `"Revit, Dynamo, MCP"`）能讓譯名穩定很多。

## 常見問題

**「整部影片沒有轉出任何語音」** — 檔案真的沒有聲音，或截到了靜音片段。用 `ffmpeg -i 檔案 -af volumedetect -f null -` 確認。

**音檔可以直接丟資料夾嗎？** 可以。`.mp3 .m4a .wav .aac .flac .ogg .opus .wma` 與常見影片格式都會被掃到。

**免費額度會卡嗎？** Groq 免費層有每分鐘 token 限制，長片翻譯時可能遇到 429。程式會自己等待重試，重跑也會從中斷處接續。

**想換翻譯模型？** `model` 參數可填任何 Groq 上的模型，例如 `qwen/qwen3.8-27b`。預設是 `openai/gpt-oss-120b`（指令遵循最穩，這條 pipeline 最吃這個）。

**想用自己的 CLI agent 翻譯？** `translator` 填那支指令的名字（需支援 `-p <prompt> --model <model>`），例如 `agy`、`claude`。

## 授權

MIT
