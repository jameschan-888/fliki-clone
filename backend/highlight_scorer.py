"""P8-Highlight: 短视频高光评分 (借鉴 autoclip step3_scoring)

思路源自 debpalash/OmniVoice-Studio 同赛道 zhouxiaoka/autoclip 的 step3_scoring.py:
LLM 当评分员, 批量评估一组视频切片, 返回 (score, reason) 列表.

Fliki 适配:
- 输入: autoedit_segments 表行 (id, subtitle, text, start_seconds, end_seconds)
- 输出: 每个 segment 加 highlight_score / highlight_reason / highlight_scored_at
- LLM 协议: OpenAI 兼容 chat/completions (MiniMax / OpenAI / OmniVoice / 任何兼容端点)
- 默认走 Mock (本地规则评分, 不依赖外部)

接口:
- HighlightScorer().score_segments(segments) -> list[HighlightScore]
- ensure_highlight_columns(conn) -> None (幂等 DB 迁移)
- apply_highlight_scores(conn, draft_id, scores) -> int (写回 DB)
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable
from pathlib import Path

logger = logging.getLogger(__name__)


HIGHLIGHT_PROMPT = """你是顶级的短视频内容编辑，擅长找出视频中最有"爆款"潜力的片段。

请对每个切片按 4 个核心维度综合评估：
1. 信息价值: 内容是否提供了独特的见解、知识或信息？信息密度是否高？
2. 情感共鸣: 内容是否能引发观众的强烈情感（喜悦、愤怒、好奇、共鸣）？观点是否鲜明？
3. 传播潜力: 内容是否包含易于传播的"金句"或有趣的"梗"？是否容易引发讨论和分享？
4. 结构完整性: 话题的讨论是否逻辑清晰、有始有终？

输入 JSON 数组（每个对象包含 id, subtitle, text, start_seconds, end_seconds）：
```json
[
  {"id": "seg_001", "subtitle": "...", "text": "...", "start_seconds": 10.5, "end_seconds": 25.8},
  ...
]
```

输出 JSON 数组（按输入 id 顺序，每个对象补 highlight_score 和 highlight_reason）：
```json
[
  {"id": "seg_001", "highlight_score": 0.85, "highlight_reason": "观点犀利，信息密度高，强烈共鸣。"},
  ...
]
```

要求：
- highlight_score 为 0.0-1.0 浮点数，保留 2 位小数。
- highlight_reason 为 15-30 字中文推荐理由，精准诱人，体现话题最核心亮点。
- 严格按输入 id 顺序返回，元素数量必须一致。
- 只输出 JSON 数组，无任何其他文字。
"""


@dataclass
class HighlightScore:
    segment_id: str
    score: float
    reason: str

    def to_dict(self) -> dict:
        return {"segment_id": self.segment_id, "score": round(self.score, 2), "reason": self.reason}


# ===== DB schema =====

HIGHLIGHT_COLUMNS_DDL = [
    "ALTER TABLE autoedit_segments ADD COLUMN highlight_score REAL",
    "ALTER TABLE autoedit_segments ADD COLUMN highlight_reason TEXT",
    "ALTER TABLE autoedit_segments ADD COLUMN highlight_scored_at TEXT",
]


def ensure_highlight_columns(conn: sqlite3.Connection) -> None:
    """幂等迁移: 给 autoedit_segments 加 3 列 (P8). 老 DB 也能跑."""
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(autoedit_segments)").fetchall()}
    additions = []
    if "highlight_score" not in cols:
        additions.append("ALTER TABLE autoedit_segments ADD COLUMN highlight_score REAL")
    if "highlight_reason" not in cols:
        additions.append("ALTER TABLE autoedit_segments ADD COLUMN highlight_reason TEXT")
    if "highlight_scored_at" not in cols:
        additions.append("ALTER TABLE autoedit_segments ADD COLUMN highlight_scored_at TEXT")
    for ddl in additions:
        conn.execute(ddl)
    if additions:
        conn.commit()


# ===== LLM 客户端 =====

class HighlightLLMError(RuntimeError):
    pass


class BaseLLMClient:
    def chat(self, prompt: str, input_data: list) -> str:
        raise NotImplementedError


class MockHighlightLLM(BaseLLMClient):
    """本地规则评分: 不依赖外部 API. 用于 CI / 离线 / 默认 fallback.

    评分规则 (启发式, 跟 autoclip 的 prompt 维度对齐):
      - 信息价值: 字幕长度 30-150 字最佳
      - 情感共鸣: 含情感词 / 感叹号 / 反问加分
      - 传播潜力: 含数字 / "金句"模式 (短句 + 引号) 加分
      - 结构完整性: 时长 5-30 秒最佳
    """
    EMOTION_WORDS = ("惊喜", "震撼", "不可思议", "太", "真的", "竟然", "没想到", "突破", "颠覆", "关键", "核心", "秘密", "真相")
    QUOTE_PATTERN = re.compile(r"[「\"''].+?[」\"'']")

    def chat(self, prompt: str, input_data: list) -> str:
        results = []
        for item in input_data:
            subtitle = (item.get("subtitle") or item.get("text") or "").strip()
            duration = float(item.get("end_seconds", 0)) - float(item.get("start_seconds", 0))

            # 信息价值
            length = len(subtitle)
            if 30 <= length <= 150:
                info = 0.85
            elif 15 <= length <= 200:
                info = 0.65
            else:
                info = 0.40

            # 情感共鸣
            emotion_hits = sum(1 for w in self.EMOTION_WORDS if w in subtitle)
            if "!" in subtitle or "！" in subtitle or "?" in subtitle or "？" in subtitle:
                emotion_hits += 1
            emotion = min(0.95, 0.40 + emotion_hits * 0.15)

            # 传播潜力
            has_number = bool(re.search(r"\d", subtitle))
            has_quote = bool(self.QUOTE_PATTERN.search(subtitle))
            spread = 0.50 + (0.15 if has_number else 0) + (0.20 if has_quote else 0)

            # 结构完整性
            if 5.0 <= duration <= 30.0:
                structure = 0.85
            elif 3.0 <= duration <= 60.0:
                structure = 0.65
            else:
                structure = 0.40

            score = round((info * 0.3 + emotion * 0.3 + spread * 0.25 + structure * 0.15), 2)
            score = max(0.0, min(1.0, score))

            # 推荐理由
            reasons = []
            if info >= 0.80:
                reasons.append("信息密度高")
            if emotion >= 0.80:
                reasons.append("情感共鸣强")
            if has_quote:
                reasons.append("含金句")
            elif has_number:
                reasons.append("数据支撑")
            if 5 <= duration <= 30:
                reasons.append("节奏紧凑")
            if not reasons:
                reasons.append("内容完整可保留")
            reason = "，".join(reasons[:3]) + "，值得作为高光片段。"

            results.append({"id": item.get("id"), "highlight_score": score, "highlight_reason": reason})
        return json.dumps(results, ensure_ascii=False)


class OpenAICompatibleLLM(BaseLLMClient):
    """OpenAI 兼容 chat/completions 客户端 (MiniMax / OpenAI / OmniVoice 都走这个).

    环境变量:
      HIGHLIGHT_LLM_BASE_URL  e.g. https://api.minimaxi.com 或 http://127.0.0.1:3900/v1
      HIGHLIGHT_LLM_API_KEY   Bearer token (OmniVoice 可空)
      HIGHLIGHT_LLM_MODEL     e.g. MiniMax-Text-01 / gpt-4o-mini / omnivoice-llm
    """

    def __init__(self, base_url: str, api_key: str | None = None, model: str = "gpt-4o-mini", timeout: float = 60.0):
        import httpx
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, prompt: str, input_data: list) -> str:
        import httpx
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(input_data, ensure_ascii=False)},
            ],
            "temperature": 0.3,
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise HighlightLLMError(f"LLM HTTP error: {exc}") from exc
        if resp.status_code != 200:
            raise HighlightLLMError(f"LLM failed (status={resp.status_code}): {(resp.text or '')[:300]}")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise HighlightLLMError(f"LLM malformed response: {exc}") from exc


def build_default_llm() -> BaseLLMClient:
    """按环境变量选择 LLM 客户端. 未配置 -> Mock."""
    provider = os.getenv("HIGHLIGHT_LLM_PROVIDER", "mock").lower()
    if provider == "mock" or not provider or provider == "disabled":
        return MockHighlightLLM()
    if provider in ("openai", "minimax", "omnivoice", "custom"):
        base_url = os.getenv("HIGHLIGHT_LLM_BASE_URL")
        if not base_url:
            logger.warning("HIGHLIGHT_LLM_PROVIDER=%s 但 HIGHLIGHT_LLM_BASE_URL 未配置, 走 Mock", provider)
            return MockHighlightLLM()
        return OpenAICompatibleLLM(
            base_url=base_url,
            api_key=os.getenv("HIGHLIGHT_LLM_API_KEY"),
            model=os.getenv("HIGHLIGHT_LLM_MODEL", "gpt-4o-mini"),
        )
    logger.warning("未知 HIGHLIGHT_LLM_PROVIDER=%s, 走 Mock", provider)
    return MockHighlightLLM()


# ===== 评分器 =====

class HighlightScorer:
    def __init__(self, llm: BaseLLMClient | None = None, batch_size: int = 8):
        self.llm = llm or build_default_llm()
        self.batch_size = max(1, batch_size)

    def _parse_scores(self, raw: str, expected_ids: list[str]) -> list[HighlightScore]:
        """从 LLM 输出解析 HighlightScore 列表. 失败 -> 走 Mock 兜底."""
        try:
            # LLM 可能包 ```json ... ```, 剥掉
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)
            if not isinstance(data, list):
                raise ValueError("LLM output is not a list")
            id_to_score = {}
            for item in data:
                seg_id = item.get("id")
                score = float(item.get("highlight_score", 0))
                reason = str(item.get("highlight_reason", "")).strip()
                if seg_id:
                    id_to_score[seg_id] = (score, reason)
            return [
                HighlightScore(
                    segment_id=sid,
                    score=id_to_score.get(sid, (0.0, "评分缺失"))[0],
                    reason=id_to_score.get(sid, (0.0, "评分缺失"))[1],
                )
                for sid in expected_ids
            ]
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("LLM 输出解析失败 (%s), 走 Mock 兜底", exc)
            mock = MockHighlightLLM().chat(HIGHLIGHT_PROMPT, [{"id": sid, "subtitle": "", "start_seconds": 0, "end_seconds": 1} for sid in expected_ids])
            return self._parse_scores(mock, expected_ids)

    def score_segments(self, segments: Iterable[dict]) -> list[HighlightScore]:
        """批量评分. 自动按 batch_size 分批."""
        seg_list = list(segments)
        if not seg_list:
            return []
        all_scores: list[HighlightScore] = []
        for i in range(0, len(seg_list), self.batch_size):
            batch = seg_list[i : i + self.batch_size]
            input_data = [
                {
                    "id": seg.get("id"),
                    "subtitle": (seg.get("subtitle") or seg.get("text") or "").strip(),
                    "text": (seg.get("text") or "").strip(),
                    "start_seconds": float(seg.get("start_seconds") or 0),
                    "end_seconds": float(seg.get("end_seconds") or 0),
                }
                for seg in batch
            ]
            expected_ids = [seg["id"] for seg in input_data]
            try:
                raw = self.llm.chat(HIGHLIGHT_PROMPT, input_data)
                scores = self._parse_scores(raw, expected_ids)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LLM 评分失败 (%s), 用 Mock 兜底", exc)
                raw = MockHighlightLLM().chat(HIGHLIGHT_PROMPT, input_data)
                scores = self._parse_scores(raw, expected_ids)
            all_scores.extend(scores)
        return all_scores


def apply_highlight_scores(conn: sqlite3.Connection, draft_id: str, scores: list[HighlightScore]) -> int:
    """写回 DB. 返回成功写入行数."""
    ensure_highlight_columns(conn)
    ts = datetime.now(timezone.utc).isoformat()
    written = 0
    for s in scores:
        cur = conn.execute(
            "UPDATE autoedit_segments SET highlight_score=?, highlight_reason=?, highlight_scored_at=? "
            "WHERE id=? AND autoedit_draft_id=?",
            (s.score, s.reason, ts, s.segment_id, draft_id),
        )
        written += cur.rowcount
    conn.commit()
    return written


def score_draft(conn: sqlite3.Connection, draft_id: str, llm: BaseLLMClient | None = None) -> int:
    """一键评分: 读 segments -> 评 -> 写回. 返回写入行数."""
    ensure_highlight_columns(conn)
    rows = conn.execute(
        "SELECT id, subtitle, text, start_seconds, end_seconds FROM autoedit_segments "
        "WHERE autoedit_draft_id=? ORDER BY position",
        (draft_id,),
    ).fetchall()
    if not rows:
        return 0
    segments = [dict(r) for r in rows]
    scorer = HighlightScorer(llm=llm)
    scores = scorer.score_segments(segments)
    return apply_highlight_scores(conn, draft_id, scores)
