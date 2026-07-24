import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main
from provider_config import mask_secret
from workflow_pipeline import ensure_node, media_duration, run_node, stage_asset, synthesize_scene_voice


class P5BPipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir=tempfile.TemporaryDirectory();self.original=main.config["DB_PATH"]
        main.config["DB_PATH"]=str(Path(self.temp_dir.name)/"app.db");main.init_db()

    def tearDown(self):
        main.config["DB_PATH"]=self.original;self.temp_dir.cleanup()

    def test_provider_api_masks_secret(self):
        endpoint=next(route.endpoint for route in main.app.routes if route.path=="/provider-configs" and "GET" in route.methods)
        with patch.dict(os.environ,{"PEXELS_API_KEY":"abcd12345678wxyz"}):
            pexels=next(item for item in endpoint("stock") if item["name"]=="pexels")
        self.assertTrue(pexels["has_api_key"]);self.assertEqual(pexels["api_key_masked"],"abcd********wxyz")
        self.assertNotIn("12345678",json.dumps(pexels))

    def test_successful_nodes_are_reused_on_retry(self):
        connection=main.get_db();timestamp="2026-07-23T00:00:00+00:00"
        connection.execute("INSERT INTO workflow_drafts (id,title,source_script,status,version,created_at,updated_at) VALUES ('draft','t','s','confirmed',1,?,?)",(timestamp,timestamp))
        connection.execute("INSERT INTO workflow_runs (id,workflow_draft_id,status,progress,created_at,updated_at) VALUES ('run','draft','queued',0,?,?)",(timestamp,timestamp));connection.commit()
        node=ensure_node(connection,"run","scene","stock",{"query":"city"});calls=[]
        first=run_node(connection,node,lambda:(calls.append(1) or "mock",{"local_path":"asset.mp4"}))
        node=connection.execute("SELECT * FROM workflow_nodes WHERE id=?",(node["id"],)).fetchone()
        second=run_node(connection,node,lambda:(calls.append(2) or "mock",{"local_path":"other.mp4"}))
        self.assertEqual(first,second);self.assertEqual(calls,[1]);connection.close()

    def test_unconfirmed_draft_cannot_start_generation(self):
        create=next(route.endpoint for route in main.app.routes if route.path=="/workflow-runs/from-draft/{draft_id}" and "POST" in route.methods)
        connection=main.get_db();timestamp="2026-07-23T00:00:00+00:00"
        connection.execute("INSERT INTO workflow_drafts (id,title,source_script,status,version,created_at,updated_at) VALUES ('draft','t','s','draft',1,?,?)",(timestamp,timestamp));connection.commit();connection.close()
        from fastapi import BackgroundTasks,HTTPException
        with self.assertRaises(HTTPException) as context:create("draft",BackgroundTasks())
        self.assertEqual(context.exception.status_code,409)


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
