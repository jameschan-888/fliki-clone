import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import time
import uuid as _uuid
import main
from auth_router import _make_token, _hash_pw, ensure_users_table
from provider_config import mask_secret
from workflow_pipeline import ensure_node, media_duration, run_node, stage_asset, synthesize_scene_voice


class _MockRequest:
    """Mock starlette Request 替身, headers 含 Bearer token."""
    def __init__(self, token):
        self.headers = {"Authorization": "Bearer " + token}


class P5BPipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir=tempfile.TemporaryDirectory();self.original=main.config["DB_PATH"]
        main.config["DB_PATH"]=str(Path(self.temp_dir.name)/"app.db");main.init_db()
        ensure_users_table()
        self.user_id = _uuid.uuid4().hex
        salt, pw_hash = _hash_pw("test-pass-123")
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with main.get_db() as _con:
            _con.execute("INSERT INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (self.user_id, "test@fliki.local", salt, pw_hash, "user", now, now))
            _con.commit()
        self.token = _make_token(self.user_id, "user")
        self.headers = {"Authorization": "Bearer " + self.token}

    def tearDown(self):
        main.config["DB_PATH"]=self.original;self.temp_dir.cleanup()

    def test_provider_api_masks_secret(self):
        endpoint=next(route.endpoint for route in main.app.routes if route.path=="/provider-configs" and "GET" in route.methods)
        with patch.dict(os.environ,{"PEXELS_API_KEY":"abcd12345678wxyz"}):
            pexels=next(item for item in endpoint("stock") if item["name"]=="pexels")
        self.assertTrue(pexels["has_api_key"]);self.assertEqual(pexels["api_key_masked"],"abcd********wxyz")
        self.assertNotIn("12345678",json.dumps(pexels))

    def test_successful_nodes_are_reused_on_retry(self):
        with main.get_db() as connection:
            timestamp="2026-07-23T00:00:00+00:00"
            connection.execute("INSERT INTO workflow_drafts (id,title,source_script,status,version,created_at,updated_at) VALUES ('draft','t','s','confirmed',1,?,?)",(timestamp,timestamp))
            connection.execute("INSERT INTO workflow_runs (id,workflow_draft_id,status,progress,created_at,updated_at) VALUES ('run','draft','queued',0,?,?)",(timestamp,timestamp));connection.commit()
            node=ensure_node(connection,"run","scene","stock",{"query":"city"});calls=[]
            first=run_node(connection,node,lambda:(calls.append(1) or "mock",{"local_path":"asset.mp4"}))
            node=connection.execute("SELECT * FROM workflow_nodes WHERE id=?",(node["id"],)).fetchone()
            second=run_node(connection,node,lambda:(calls.append(2) or "mock",{"local_path":"other.mp4"}))
            self.assertEqual(first,second);self.assertEqual(calls,[1])

    def test_unconfirmed_draft_cannot_start_generation(self):
        create=next(route.endpoint for route in main.app.routes if route.path=="/workflow-runs/from-draft/{draft_id}" and "POST" in route.methods)
        with main.get_db() as connection:
            timestamp="2026-07-23T00:00:00+00:00"
            connection.execute("INSERT INTO workflow_drafts (id,title,source_script,status,version,created_at,updated_at,user_id) VALUES ('draft','t','s','draft',1,?,?,?)",(timestamp,timestamp,self.user_id));connection.commit()
            from fastapi import BackgroundTasks,HTTPException
            with self.assertRaises(HTTPException) as context:create("draft",BackgroundTasks(),request=_MockRequest(self.token))
            self.assertEqual(context.exception.status_code,409)


    def test_force_creates_a_new_run_after_success(self):
        create=next(route.endpoint for route in main.app.routes if route.path=="/workflow-runs/from-draft/{draft_id}" and "POST" in route.methods)
        with main.get_db() as connection:
            timestamp="2026-07-23T00:00:00+00:00"
            connection.execute("INSERT INTO workflow_drafts (id,title,source_script,status,version,created_at,updated_at,user_id) VALUES ('draft-force','t','s','confirmed',1,?,?,?)",(timestamp,timestamp,self.user_id))
            connection.execute("INSERT INTO workflow_runs (id,workflow_draft_id,status,progress,created_at,updated_at,user_id) VALUES ('old-run','draft-force','success',100,?,?,?)",(timestamp,timestamp,self.user_id));connection.commit()
            from fastapi import BackgroundTasks
            reused=create("draft-force",BackgroundTasks(),request=_MockRequest(self.token))
            forced=create("draft-force",BackgroundTasks(),force=True,request=_MockRequest(self.token))
            self.assertEqual(reused["id"],"old-run")
            self.assertNotEqual(forced["id"],"old-run")


    def test_rerender_requires_assets_and_props(self):
        rerender_endpoint = next(route.endpoint for route in main.app.routes if route.path == "/workflow-runs/{run_id}/rerender" and "POST" in route.methods)
        with main.get_db() as connection:
            timestamp = "2026-07-23T00:00:00+00:00"
            connection.execute("INSERT INTO workflow_drafts (id,title,source_script,status,version,created_at,updated_at,user_id) VALUES ('draft-rerender','t','s','confirmed',1,?,?,?)", (timestamp, timestamp, self.user_id))
            connection.execute("INSERT INTO workflow_runs (id,workflow_draft_id,status,progress,created_at,updated_at,user_id) VALUES ('run-rerender','draft-rerender','success',100,?,?,?)", (timestamp, timestamp, self.user_id))
            connection.commit()
            connection.close()
            from fastapi import BackgroundTasks, HTTPException
            with self.assertRaises(HTTPException) as context:
                rerender_endpoint("run-rerender", BackgroundTasks(), request=_MockRequest(self.token))
            self.assertEqual(context.exception.status_code, 409)

    def test_rerender_writes_camera_motion_into_props(self):
        with main.get_db() as connection:
            ts = "2026-07-23T00:00:00+00:00"
            connection.execute("INSERT INTO workflow_drafts (id,title,source_script,status,version,created_at,updated_at) VALUES ('draft-cm','t','s','confirmed',1,?,?)", (ts, ts))
            connection.execute("INSERT INTO scene_drafts (id,workflow_draft_id,position,title,narration,visual_intent,subtitle,duration_seconds,voice,avatar,camera_motion,created_at,updated_at) VALUES ('scene-cm','draft-cm',0,'t','n','v','s',3.0,'zh-CN-XiaoxiaoNeural',NULL,'pan-left',?,?)", (ts, ts))
            connection.execute("INSERT INTO workflow_runs (id,workflow_draft_id,status,progress,created_at,updated_at) VALUES ('run-cm','draft-cm','success',100,?,?)", (ts, ts))
            scene_dir = Path(self.temp_dir.name) / 'run-cm'
            scene_dir.mkdir()
            (scene_dir / 'voice.mp3').write_bytes(b'mp3')
            (scene_dir / 'stock.mp4').write_bytes(b'mp4')
            (scene_dir / 'remotion_public').mkdir()
            (scene_dir / 'remotion_public' / 'scene-0-stock.mp4').write_bytes(b'mp4')
            (scene_dir / 'remotion_public' / 'scene-0-voice.mp3').write_bytes(b'mp3')
            (scene_dir / 'remotion_public' / 'background-music.mp3').write_bytes(b'mp3')
            connection.execute("INSERT INTO scene_assets (id,workflow_run_id,scene_draft_id,asset_type,provider,source_url,local_path,attribution_json,created_at) VALUES ('a1','run-cm','scene-cm','voice','edge_tts',NULL,?, '{}', ?)", (str(scene_dir / 'voice.mp3'), ts))
            connection.execute("INSERT INTO scene_assets (id,workflow_run_id,scene_draft_id,asset_type,provider,source_url,local_path,attribution_json,created_at) VALUES ('a2','run-cm','scene-cm','stock','pexels',NULL,?, '{}', ?)", (str(scene_dir / 'stock.mp4'), ts))
            connection.execute("INSERT INTO scene_assets (id,workflow_run_id,scene_draft_id,asset_type,provider,source_url,local_path,attribution_json,created_at) VALUES ('a3','run-cm','scene-cm','music','freesound',NULL,?, '{}', ?)", (str(scene_dir / 'remotion_public' / 'background-music.mp3'), ts))
            connection.commit()
            connection.close()
            props_dir = Path(main.config['DATA_DIR']) / 'props'
            props_dir.mkdir(parents=True, exist_ok=True)
            props_path = props_dir / 'workflow-run-cm.json'
            props_path.write_text(json.dumps({'scenes': [{'id': 'scene-cm', 'title': 't', 'durationInSeconds': 3.0, 'videoSrc': '/public/scene-0-stock.mp4', 'audioSrc': '/public/scene-0-voice.mp3', 'avatarSrc': None}], 'musicSrc': '/public/background-music.mp3', 'durationInSeconds': 3.0, '_publicDir': str(scene_dir / 'remotion_public')}), encoding='utf-8')
            render_calls = []
            captured_props = {}
            class FakeRenderBody:
                def __init__(self, **kwargs):
                    self.kwargs = kwargs
            def render_create(body, bg):
                captured_props['path'] = body.kwargs['props_path']
                render_calls.append(body.kwargs.get('resolution'))
                return {'jobId': 'fake-job'}
            from workflow_pipeline import rerender_existing
            from fastapi import BackgroundTasks
            rerender_existing('run-cm', main.get_db, render_create, FakeRenderBody, BackgroundTasks())
            self.assertEqual(render_calls, ['720p'])
            payload = json.loads(props_path.read_text(encoding='utf-8'))
            self.assertEqual(payload['scenes'][0]['cameraMotion'], 'pan-left')


    def test_selected_scene_voice_reaches_edge_tts(self):
        destination=Path(self.temp_dir.name)/"voice.mp3"
        scene={"narration":"Hello from the selected voice", "voice":"en-US-JennyNeural"}
        expected={"provider":"edge_tts","voice":"en-US-JennyNeural","local_path":str(destination)}
        with patch("workflow_pipeline.EdgeTTSProvider.synthesize",return_value=expected) as synthesize:
            result=synthesize_scene_voice(scene,destination)
        self.assertEqual(result,expected)
        synthesize.assert_called_once_with(scene["narration"],destination,voice="en-US-JennyNeural")

    def test_media_duration_decodes_ffprobe_bytes(self):
        completed=type("Completed",(),{"returncode":0,"stdout":b"2.375\n"})()
        with patch("workflow_pipeline.subprocess.run",return_value=completed):
            self.assertEqual(media_duration("voice.mp3"),2.375)


    def test_stage_asset_exposes_real_file_to_remotion(self):
        source=Path(self.temp_dir.name)/"stock.mp4"
        source.write_bytes(b"video-bytes")
        public_dir=Path(self.temp_dir.name)/"public"
        relative=stage_asset(source,public_dir,"scene-0-stock")
        self.assertEqual(relative,"/public/scene-0-stock.mp4")
        self.assertEqual((public_dir/Path(relative).name).read_bytes(),b"video-bytes")


if __name__=="__main__":unittest.main()
