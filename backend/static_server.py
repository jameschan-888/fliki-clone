import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()
ROOT = os.getenv("FLIKI_STATIC_ROOT") or r"D:\workspace\Fliki视频制作还原\backend\data\workflow_runs"
app.mount("/media", StaticFiles(directory=ROOT, check_dir=False), name="media")
