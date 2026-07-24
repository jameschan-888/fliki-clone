import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import edge_tts
from fastapi import APIRouter, HTTPException, Query


VOICE_COLUMNS = (
    "ShortName", "Gender", "Locale", "FriendlyName",
    "SuggestedCodec", "Status", "VoiceType",
)


def now_epoch():
    return int(time.time())


async def fetch_edge_voices():
    voices = await edge_tts.list_voices()
    return [
        {column: voice.get(column) for column in VOICE_COLUMNS}
        for voice in voices
        if voice.get("ShortName")
    ]


def replace_voices(connection, voices):
    fetched_at = now_epoch()
    connection.execute("DELETE FROM edge_voices")
    connection.executemany(
        "INSERT INTO edge_voices "
        "(ShortName, Gender, Locale, FriendlyName, SuggestedCodec, Status, VoiceType, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [tuple(voice.get(column) for column in VOICE_COLUMNS) + (fetched_at,) for voice in voices],
    )
    connection.commit()
    return len(voices)


def run_async(coroutine):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coroutine).result()


def refresh_voices(connection):
    return replace_voices(connection, run_async(fetch_edge_voices()))


def ensure_voices(connection):
    count = connection.execute("SELECT COUNT(*) FROM edge_voices").fetchone()[0]
    return count if count else refresh_voices(connection)


def voice_payload(row):
    return {key: row[key] for key in (*VOICE_COLUMNS, "fetched_at")}


def create_router(get_db, preview_dir=None):
    router = APIRouter(prefix="/voices", tags=["voices"])
    preview_root = Path(preview_dir or Path(__file__).parent / "data" / "voice_previews")
    preview_root.mkdir(parents=True, exist_ok=True)

    @router.get("")
    def list_voices(
        locale: str | None = None,
        gender: str | None = None,
        search: str | None = Query(default=None, max_length=200),
    ):
        clauses = []
        parameters = []
        if locale:
            clauses.append("Locale = ?")
            parameters.append(locale)
        if gender:
            clauses.append("Gender = ?")
            parameters.append(gender)
        if search:
            clauses.append("(ShortName LIKE ? OR FriendlyName LIKE ? OR Locale LIKE ?)")
            term = f"%{search.strip()}%"
            parameters.extend([term, term, term])
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        connection = get_db()
        try:
            rows = connection.execute(
                f"SELECT * FROM edge_voices{where} ORDER BY Locale, FriendlyName, ShortName",
                parameters,
            ).fetchall()
            return [voice_payload(row) for row in rows]
        finally:
            connection.close()

    @router.get("/locales")
    def list_locales():
        connection = get_db()
        try:
            rows = connection.execute(
                "SELECT Locale AS locale, COUNT(*) AS count FROM edge_voices "
                "GROUP BY Locale ORDER BY Locale"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    @router.get("/{short_name}/preview")
    def preview_voice(short_name: str, text: str = Query(default="你好世界", min_length=1, max_length=200)):
        connection = get_db()
        try:
            voice = connection.execute(
                "SELECT ShortName FROM edge_voices WHERE ShortName = ?", (short_name,)
            ).fetchone()
        finally:
            connection.close()
        if voice is None:
            raise HTTPException(status_code=404, detail="Voice not found")
        normalized_text = text.strip()[:200]
        destination = preview_root / f"{short_name}.mp3"
        try:
            asyncio.run(edge_tts.Communicate(normalized_text, short_name).save(str(destination)))
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=502, detail=f"Edge TTS preview failed: {exc}") from exc
        if not destination.exists() or destination.stat().st_size <= 1024:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=502, detail="Edge TTS preview returned empty audio")
        return {
            "ShortName": short_name,
            "text": normalized_text,
            "audio_url": f"/voice-previews/{quote(destination.name)}",
            "size_bytes": destination.stat().st_size,
        }

    @router.post("/refresh")
    def refresh():
        connection = get_db()
        try:
            count = refresh_voices(connection)
            return {"count": count, "fetched_at": now_epoch()}
        except Exception as exc:
            connection.rollback()
            raise HTTPException(status_code=502, detail=f"Unable to refresh Edge voices: {exc}") from exc
        finally:
            connection.close()

    return router
