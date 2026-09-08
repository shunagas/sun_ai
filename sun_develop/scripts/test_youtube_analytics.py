"""APIキーで動画IDからタイトルが取得できるか確認するテストスクリプト。"""
import os
from googleapiclient.discovery import build

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_KEY_FILE = os.path.join(BASE_DIR, ".secrets", "youtube_data_api_key.txt")

with open(API_KEY_FILE) as f:
    api_key = f.read().strip()

youtube = build("youtube", "v3", developerKey=api_key)

video_ids = ["zJKPKrLwP9A", "C2ydpzWnsEk", "bvdPkzjPHRU"]
response = youtube.videos().list(part="snippet", id=",".join(video_ids)).execute()

for item in response.get("items", []):
    print(item["id"], item["snippet"]["title"])
