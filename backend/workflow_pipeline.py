import json
import os
import shutil
import subprocess
import threading
import uuid
from datetime import datetime,timezone
from pathlib import Path

from fastapi import APIRouter,BackgroundTasks,HTTPException,Request
from pydantic import BaseModel

from providers.music import FreesoundProvider, fetch_music_with_fallback

UPLOAD_DIR = Path(__file__).parent / "data" / "uploads"
from providers.stock import fetch_with_fallback
from providers.tts import DEFAULT_VOICE, EdgeTTSProvider, synthesize_tts_with_fallback
from services.cadence import detect_voice_segments as cadence_detect, cadence_summary as cadence_summary_svc
from providers.avatar import build_wav2lip_provider, AVATAR_CLONE_PREFIX
from providers.base import ProviderError
from providers.template_renderer import TemplateRenderer
from avatar_segment_pipeline import synthesize_segmented_avatar
from workers.segment_dispatcher import dispatch_segments as render_segments_dispatch


def now(): return datetime.now(timezone.utc).isoformat()


def media_duration(path):
    result=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],capture_output=True,timeout=20)
    output=(result.stdout or b"").decode("utf-8",errors="replace").strip()
    return round(float(output),3) if result.returncode==0 and output else None


def synthesize_scene_voice(scene, destination):
    """已废弃: P7-Fallback 之后用 synthesize_tts_with_fallback.
    保留仅为兼容旧测试."""
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
        model_path = provider_kwargs.get("model_path") if provider_kwargs else None
        cache_dir = Path(__file__).parent / "data" / "avatar_segment_cache"
        result = synthesize_segmented_avatar(
            face_path=face_path,
            audio_path=audio_source,
            destination_path=destination,
            provider_factory=lambda: provider,
            cache_dir=cache_dir,
            model_path=model_path,
            minimum_seconds=2.0,
            maximum_seconds=6.0,
            fps=float(provider_kwargs.get("fps", 25.0)) if provider_kwargs else 25.0,
            max_dimension=int(provider_kwargs.get("max_dimension", 320)) if provider_kwargs else 320,
            ffmpeg_binary=provider_kwargs.get("ffmpeg_binary", "ffmpeg") if provider_kwargs else "ffmpeg",
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


def _resolve_template_plan(scene, connection):
    """Pipeline template node worker. Mock 模式不真渲染, 仅生成 plan.
    视频额度测试期间防止误触发下游 Remotion / ffmpeg 调用."""
    template_id = (scene["template_id"] if "template_id" in scene.keys() else None)
    if not template_id:
        return ("template_mock", {"ok": False, "skipped": True, "reason": "no template_id"})
    fields_raw = (scene["template_fields"] if "template_fields" in scene.keys() else None)
    if isinstance(fields_raw, str):
        try: fields = json.loads(fields_raw or "{}")
        except Exception: fields = {}
    else:
        fields = fields_raw or {}
    template = None
    try:
        from templates_router import _template_payload
        row = connection.execute("SELECT * FROM templates WHERE id=?", (template_id,)).fetchone()
        if row is not None:
            template = _template_payload(row, include_config=True)
    except Exception:
        template = None
    if template is None:
        return ("template_mock", {"ok": False, "skipped": True, "reason": "template not found"})
    renderer = TemplateRenderer(
        template, fields,
        mode="mock", scene_id=scene["id"],
        duration_override=(scene["duration_seconds"] if "duration_seconds" in scene.keys() else None),
    )
    plan_result = renderer.render()
    return ("template_mock", plan_result)




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


def run_node(connection, node, work, *, max_attempts=None):
    """Run a workflow node with auto-retry (exponential backoff).

    - max_attempts: max attempts (default env FLIKI_NODE_MAX_ATTEMPTS, default 3)
    - 第一次失败后按 0.5s, 1s, 2s, 4s ... 退避重试
    - 用尽 attempts 后把节点标记 failed 终态, 抛出原异常让 execute_pipeline 终止
    """
    if max_attempts is None:
        max_attempts = int(os.getenv("FLIKI_NODE_MAX_ATTEMPTS", "3"))
    assert max_attempts >= 1, "max_attempts must be >= 1"
    if node["status"] == "success" and node["result_json"]:
        return json.loads(node["result_json"])
    last_error = None
    import time as _time
    for try_index in range(max_attempts):
        connection.execute(
            "UPDATE workflow_nodes SET status='processing',progress=10,attempt=?,message=NULL,updated_at=? WHERE id=?",
            (try_index + 1, now(), node["id"]),
        )
        connection.commit()
        try:
            provider, result = work()
            complete_node(connection, node["id"], provider, result)
            return result
        except Exception as error:
            last_error = error
            connection.execute(
                "UPDATE workflow_nodes SET status='failed',message=?,updated_at=? WHERE id=?",
                (str(error)[:2000], now(), node["id"]),
            )
            connection.commit()
            if try_index < max_attempts - 1:
                backoff = min(8.0, 0.5 * (2 ** try_index))
                _time.sleep(backoff)
                continue
            break
    connection.execute(
        "UPDATE workflow_nodes SET status='failed',message=?,updated_at=?,finished_at=? WHERE id=?",
        (f"[after {max_attempts} attempts] " + str(last_error)[:1900], now(), now(), node["id"]),
    )
    connection.commit()
    raise last_error


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
            tts=run_node(connection,tts_node,lambda:("tts_chain",synthesize_tts_with_fallback(scene["narration"], scene_dir/"voice.mp3", voice=selected_voice, language=(scene["language"] if "language" in scene.keys() else "zh"))));tts["duration_seconds"]=media_duration(tts["local_path"]);upsert_asset(connection,run_id,scene["id"],"voice",tts)
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
            stock_url=(scene["stock_url"] if "stock_url" in scene.keys() else None)
            stock_node=ensure_node(connection,run_id,scene["id"],"stock",{"query":scene["visual_intent"],"stock_url":stock_url})
            if stock_url:
                stock_dest=scene_dir/"stock.mp4"
                if stock_url.startswith("/uploads/"):
                    src_file=UPLOAD_DIR/stock_url[len("/uploads/"):]
                else:
                    src_file=Path(stock_url)
                try:
                    shutil.copy(src_file,stock_dest)
                    stock={"provider":"local","source_url":stock_url,"local_path":str(stock_dest),"page_url":None,"creator":"user-upload"}
                except OSError:
                    stock=run_node(connection,stock_node,lambda:(lambda result:(result["provider"],result))(fetch_with_fallback(scene["visual_intent"],scene_dir/"stock.mp4")))
            else:
                stock=run_node(connection,stock_node,lambda:(lambda result:(result["provider"],result))(fetch_with_fallback(scene["visual_intent"],scene_dir/"stock.mp4")))
            upsert_asset(connection,run_id,scene["id"],"stock",stock)
            video_src=stage_asset(stock["local_path"],public_dir,f"scene-{index}-stock")
            template_plan=None
            if (scene["template_id"] if "template_id" in scene.keys() else None):
                template_node=ensure_node(connection,run_id,scene["id"],"template",{"template_id":(scene["template_id"] if "template_id" in scene.keys() else None),"fields":scene["template_fields"] or {}})
                template_plan=run_node(connection,template_node,lambda:_resolve_template_plan(scene, connection))
                try: fields=(scene["template_fields"] if ("template_fields" in scene.keys() and scene["template_fields"] is not None) else {})
                except Exception: fields={}
                upsert_asset(connection,run_id,scene["id"],"template",{"provider":(template_plan.get("plan") or {}).get("provider","mock"),"local_path":(template_plan.get("plan") or {}).get("placeholder_path") or f"templates/{scene['template_id']}/mock-{scene['id']}.mp4","source_url":None,"duration_seconds":(template_plan.get("plan") or {}).get("duration_seconds"),"template_id":scene["template_id"],"layer_count":(template_plan.get("plan") or {}).get("layer_count",0)})
            rendered_scenes.append({"id":scene["id"],"title":scene["title"],"subtitle":scene["subtitle"],"durationInSeconds":tts.get("duration_seconds") or scene["duration_seconds"],"videoSrc":video_src,"audioSrc":audio_src,"avatarSrc":avatar_src,"cameraMotion":(scene["camera_motion"] if "camera_motion" in scene.keys() else "zoom-in"),"templateId":(scene["template_id"] if "template_id" in scene.keys() else None),"templatePlan":(template_plan or {}).get("plan") if template_plan else None,"avatarFallback":bool(avatar_meta and avatar_meta.get("fallback_used")),"avatarMode":(avatar_meta or {}).get("mode"),"avatarName":(avatar_meta or {}).get("avatar_name"),"avatarLayout":None,"subtitle_display":(scene["subtitle_display"] if "subtitle_display" in scene.keys() else scene["subtitle"]),"subtitle_spoken":(scene["subtitle_spoken"] if "subtitle_spoken" in scene.keys() else scene["narration"]),"video_aspect":(scene["video_aspect"] if "video_aspect" in scene.keys() else "16:9"),"video_transition_mode":(scene["video_transition_mode"] if "video_transition_mode" in scene.keys() else "fade"),"media_width":(scene["media_width"] if "media_width" in scene.keys() else 1280),"media_height":(scene["media_height"] if "media_height" in scene.keys() else 720)})
            connection.execute("UPDATE workflow_runs SET progress=?,updated_at=? WHERE id=?",(10+int(55*(index+1)/len(scenes)),now(),run_id));connection.commit()
        music_node=ensure_node(connection,run_id,None,"music",{"query":"calm cinematic background music"})
        music=run_node(connection,music_node,lambda:("music_chain",fetch_music_with_fallback("calm cinematic background music",run_dir/"music.mp3")))
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
        dispatch_ok, dispatch_msg, final_job_id = render_segments_dispatch(
            connection,
            run_id,
            rendered_scenes,
            props,
            Path(__file__).parent / "data" / "workflow_runs" / run_id,
            resolution,
        )
        if dispatch_ok:
            connection.execute("UPDATE workflow_runs SET render_job_id=?,progress=100,updated_at=?,finished_at=? WHERE id=?", (final_job_id, now(), now(), run_id))
            connection.execute("UPDATE workflow_nodes SET status='success',progress=100,result_json=?,finished_at=?,updated_at=? WHERE id=?", (json.dumps({"jobId": final_job_id, "dispatch_msg": dispatch_msg}, ensure_ascii=False), now(), now(), render_node["id"]))
            connection.commit()
        else:
            connection.execute("UPDATE workflow_nodes SET status='failed',message=?,finished_at=?,updated_at=? WHERE id=?", (dispatch_msg[:2000] if dispatch_msg else "dispatch failed", now(), now(), render_node["id"]))
            connection.commit()
            raise RuntimeError("render_segments_dispatch failed: " + (dispatch_msg or ""))
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


def rerender_existing(run_id, get_db, render_create, render_body_class, background_tasks):
    connection = get_db()
    try:
        run = connection.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
        if run is None:
            raise HTTPException(status_code=404, detail="Workflow run not found")
        if run["status"] not in ("success", "failed", "rendering"):
            raise HTTPException(status_code=409, detail="Run is still generating assets")
        scenes = connection.execute("SELECT id, camera_motion FROM scene_drafts WHERE workflow_draft_id=? ORDER BY position", (run["workflow_draft_id"],)).fetchall()
        motion_by_id = {row["id"]: (row["camera_motion"] or "zoom-in") for row in scenes}
        run_dir = Path(__file__).parent / "data" / "workflow_runs" / run_id
        public_dir = run_dir / "remotion_public"
        assets = connection.execute(
            "SELECT scene_draft_id, asset_type, local_path FROM scene_assets WHERE workflow_run_id=?",
            (run_id,),
        ).fetchall()
        missing = [row for row in assets if not row["local_path"] or not Path(row["local_path"]).is_file()]
        if missing:
            raise HTTPException(status_code=409, detail="Source assets missing; please re-generate the draft first")
        props_path = Path(__file__).parent / "data" / "props" / f"workflow-{run_id}.json"
        if not props_path.is_file():
            raise HTTPException(status_code=409, detail="Original render props missing; cannot rerender")
        payload = json.loads(props_path.read_text(encoding="utf-8"))
        for scene in payload.get("scenes", []):
            scene["cameraMotion"] = motion_by_id.get(scene["id"], "zoom-in")
        payload["_publicDir"] = str(public_dir)
        payload["_rerenderSource"] = run_id
        props_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        render_node = ensure_node(connection, run_id, None, "render", {"props_path": str(props_path), "rerender": True})
        connection.execute(
            "UPDATE workflow_nodes SET status='processing', progress=5, provider='remotion', updated_at=? WHERE id=?",
            (now(), render_node["id"]),
        )
        connection.execute(
            "UPDATE workflow_runs SET status='rendering', progress=70, message='仅重新渲染（复用素材）', updated_at=?, finished_at=NULL WHERE id=?",
            (now(), run_id),
        )
        connection.commit()
        connection.close()
        response = render_create(
            render_body_class(playback_id=f"workflow-{run_id}", props_path=str(props_path), resolution="720p"),
            background_tasks,
        )
        connection = get_db()
        connection.execute(
            "UPDATE workflow_runs SET render_job_id=?, progress=75, updated_at=? WHERE id=?",
            (response["jobId"], now(), run_id),
        )
        connection.execute(
            "UPDATE workflow_nodes SET result_json=? WHERE id=?",
            (json.dumps(response, ensure_ascii=False), render_node["id"]),
        )
        connection.commit()
        return run_payload(connection, run_id)
    finally:
        connection.close()


def create_router(get_db, render_create, render_body_class):
    from auth_router import get_user_id_from_request as _uid_of_request
    router=APIRouter(prefix="/workflow-runs",tags=["workflow-runs"])
    @router.get("")
    def list_runs(request: Request = None, page: int = 0, limit: int = 20, status: str | None = None):
        """列出当前 user 的 workflow_runs (按 created_at DESC, 默认 20, 上限 100).
        - 无 token: 返回空数组 (不暴露他人 run)
        - 有 token: 强制按 user_id 过滤
        - 可选 status 过滤 (queued/running/success/failed)
        - page=0 (默认) 返 list 形态 (向后兼容); page>=1 返 wrapper {items, total, page, limit, has_more}
        """
        from auth_router import get_user_id_from_request as _uid
        user_id = _uid(request)
        if not user_id:
            return [] if page <= 0 else {"items": [], "total": 0, "page": page, "limit": limit, "has_more": False}
        connection = get_db()
        try:
            clauses = ["user_id = ?"]
            params: list = [user_id]
            if status:
                clauses.append("status = ?")
                params.append(status)
            where = " WHERE " + " AND ".join(clauses)
            capped_limit = max(1, min(limit, 100))
            if page <= 0:
                # 旧行为: 返 list
                rows = connection.execute(
                    "SELECT * FROM workflow_runs" + where + " ORDER BY created_at DESC LIMIT ?", params + [capped_limit]
                ).fetchall()
                return [run_payload(connection, row["id"]) for row in rows]
            # 新行为: 分页 wrapper
            total = int(connection.execute(
                "SELECT count(*) FROM workflow_runs" + where, params
            ).fetchone()[0] or 0)
            offset = (page - 1) * capped_limit
            rows = connection.execute(
                "SELECT * FROM workflow_runs" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [capped_limit, offset]
            ).fetchall()
            items = [run_payload(connection, row["id"]) for row in rows]
            return {
                "items": items,
                "total": total,
                "page": page,
                "limit": capped_limit,
                "has_more": (offset + len(items)) < total,
            }
        finally:
            connection.close()
    @router.post("/from-draft/{draft_id}")
    def create_run(draft_id:str,background_tasks:BackgroundTasks,request:Request = None,preview:bool=False,force:bool=False):
        from auth_router import get_user_id_from_request as _uid
        user_id = _uid(request)
        connection=get_db()
        try:
            if not user_id:raise HTTPException(status_code=401,detail="未登录或登录已过期，请重新登录")
            draft=connection.execute("SELECT status, user_id FROM workflow_drafts WHERE id=?",(draft_id,)).fetchone()
            if draft is None or draft["user_id"] != user_id:raise HTTPException(status_code=404,detail="Workflow draft not found")
            if draft["status"]!="confirmed":raise HTTPException(status_code=409,detail="Confirm the draft before generation")
            existing=connection.execute("SELECT * FROM workflow_runs WHERE workflow_draft_id=? AND status IN ('queued','generating_assets','rendering','success') ORDER BY created_at DESC LIMIT 1",(draft_id,)).fetchone()
            if existing and (existing["status"] != "success" or not force):return run_payload(connection,existing["id"])
            run_id=uuid.uuid4().hex;timestamp=now();connection.execute("INSERT INTO workflow_runs (id,workflow_draft_id,status,progress,created_at,updated_at,user_id) VALUES (?,?,'queued',0,?,?,?)",(run_id,draft_id,timestamp,timestamp,user_id));connection.commit()
            background_tasks.add_task(execute_pipeline,run_id,get_db,render_create,render_body_class,background_tasks,preview)
            return run_payload(connection,run_id)
        finally:connection.close()
    @router.get("/{run_id}")
    def get_run(run_id:str,request:Request = None):
        connection=get_db()
        try:
            user_id = _uid_of_request(request)
            if not user_id:raise HTTPException(status_code=401,detail="未登录或登录已过期，请重新登录")
            run=connection.execute("SELECT * FROM workflow_runs WHERE id=?",(run_id,)).fetchone()
            if run is None or run["user_id"] != user_id:raise HTTPException(status_code=404,detail="Workflow run not found")
            sync_render(connection,run)
            return run_payload(connection,run_id)
        finally:connection.close()
    @router.post("/{run_id}/retry")
    def retry_run(run_id:str,background_tasks:BackgroundTasks,preview:bool=False,request:Request = None):
        connection=get_db()
        try:
            user_id = _uid_of_request(request)
            if not user_id:raise HTTPException(status_code=401,detail="未登录或登录已过期，请重新登录")
            run=connection.execute("SELECT * FROM workflow_runs WHERE id=?",(run_id,)).fetchone()
            if run is None or run["user_id"] != user_id:raise HTTPException(status_code=404,detail="Workflow run not found")
            if run["status"]!="failed":raise HTTPException(status_code=409,detail="Only failed runs can be retried")
            connection.execute("UPDATE workflow_runs SET status='queued',message=NULL,updated_at=?,finished_at=NULL WHERE id=?",(now(),run_id));connection.commit();background_tasks.add_task(execute_pipeline,run_id,get_db,render_create,render_body_class,background_tasks);return run_payload(connection,run_id)
        finally:connection.close()
    @router.post("/{run_id}/rerender")
    def rerender_run(run_id:str,background_tasks:BackgroundTasks,request:Request = None):
        user_id = _uid_of_request(request)
        if not user_id:raise HTTPException(status_code=401,detail="未登录或登录已过期，请重新登录")
        connection=get_db()
        try:
            run=connection.execute("SELECT user_id FROM workflow_runs WHERE id=?",(run_id,)).fetchone()
            if run is None or run["user_id"] != user_id:raise HTTPException(status_code=404,detail="Workflow run not found")
        finally:connection.close()
        return rerender_existing(run_id, get_db, render_create, render_body_class, background_tasks)
    return router


