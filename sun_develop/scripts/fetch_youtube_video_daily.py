"""直近30日・動画ごとの日次再生数を取得し、上位10本にまとめてJSON出力するスクリプト。
YouTube Analytics APIはdimensions="day,video"の組み合わせをサポートしないため、
1日ずつ dimensions="video" でクエリして積み上げる。
"""
import datetime
import json
import os

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_DIR = os.path.join(BASE_DIR, ".secrets")
TOKEN_FILE = os.path.join(SECRETS_DIR, "youtube_analytics_token.json")
API_KEY_FILE = os.path.join(SECRETS_DIR, "youtube_data_api_key.txt")
OUT_FILE = os.path.join(BASE_DIR, "materials", "youtube_video_daily.json")

DAYS = 30
TOP_N = 10

creds = Credentials.from_authorized_user_file(TOKEN_FILE)
youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)

with open(API_KEY_FILE) as f:
    api_key = f.read().strip()
youtube_data = build("youtube", "v3", developerKey=api_key)

today = datetime.date.today()
dates = [(today - datetime.timedelta(days=i)).isoformat() for i in range(DAYS, 0, -1)]

# {videoId: {date: {"views": int, "minutes": int}}}
per_video_daily = {}
for date in dates:
    response = youtube_analytics.reports().query(
        ids="channel==MINE",
        startDate=date,
        endDate=date,
        metrics="views,estimatedMinutesWatched",
        dimensions="video",
        sort="-views",
        maxResults=200,
    ).execute()
    for video_id, views, minutes in response.get("rows", []):
        per_video_daily.setdefault(video_id, {})[date] = {"views": views, "minutes": minutes}

# 上位N本を合計再生数で選定
totals = {vid: sum(day["views"] for day in days.values()) for vid, days in per_video_daily.items()}
top_ids = sorted(totals, key=totals.get, reverse=True)[:TOP_N]

# タイトル取得（50件までなら1コール）
titles = {}
if top_ids:
    resp = youtube_data.videos().list(part="snippet", id=",".join(top_ids)).execute()
    for item in resp.get("items", []):
        titles[item["id"]] = item["snippet"]["title"]

videos = []
for vid in top_ids:
    series = [
        {
            "date": d,
            "views": per_video_daily[vid].get(d, {}).get("views", 0),
            "minutes": per_video_daily[vid].get(d, {}).get("minutes", 0),
        }
        for d in dates
    ]
    videos.append({
        "videoId": vid,
        "title": titles.get(vid, vid),
        "totalViews": totals[vid],
        "totalMinutes": sum(per_video_daily[vid].get(d, {}).get("minutes", 0) for d in dates),
        "series": series,
    })

output = {
    "updatedAt": datetime.datetime.now().isoformat(timespec="seconds"),
    "rangeStart": dates[0],
    "rangeEnd": dates[-1],
    "videos": videos,
}

with open(OUT_FILE, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"書き出しました: {OUT_FILE}")
print(f"動画数: {len(videos)}")
