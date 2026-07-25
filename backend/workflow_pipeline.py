import json
import os
import shutil
import subprocess
import threading
import uuid
from datetime import datetime,timezone
from pathlib import Path

from fastapi import APIRouter,BackgroundTasks,HTTPException
from pydantic import BaseModel

from providers.music import FreesoundProvider
from providers.stock import fetch_with_fallback
from providers.tts import DEFAULT_VOICE, EdgeTTSProvider
from services.cadence import detect_voice_segments as cadence_detect, cadence_summary as cadence_summary_svc
from providers.avatar import build_wav2lip_provider, AVATAR_CLONE_PREFIX
from providers.base import ProviderError


def now(): return datetime.now(timezone.utc).isoformat()


def media_duration(path):
    result=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],capture_output=True,timeout=20)
    output=(result.stdout or b"").decode("utf-8",errors="replace").strip()
    return round(float(output),3) if result.returncode==0 and output else None


def synthesize_scene_voice(scene, destination):
    selected_voice = scene["voice"] or DEFAULT_VOICE
    return EdgeTTSProvider().synthesize(scene["narration"], destination, voice=selected_voice)


def _merge_avatar_layout(global_layout, scene_layout):
    if not isinstance(global_layout, dict):
        global_layout = None
    if not isinstance(scene_layout, dict):
        return global_layout
    if not global_layout:
        return scene_layout
    merged = dict(global_layout)
    for k, v in scene_layout.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = {**merged[k], **v}
        else:
            merged[k] = v
    return merged


def _load_avatar_layout(connection):
    if connection is None:
        return None
    try:
        row = connection.execute(
            "SELECT config_json FROM provider_configs WHERE category=? AND name=? LIMIT 1",
            ("avatar", "wav2lip_onnx"),
        ).fetchone()
    except Exception:
        return None
    if row is None or not row["config_json"]:
        return None
    try:
        config = json.loads(row["config_json"])
    except (TypeError, ValueError):
        return None
    if not isinstance(config, dict):
        return None
    extra = config.get("extra") if isinstance(config.get("extra"), dict) else {}
    layout = extra.get("avatar_layout")
    if not isinstance(layout, dict):
        layout = config.get("avatar_layout")
    return layout if isinstance(layout, dict) else None


def _fetch_avatar_clone(connection, avatar_token):
    if not avatar_token:
        return None
    if avatar_token.startswith(AVATAR_CLONE_PREFIX):
        avatar_uuid = avatar_token[len(AVATAR_CLONE_PREFIX):]
    else:
        avatar_uuid = avatar_token
    return connection.execute(
        "SELECT uuid, avatar_name, ref_face_path, default_audio_path, enabled FROM avatar_clones WHERE uuid=?",
        (avatar_uuid,),
    ).fetchone()


def synthesize_scene_avatar(scene, audio_source, destination, connection=None, config=None):
    """Render a Wav2Lip avatar MP4 for a scene. Returns provider-shaped dict.

    Falls back to a static-image FFmpeg MP4 when ONNX model or deps missing.
    """
    try:
        avatar_token = (scene["avatar"] or "").strip()
    except (KeyError, TypeError):
        avatar_token = ""
    if not avatar_token:
        return {"skipped": True, "reason": "no avatar selected"}
    if connection is not None:
        row = _fetch_avatar_clone(connection, avatar_token)
    else:
        row = None
    face_path = None
    if row and row["ref_face_path"]:
        face_path = row["ref_face_path"]
    if not face_path:
        return {"skipped": True, "reason": "avatar clone has no ref_face_path"}
    provider_kwargs = {}
    if config:
        provider_kwargs = dict(config)
    provider = build_wav2lip_provider(**provider_kwargs) if provider_kwargs else build_wav2lip_provider()
    try:
        result = provider.synthesize(
            face_image_path=face_path,
            audio_path=audio_source,
            destination_path=destination,
        )
        result["avatar_uuid"] = (row["uuid"] if row else avatar_token[len(AVATAR_CLONE_PREFIX):])
        result["avatar_name"] = row["avatar_name"] if row else avatar_token
        return result
    except ProviderError as exc:
        return {
            "provider": provider.name,
            "status": "failed",
            "reason": str(exc)[:500],
            "fallback_used": True,
            "local_path": None,
        }



def stage_asset(source_path, public_dir, stem):
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"Asset does not exist: {source}")
    destination_dir = Path(public_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    suffix = source.suffix.lower() or ".bin"
    destination = destination_dir / f"{stem}{suffix}"
    if destination.exists():
        if destination.stat().st_size == source.stat().st_size:
            return f"/public/{destination.name}"
        destination.unlink()
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    return f"/public/{destination.name}"


def node_payload(row):
    return {"id":row["id"],"scene_draft_id":row["scene_draft_id"],"node_type":row["node_type"],"status":row["status"],"progress":row["progress"],"provider":row["provider"],"attempt":row["attempt"],"result":json.loads(row["result_json"] or "null"),"message":row["message"]}


def run_payload(connection,run_id):
    row=connection.execute("SELECT * FROM workflow_runs WHERE id=?",(run_id,)).fetchone()
    if row is None: raise HTTPException(status_code=404,detail="Workflow run not found")
    nodes=connection.execute("SELECT * FROM workflow_nodes WHERE workflow_run_id=? ORDER BY created_at,id",(run_id,)).fetchall()
    return {"id":row["id"],"workflow_draft_id":row["workflow_draft_id"],"status":row["status"],"progress":row["progress"],"render_job_id":row["render_job_id"],"message":row["message"],"nodes":[node_payload(node) for node in nodes],"created_at":row["created_at"],"updated_at":row["updated_at"],"finished_at":row["finished_at"]}


def ensure_node(connection,run_id,scene_id,node_type,input_data):
    row=connection.execute("SELECT * FROM workflow_nodes WHERE workflow_run_id=? AND scene_draft_id IS ? AND node_type=?",(run_id,scene_id,node_type)).fetchone()
    if row:return row
    node_id=uuid.uuid4().hex;timestamp=now()
    connection.execute("INSERT INTO workflow_nodes (id,workflow_run_id,scene_draft_id,node_type,status,progress,input_json,created_at,updated_at) VALUES (?,?,?,?, 'queued',0,?,?,?)",(node_id,run_id,scene_id,node_type,json.dumps(input_data,ensure_ascii=False),timestamp,timestamp));connection.commit()
    return connection.execute("SELECT * FROM workflow_nodes WHERE id=?",(node_id,)).fetchone()


def complete_node(connection,node_id,provider,result):
    connection.execute("UPDATE workflow_nodes SET status='success',progress=100,provider=?,result_json=?,message=NULL,updated_at=?,finished_at=? WHERE id=?",(provider,json.dumps(result,ensure_ascii=False),now(),now(),node_id));connection.commit()


def run_node(connection,node,work):
    if node["status"]=="success" and node["result_json"]:return json.loads(node["result_json"])
    connection.execute("UPDATE workflow_nodes SET status='processing',progress=10,attempt=attempt+CASE WHEN status='failed' THEN 1 ELSE 0 END,message=NULL,updated_at=? WHERE id=?",(now(),node["id"]));connection.commit()
    try:
        provider,result=work();complete_node(connection,node["id"],provider,result);return result
    except Exception as error:
        connection.execute("UPDATE workflow_nodes SET status='failed',message=?,updated_at=?,finished_at=? WHERE id=?",(str(error)[:2000],now(),now(),node["id"]));connection.commit();raise


def upsert_asset(connection,run_id,scene_id,asset_type,result):
    connection.execute("INSERT OR REPLACE INTO scene_assets (id,workflow_run_id,scene_draft_id,asset_type,provider,source_url,local_path,duration_seconds,attribution_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",(uuid.uuid4().hex,run_id,scene_id,asset_type,result["provider"],result.get("source_url"),result["local_path"],result.get("duration_seconds"),json.dumps({key:result.get(key) for key in ("page_url","creator","license")},ensure_ascii=False),now()));connection.commit()


def enrich_voice_with_cadence(tts_result):
    """给 TTS 结果附加 cadence 段信息；失败则填零计数。

    借鉴灵剪 capabilities/cadence 思路。段起点列表不写入数据库 JSON，
    只保留前 64 段，足够前端展示与对齐判断。
    """
    if not isinstance(tts_result, dict):
        return tts_result
    audio_path = tts_result.get("local_path")
    if not audio_path:
        tts_result.setdefault("cadence_segments", [])
        tts_result["cadence_summary"] = {"count": 0, "avg_silence": 0.0, "max_silence": 0.0}
        return tts_result
    try:
        segments = cadence_detect(audio_path)
        tts_result["cadence_segments"] = segments[:64]
        tts_result["cadence_summary"] = cadence_summary_svc(segments)
    except Exception:
        tts_result.setdefault("cadence_segments", [])
        tts_result["cadence_summary"] = {"count": 0, "avg_silence": 0.0, "max_silence": 0.0}
    return tts_result


def execute_pipeline(run_id,get_db,render_create,render_body_class,background_tasks,preview=False):
    connection=get_db();run=connection.execute("SELECT * FROM workflow_runs WHERE id=?",(run_id,)).fetchone()
    try:
        connection.execute("UPDATE workflow_runs SET status='generating_assets',progress=5,updated_at=? WHERE id=?",(now(),run_id));connection.commit()
        draft=connection.execute("SELECT * FROM workflow_drafts WHERE id=?",(run["workflow_draft_id"],)).fetchone()
        scenes=connection.execute("SELECT * FROM scene_drafts WHERE workflow_draft_id=? ORDER BY position",(draft["id"],)).fetchall()
        run_dir=Path(__file__).parent/"data"/"workflow_runs"/run_id;run_dir.mkdir(parents=True,exist_ok=True)
        public_dir=run_dir/"remotion_public";public_dir.mkdir(parents=True,exist_ok=True)
        rendered_scenes=[]
        for index,scene in enumerate(scenes):
            scene_dir=run_dir/scene["id"];scene_dir.mkdir(parents=True,exist_ok=True)
            selected_voice=scene["voice"] or DEFAULT_VOICE
            tts_node=ensure_node(connection,run_id,scene["id"],"tts",{"text":scene["narration"],"voice":selected_voice})
            tts=run_node(connection,tts_node,lambda:("edge_tts",synthesize_scene_voice(scene,scene_dir/"voice.mp3")));tts["duration_seconds"]=media_duration(tts["local_path"]);upsert_asset(connection,run_id,scene["id"],"voice",tts)
            enrich_voice_with_cadence(tts)
            upsert_asset(connection,run_id,scene["id"],"voice",tts)
            audio_src=stage_asset(tts["local_path"],public_dir,f"scene-{index}-voice")
            avatar_src=None;avatar_meta=None
            if scene["avatar"] and not preview:
                avatar_node=ensure_node(connection,run_id,scene["id"],"avatar",{"avatar":scene["avatar"],"driven_by":"tts"})
                avatar_meta=run_node(connection,avatar_node,lambda:("wav2lip_onnx",synthesize_scene_avatar(scene,tts["local_path"],scene_dir/"avatar.mp4",connection=connection)))
                if avatar_meta.get("local_path") and Path(avatar_meta["local_path"]).is_file():
                    avatar_src=stage_asset(avatar_meta["local_path"],public_dir,f"scene-{index}-avatar")
                    upsert_asset(connection,run_id,scene["id"],"avatar",{"provider":avatar_meta.get("provider") or "wav2lip_onnx","local_path":avatar_meta["local_path"],"duration_seconds":tts.get("duration_seconds"),"source_url":None})
            stock_node=ensure_node(connection,run_id,scene["id"],"stock",{"query":scene["visual_intent"]})
            stock=run_node(connection,stock_node,lambda:(lambda result:(result["provider"],result))(fetch_with_fallback(scene["visual_intent"],scene_dir/"stock.mp4")));upsert_asset(connection,run_id,scene["id"],"stock",stock)
            video_src=stage_asset(stock["local_path"],public_dir,f"scene-{index}-stock")
            rendered_scenes.append({"id":scene["id"],"title":scene["title"],"subtitle":scene["subtitle"],"durationInSeconds":tts.get("duration_seconds") or scene["duration_seconds"],"videoSrc":video_src,"audioSrc":audio_src,"avatarSrc":avatar_src,"avatarFallback":bool(avatar_meta and avatar_meta.get("fallback_used")),"avatarMode":(avatar_meta or {}).get("mode"),"avatarName":(avatar_meta or {}).get("avatar_name"),"avatarLayout":None})
            connection.execute("UPDATE workflow_runs SET progress=?,updated_at=? WHERE id=?",(10+int(55*(index+1)/len(scenes)),now(),run_id));connection.commit()
        music_node=ensure_node(connection,run_id,None,"music",{"query":"calm cinematic background music"})
        music=run_node(connection,music_node,lambda:("freesound",FreesoundProvider().fetch("calm cinematic background music",run_dir/"music.mp3")))
        global_avatar_layout=_load_avatar_layout(connection)
        for rs, sc in zip(rendered_scenes, scenes):
            sc_layout_raw = sc["avatar_layout"]
            try: sc_layout = json.loads(sc_layout_raw) if sc_layout_raw else None
            except Exception: sc_layout = None
            rs["avatarLayout"] = _merge_avatar_layout(global_avatar_layout, sc_layout)
        music["duration_seconds"]=media_duration(music["local_path"]);upsert_asset(connection,run_id,scenes[0]["id"],"music",music)
        music_src=stage_asset(music["local_path"],public_dir,"background-music")
        props={"title":draft["title"],"subtitle":"","durationInSeconds":sum(scene["durationInSeconds"] for scene in rendered_scenes),"primaryColor":"#ffffff","backgroundColor":"#111827","scenes":rendered_scenes,"musicSrc":music_src,"musicVolume":0.12,"_publicDir":str(public_dir),"avatarLayout":global_avatar_layout}
        props_path=Path(__file__).parent/"data"/"props"/f"workflow-{run_id}.json";props_path.parent.mkdir(parents=True,exist_ok=True);props_path.write_text(json.dumps(props,ensure_ascii=False),encoding="utf-8")
        render_node=ensure_node(connection,run_id,None,"render",{"props_path":str(props_path)})
        connection.execute("UPDATE workflow_nodes SET status='processing',progress=5,provider='remotion',updated_at=? WHERE id=?",(now(),render_node["id"]));connection.execute("UPDATE workflow_runs SET status='rendering',progress=70,updated_at=? WHERE id=?",(now(),run_id));connection.commit()
        resolution="480p" if preview else "720p"
        response=render_create(render_body_class(playback_id=f"workflow-{run_id}",props_path=str(props_path),resolution=resolution),background_tasks)
        connection.execute("UPDATE workflow_runs SET render_job_id=?,progress=75,updated_at=? WHERE id=?",(response["jobId"],now(),run_id));connection.execute("UPDATE workflow_nodes SET result_json=? WHERE id=?",(json.dumps(response),render_node["id"]));connection.commit()
    except Exception as error:
        connection.execute("UPDATE workflow_runs SET status='failed',message=?,updated_at=?,finished_at=? WHERE id=?",(str(error)[:2000],now(),now(),run_id));connection.commit()
    finally:connection.close()


def sync_render(connection,run):
    if run["status"]!="rendering" or not run["render_job_id"]:return
    render=connection.execute("SELECT * FROM render_jobs WHERE _id=?",(run["render_job_id"],)).fetchone()
    if not render:return
    mapped=75+int(render["progress"]*.25)
    if render["status"]=="success":
        connection.execute("UPDATE workflow_runs SET status='success',progress=100,message=NULL,updated_at=?,finished_at=? WHERE id=?",(now(),now(),run["id"]));connection.execute("UPDATE workflow_nodes SET status='success',progress=100,finished_at=?,updated_at=? WHERE workflow_run_id=? AND node_type='render'",(now(),now(),run["id"]))
    elif render["status"]=="failed":
        connection.execute("UPDATE workflow_runs SET status='failed',message=?,updated_at=?,finished_at=? WHERE id=?",(render["message"],now(),now(),run["id"]));connection.execute("UPDATE workflow_nodes SET status='failed',message=?,finished_at=?,updated_at=? WHERE workflow_run_id=? AND node_type='render'",(render["message"],now(),now(),run["id"]))
    else:connection.execute("UPDATE workflow_runs SET progress=?,updated_at=? WHERE id=?",(mapped,now(),run["id"]))
    connection.commit()


def create_router(get_db,render_create,render_body_class):
    router=APIRouter(prefix="/workflow-runs",tags=["workflow-runs"])
    @router.post("/from-draft/{draft_id}")
    def create_run(draft_id:str,background_tasks:BackgroundTasks,preview:bool=False):
        connection=get_db()
        try:
            draft=connection.execute("SELECT status FROM workflow_drafts WHERE id=?",(draft_id,)).fetchone()
            if draft is None:raise HTTPException(status_code=404,detail="Workflow draft not found")
            if draft["status"]!="confirmed":raise HTTPException(status_code=409,detail="Confirm the draft before generation")
            existing=connection.execute("SELECT * FROM workflow_runs WHERE workflow_draft_id=? AND status IN ('queued','generating_assets','rendering','success') ORDER BY created_at DESC LIMIT 1",(draft_id,)).fetchone()
            if existing:return run_payload(connection,existing["id"])
            run_id=uuid.uuid4().hex;timestamp=now();connection.execute("INSERT INTO workflow_runs (id,workflow_draft_id,status,progress,created_at,updated_at) VALUES (?,?,'queued',0,?,?)",(run_id,draft_id,timestamp,timestamp));connection.commit()
            background_tasks.add_task(execute_pipeline,run_id,get_db,render_create,render_body_class,background_tasks,preview)
            return run_payload(connection,run_id)
        finally:connection.close()
    @router.get("/{run_id}")
    def get_run(run_id:str):
        connection=get_db()
        try:
            run=connection.execute("SELECT * FROM workflow_runs WHERE id=?",(run_id,)).fetchone()
            if run is None:raise HTTPException(status_code=404,detail="Workflow run not found")
            sync_render(connection,run)
            return run_payload(connection,run_id)
        finally:connection.close()
    @router.post("/{run_id}/retry")
    def retry_run(run_id:str,background_tasks:BackgroundTasks,preview:bool=False):
        connection=get_db()
        try:
            run=connection.execute("SELECT * FROM workflow_runs WHERE id=?",(run_id,)).fetchone()
            if run is None:raise HTTPException(status_code=404,detail="Workflow run not found")
            if run["status"]!="failed":raise HTTPException(status_code=409,detail="Only failed runs can be retried")
            connection.execute("UPDATE workflow_runs SET status='queued',message=NULL,updated_at=?,finished_at=NULL WHERE id=?",(now(),run_id));connection.commit();background_tasks.add_task(execute_pipeline,run_id,get_db,render_create,render_body_class,background_tasks);return run_payload(connection,run_id)
        finally:connection.close()
    return router
