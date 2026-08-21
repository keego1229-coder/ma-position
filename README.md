# 移動平均チェック

日本株の日足を毎営業日の引け後に取得して、終値が **5日・25日・75日の移動平均線のどこにいるか** を一覧表示します。

- 三線に対する上下の判定（例：「三線すべての上」「25日線だけ下」）
- 各線からの乖離率（%）を左右バーで表示
- パーフェクトオーダーの判定
- 直近の 5日×25日 ゴールデン／デッドクロスと、その経過営業日数

## しくみ

ブラウザから株価APIを直接叩くと CORS で弾かれるため、**取得はGitHub Actions側（サーバー側）で済ませます**。

```
GitHub Actions（平日17:10 JST）
  └ scripts/fetch_ma.py で日足取得＆判定
      └ docs/data/ma.json にコミット
          └ GitHub Pages が静的配信 → 画面はJSONを読むだけ
```

APIキーもサーバーも不要で、無料枠だけで動きます。

## セットアップ

1. 新しいリポジトリ（例 `ma-position`）を作り、このフォルダの中身をそのまま push する
2. **Settings → Actions → General → Workflow permissions** を `Read and write permissions` に変更
   （Actionsがデータをコミットするために必要）
3. **Settings → Pages → Source** を `Deploy from a branch`、ブランチ `main` / フォルダ `/docs` に設定
4. **Actions タブ → 「移動平均データ更新」→ Run workflow** で一度手動実行
5. `https://<ユーザー名>.github.io/ma-position/` を開く

初回実行前は「データがまだありません」と表示されます。

## 銘柄の追加・変更

`watchlist.json` を編集して push するだけです。

```json
[
  { "code": "7203", "name": "トヨタ自動車" },
  { "code": "^N225", "name": "日経平均株価" }
]
```

- 個別株は4桁コードだけでOK（内部で `.T` を付けます）
- 指数は `^N225`（日経平均）、`^TPX`（TOPIX）のように先頭に `^`
- 1銘柄あたり1秒待つので、20〜30銘柄程度までが快適です

## 手元で試す

```bash
pip install yfinance
python scripts/fetch_ma.py
cd docs && python -m http.server 8000   # http://localhost:8000
```

## 注意

- 株価は Yahoo Finance 由来で、リアルタイムではなく参考値です（15分程度の遅延）。私的利用の範囲で使ってください
- GitHub の cron は混雑時に数十分ずれることがあります。時刻の厳密さは期待しないでください
- **リポジトリに60日間コミットがないと、スケジュール実行が自動停止します**。止まったら Actions タブから再有効化してください
- 移動平均は権利落ち調整済みの終値ベースなので、証券会社のチャートと数円ずれることがあります
