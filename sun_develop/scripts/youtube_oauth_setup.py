"""YouTube Analytics APIの初回OAuth認可を行い、リフレッシュトークンを.secrets/に保存するワンショットスクリプト。
実行するとブラウザが開くので、YouTubeチャンネル(@sun-viaje)オーナーのGoogleアカウントでログイン・許可してください。
"""
import glob
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECRETS_DIR = os.path.join(BASE_DIR, ".secrets")

client_secret_files = glob.glob(os.path.join(SECRETS_DIR, "client_secret_*.json"))
if not client_secret_files:
    raise SystemExit(f"client_secret_*.json が {SECRETS_DIR} に見つかりません")
CLIENT_SECRET_FILE = client_secret_files[0]
TOKEN_FILE = os.path.join(SECRETS_DIR, "youtube_analytics_token.json")

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_FILE, "w") as f:
    f.write(creds.to_json())
os.chmod(TOKEN_FILE, 0o600)

print(f"トークンを保存しました: {TOKEN_FILE}")
