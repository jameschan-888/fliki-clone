import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import main


class CharactersEndpointTest(unittest.TestCase):
    def test_characters_route_returns_fliki_picker_shape(self):
        routes = {route.path for route in main.app.routes}
        self.assertIn("/characters", routes)

        with tempfile.TemporaryDirectory() as temp_dir:
            original_db_path = main.config["DB_PATH"]
            main.config["DB_PATH"] = str(Path(temp_dir) / "app.db")
            try:
                main.init_db()
                conn = sqlite3.connect(main.config["DB_PATH"])
                conn.execute(
                    """
                    INSERT INTO characters
                    (id, name, kind, image_path, voice_id, provider, meta_json, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "character-1",
                        "Chloe",
                        "female",
                        "image/chloe.jpg",
                        "edge_tts",
                        "fliki_stock",
                        json.dumps({"looksCount": 4}),
                        "2026-07-23T11:05:45.103Z",
                    ),
                )
                conn.commit()
                conn.close()

                from routers.analytics import list_characters
                self.assertIsNotNone(list_characters)
                result = list_characters(gender="female", limit=10)
                self.assertEqual(
                    result,
                    [
                        {
                            "_id": "character-1",
                            "name": "Chloe",
                            "gender": "FEMALE",
                            "looksCount": 4,
                            "thumbnail": "image/chloe.jpg",
                        }
                    ],
                )
            finally:
                main.config["DB_PATH"] = original_db_path


if __name__ == "__main__":
    unittest.main()