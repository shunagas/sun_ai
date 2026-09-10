# YouTubeチャンネル日次サマリーの自動記録（fetch_youtube_channel_daily.py）

視聴回数・総再生時間・インプレッション・CTR・平均視聴時間・登録者数の「チャンネル全体の累計値」を、
日付ごとの履歴として `sun_develop/materials/youtube_channel_daily.json` に毎日1行ずつ記録するスクリプト。

## 前提として理解しておいてほしいこと（重要な制約）

- **完全な自動化はできません。** 無人のクラウドルーティン（RemoteTrigger）からArtifactの`write_db`を呼ぶと
  承認待ちで永久にハングするAnthropicプラットフォーム側の不具合があり、回避不可能と確定しています
  （経緯: `sun_develop/materials/dev-backlog.md` 2026-09-05〜09-09の各エントリ）。
  そのため、このスクリプトは**ダッシュボードのDBには一切触れません**。ローカルの `.secrets/` を使って
  YouTube APIから値を取得し、リポジトリ内のJSONファイルに追記するところまでが自動化の範囲です。
- **ダッシュボード（Sun Travel）への反映は、あなたが対話セッションでClaudeに
  「Sun Travelの内容をリポジトリに同期して」（`/sun-travel-sync`）と伝えたときだけ**行われます。
  スクリプトを自動実行するだけではダッシュボードの数字は更新されません。
- つまり実現できるのは「**日々のAPI取得とファイルへの記録の自動化**」までで、「ダッシュボード表示の自動更新」
  そのものではありません。既存の `fetch_youtube_video_daily.py`（動画別日次データ）と全く同じ運用モデルです。

## 1. 手動で試す（自動化の前に一度）

```
cd /Users/shunagas/sun_ai
python3 sun_develop/scripts/fetch_youtube_channel_daily.py
```

`sun_develop/materials/youtube_channel_daily.json` が作成/更新されることを確認してください。
初回はOAuthトークン（`.secrets/youtube_analytics_token.json`）が
`fetch_youtube_video_daily.py`用に発行済みのものと共用なので、追加の認証作業は不要のはずです。

## 2. git commit/pushについて

デフォルトでは、このスクリプトは**JSONファイルを書き換えるだけ**でgit操作は一切行いません。
手動で以下を実行してリポジトリに反映してください。

```
git add sun_develop/materials/youtube_channel_daily.json
git commit -m "YouTubeチャンネル日次サマリーを更新"
git push
```

`AUTO_GIT_PUSH=1` という環境変数を付けて実行すると、このJSONファイル1点に限定して
`git add` → （差分があれば）`git commit` → `git push` まで自動で行います（他の変更中のファイルを
巻き込まないよう、対象はこのファイルだけに限定しています）。毎日完全放置で回したい場合はこちらを使ってください。

```
AUTO_GIT_PUSH=1 python3 sun_develop/scripts/fetch_youtube_channel_daily.py
```

## 3. 毎日自動実行する設定（launchd、任意）

毎日決まった時刻にMacが自動実行するようにしたい場合の手順です。**この手順はこちらでは実行していません
（本人のMac環境の設定を勝手に変更しないため）。設定するかどうか、実際に行うかはあなたの判断でお願いします。**

1. テンプレートを実際の設定ファイルとしてコピーする。

   ```
   cp /Users/shunagas/sun_ai/sun_develop/scripts/com.sunai.youtube-channel-daily.plist.template \
      ~/Library/LaunchAgents/com.sunai.youtube-channel-daily.plist
   ```

2. コピーしたファイルを開き、`ProgramArguments`の1つ目の文字列（`/opt/anaconda3/bin/python3`の部分）を
   実際のPython3のパスに置き換える。ターミナルで `which python3` を実行して出てきたパスを使う。
   （必要なライブラリ `google-auth` / `google-api-python-client` がそのPython環境に入っている必要があります。
   `python3 -c "import googleapiclient"` でエラーが出なければ大丈夫です。）
3. git push まで自動でやりたくない場合は、コピーしたファイル内の `EnvironmentVariables`
   ブロック（`AUTO_GIT_PUSH`）を丸ごと削除する。
4. ログ出力先ディレクトリを作成する。

   ```
   mkdir -p /Users/shunagas/sun_ai/sun_develop/scripts/logs
   ```

5. launchdに登録する。

   ```
   launchctl load ~/Library/LaunchAgents/com.sunai.youtube-channel-daily.plist
   ```

   デフォルトの設定では毎日 **朝7時30分（JST）** に実行されます
   （テンプレート内の`StartCalendarInterval`で時刻変更可）。

6. 動作確認したい場合は、待たずに手動でキックできます。

   ```
   launchctl start com.sunai.youtube-channel-daily
   ```

   実行結果は `sun_develop/scripts/logs/youtube_channel_daily.out.log`（正常時）・
   `youtube_channel_daily.err.log`（エラー時）で確認できます。

7. 停止・解除したくなったら。

   ```
   launchctl unload ~/Library/LaunchAgents/com.sunai.youtube-channel-daily.plist
   rm ~/Library/LaunchAgents/com.sunai.youtube-channel-daily.plist
   ```

### cronで代替する場合

launchdの代わりにcronでも同じことができます（`crontab -e`で編集、毎日7:30 JSTの例）。

```
30 7 * * * cd /Users/shunagas/sun_ai && AUTO_GIT_PUSH=1 /opt/anaconda3/bin/python3 sun_develop/scripts/fetch_youtube_channel_daily.py >> sun_develop/scripts/logs/youtube_channel_daily.out.log 2>> sun_develop/scripts/logs/youtube_channel_daily.err.log
```

## 4. ダッシュボードに反映したいとき

対話セッションで以下のように伝えてください。

```
Sun Travelの内容をリポジトリに同期して
```

これで `/sun-travel-sync` コマンドが実行され、`youtube_channel_daily.json`の最新履歴が
ダッシュボードDB（`kpi/youtube_channel_daily`）に書き込まれます（詳細は
`~/.claude/commands/sun-travel-sync.md` のステップ3b）。
