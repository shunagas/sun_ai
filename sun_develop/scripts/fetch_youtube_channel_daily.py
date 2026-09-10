"""チャンネル全体の累計サマリー（視聴回数・総再生時間・平均視聴時間・インプレッション・CTR・登録者数）を
日次スナップショットとして取得し、日付をキーにした履歴配列でJSONに追記していくスクリプト。

fetch_youtube_video_daily.py と同じ認証（.secrets/のOAuthトークン・APIキー）を使い回す。
想定運用：本人のMacで毎日1回実行し、生成された materials/youtube_channel_daily.json を
git commit/push する。ダッシュボードDBへの反映は対話セッションで `/sun-travel-sync` を
実行したときのみ（無人のクラウドルーティンからArtifactのwrite_dbを呼ぶと承認待ちで
永久にハングする既知の不具合があるため、このスクリプト自体はDBに一切触れない設計）。

毎日の自動実行方法（launchd）は sun_develop/scripts/README_channel_daily.md を参照。
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
OUT_FILE = os.path.join(BASE_DIR, "materials", "youtube_channel_daily.json")

CHANNEL_HANDLE = "@sun-viaje"
# YouTube Analytics APIが実際に遡れる期間よりも十分前の日付を指定し、
# 「チャンネル開設からendDateまでの累計」を1行で集計させる。
LIFETIME_START = "2005-01-01"


def fmt_avg_watch(seconds):
    seconds = int(round(seconds or 0))
    return "%02d:%02d" % (seconds // 60, seconds % 60)


creds = Credentials.from_authorized_user_file(TOKEN_FILE)
youtube_analytics = build("youtubeAnalytics", "v2", credentials=creds)

with open(API_KEY_FILE) as f:
    api_key = f.read().strip()
youtube_data = build("youtube", "v3", developerKey=api_key)

# YouTube Analyticsのデータ確定には数日のラグがあり得るため、当日ではなく前日時点の累計を記録する。
target_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

# 1) 視聴回数・総再生時間・平均視聴時間（dimensionsなしで期間内の単一行集計＝累計値になる）
engagement = youtube_analytics.reports().query(
    ids="channel==MINE",
    startDate=LIFETIME_START,
    endDate=target_date,
    metrics="views,estimatedMinutesWatched,averageViewDuration",
).execute()
erow = (engagement.get("rows") or [[0, 0, 0]])[0]
views, minutes_watched, avg_view_duration_sec = erow[0], erow[1], erow[2]

# 2) インプレッション・CTR（別のレポート系のため分けてクエリ。失敗しても他の値は記録する）
impressions, ctr = 0, 0.0
try:
    impression = youtube_analytics.reports().query(
        ids="channel==MINE",
        startDate=LIFETIME_START,
        endDate=target_date,
        metrics="impressions,impressionsClickThroughRate",
    ).execute()
    irow = (impression.get("rows") or [[0, 0]])[0]
    impressions, ctr = irow[0], irow[1]
except Exception as e:
    print(f"警告: impressions/CTRの取得に失敗しました（{e}）。0扱いで続行します。")

# 3) 登録者数（Data API、チャンネルが登録者数を非公開にしていなければAPIキーのみで取得可）
subs = None
try:
    resp = youtube_data.channels().list(part="statistics", forHandle=CHANNEL_HANDLE).execute()
    items = resp.get("items") or []
    if items and not items[0]["statistics"].get("hiddenSubscriberCount"):
        subs = int(items[0]["statistics"]["subscriberCount"])
except Exception as e:
    print(f"警告: 登録者数の取得に失敗しました（{e}）。")

history = []
if os.path.exists(OUT_FILE):
    with open(OUT_FILE) as f:
        history = json.load(f).get("history", [])

if subs is None:
    if history:
        subs = history[-1]["subs"]
        print(f"登録者数を取得できなかったため、前回記録値を引き継ぎます: {subs}人")
    else:
        subs = 0
        print("登録者数を取得できず、過去の履歴もないため暫定的に0を記録します。")

sub_rate = (subs / views * 100) if views else 0.0

entry = {
    "date": target_date,
    "views": views,
    "watchHours": round(minutes_watched / 60, 1),
    "impressions": impressions,
    "ctr": round(ctr, 1),
    "avgWatch": fmt_avg_watch(avg_view_duration_sec),
    "subs": subs,
    "subRate": round(sub_rate, 4),
}

# 同じ日付の再実行はレコードを上書き（重複を作らない）
history = [h for h in history if h["date"] != entry["date"]]
history.append(entry)
history.sort(key=lambda h: h["date"])

output = {
    "updatedAt": datetime.datetime.now().isoformat(timespec="seconds"),
    "history": history,
}

with open(OUT_FILE, "w") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"書き出しました: {OUT_FILE}")
print(
    f"{entry['date']} 時点の累計: 視聴回数{views:,}回 / "
    f"総再生時間{entry['watchHours']}h / 登録者{subs}人 / "
    f"インプレッション{impressions:,}回 / CTR{entry['ctr']}% / 平均視聴時間{entry['avgWatch']}"
)

# 任意: 環境変数 AUTO_GIT_PUSH=1 のときだけ、このJSONファイル1点に限定してcommit/pushする。
# デフォルト(未設定)では何もしない＝手動でgit add/commit/pushする運用のまま安全に動く。
if os.environ.get("AUTO_GIT_PUSH") == "1":
    import subprocess

    rel_path = os.path.relpath(OUT_FILE, BASE_DIR)
    try:
        subprocess.run(["git", "add", rel_path], cwd=BASE_DIR, check=True)
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", rel_path], cwd=BASE_DIR
        )
        if diff.returncode == 0:
            print("差分なし（前回実行と同じ値）のためcommitはスキップします。")
        else:
            subprocess.run(
                ["git", "commit", "-m", f"YouTubeチャンネル日次サマリーを更新（{entry['date']}）"],
                cwd=BASE_DIR,
                check=True,
            )
            subprocess.run(["git", "push"], cwd=BASE_DIR, check=True)
            print("git commit/pushまで完了しました。")
    except subprocess.CalledProcessError as e:
        print(f"警告: git commit/pushに失敗しました（{e}）。手動で対応してください。")
