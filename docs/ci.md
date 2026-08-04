# GitHub Actions での実行

企画（`plan`）はローカルのまま、それ以降の工程を GitHub Actions 上で回すための構成。
成果物は各 run の Artifacts からダウンロードできる。

現在実装済みなのは **`ci`（配線チェック）**・**`sim`（シミュレーション）**・
**`upload`（YouTube 非公開投稿）** の3本。
material / narration / composite / thumbnail と、それらを束ねる orchestrator は今後追加する。
そのため **現時点で `upload` が投稿するのは Blender の生素材**（字幕・ナレーション・効果音なし）で、
compose 工程が CI 化されたら `upload` の入力アーティファクトを差し替えるだけで済む設計にしてある。

## ワークフロー一覧

| ワークフロー | トリガ | 用途 | 所要 |
|---|---|---|---|
| `ci.yml` | push(main) / PR / 手動 | スタブモードで全工程を通し、配線と共通セットアップを検証 | 約2〜5分 |
| `sim.yml` | 手動 / `workflow_call` | Blender シミュレーション＋レンダー。成功すると既定で `upload` へ連鎖 | preview 6秒尺で約10〜20分 |
| `upload.yml` | 手動 / `workflow_call`（`sim` から） | アーティファクトの mp4 を YouTube へ **非公開** で投稿 | 約1〜3分 |
| `gate-review.yml` | 手動 / `docs/gate1/slugs.txt` への push | 既存 sim 実行の `sim-<slug>` を再取得し、コンタクトシートを `docs/gate1/` に集めてコミット | 約30秒 |
| `catalog.yml` | `concepts/` `scenes/` への push / PR / 手動 | 企画とシーンを突き合わせて `docs/catalog/` を再生成。error があれば失敗 | 約1分 |

`docs/` 以下の生成ビュー:

| ビュー | 何が分かるか | いつ更新されるか |
|---|---|---|
| `docs/gate1/` | Phase 1 の画づくり（コンタクトシート） | `gate-review` 実行時 |
| `docs/catalog/` | 企画とコードの整合（scene_script の実在・params の到達率・シーン契約） | `concepts/` か `scenes/` を触るたび自動 |

### 判定データの保存先

人が読むビューは `docs/` に、機械可読なデータは `outputs/` に出す。
`outputs/` は gitignore なので、**CI では成果物はアーティファクト経由で受け取る**。

| 生成物 | ローカル | CI | git |
|---|---|---|---|
| 企画カタログ（JSON/CSV） | `outputs/catalog/catalog.json` / `concepts.csv` | `catalog-report`（14日） | しない |
| Phase 1 判定データ（JSON/CSV） | `outputs/gate1/gate1.json` / `gate1.csv` | `gate1-report`（30日） | しない |
| 投稿レシート（JSON） | `outputs/uploads/<slug>.json` | `upload-<slug>`（30日） | しない |
| **合否の記録** | `docs/gate1/verdicts.yaml` | 同左 | **する（人が手で書く）** |
| 企画カタログ（Markdown） | `docs/catalog/README.md` | 同左 | する |

判定の結論は `verdicts.yaml` だけが永続する。数字はいつでも再生成できるが、
「なぜ不合格にしたか」は再生成できないため。CSV は BOM 付き UTF-8 で書くので
Excel でそのまま開ける。

```bash
python scripts/chaosim.py catalog        # docs/catalog/ と outputs/catalog/
python scripts/chaosim.py gate1-report   # outputs/gate1/
python scripts/chaosim.py gate1-report --check   # 未判定が残っていれば exit 1
```

## 使い方

1. ローカルで企画を作り、YAML をコミットする。
   ```bash
   python scripts/chaosim.py plan --topic "domino chain" --local
   git add concepts/generated/<slug>.yaml && git commit && git push
   ```
2. GitHub の **Actions → sim → Run workflow** から実行する。
   - `concept`: `concepts/generated/<slug>.yaml`
   - `preset`: `preview`（既定）
   - `engine`: `CYCLES`（既定）
3. run が終わったら Artifacts の **`sim-<slug>`** をダウンロードする。
   - `<slug>.mp4` — レンダー結果
   - `<slug>_contact.png` — 等間隔6フレームのコンタクトシート。
     `docs/production-plan.md` の Gate 1→2（画づくりの合否）をここで判断する
   - `<slug>_events.json` — SFX 用の衝突イベント
   - `<slug>_render.log` — 実行ログ
4. 同じ run の **`upload`** ジョブが、その mp4 を YouTube へ**非公開**で投稿する
   （`sim` の入力 `upload` を `false` にすればスキップされる）。
   ジョブサマリに動画 URL が出るので、YouTube Studio で中身を確認する。
   公開への昇格は自動化しない —— `docs/production-plan.md` の Gate 4 を人が通す。
5. 複数企画をまとめて見比べるときは **`gate-review`** を回す。
   実行済みの sim から `sim-<slug>` を再取得して `docs/gate1/` にコミットするので、
   zip を1本ずつ落とさずリポジトリ上でコンタクトシートを並べて判定できる
   （レンダーはやり直さない）。対象は `docs/gate1/slugs.txt` で指定する。
   mp4 はコミットしないので、動きを見るときは Artifacts から取る。

## YouTube 投稿（`upload`）

### YouTube に「下書き」状態は無い

YouTube Data API に draft という状態は存在しない。`status.privacyStatus: "private"` が
その代わりになる。さらに **Google の監査を通していない API プロジェクトからの `videos.insert`
は強制的に private にロックされる**（2020-07-28 以降に作成したプロジェクト）ので、
下書き用途なら監査申請は不要。`upload.yml` は `public` を入力として受け付けない。

### セットアップ（初回のみ）

1. Google Cloud Console で **YouTube Data API v3** を有効化する。
2. OAuth クライアント（種別 **Desktop app**）を作成し、JSON を
   `config/youtube_client_secret.json` に置く（`.gitignore` 済み）。
3. **OAuth 同意画面を "In Production" に publish する。**
   "Testing" のままだと**リフレッシュトークンが7日で失効**し、CI が週明けに必ず落ちる。
   審査を通していないアプリなので同意画面に警告が出るが、自分のアカウントなら続行できる。
4. 手元でトークンを発行する（ブラウザが開く）。
   ```bash
   python scripts/chaosim.py youtube-auth
   ```
5. 出力された3つの値を GitHub の **Settings → Environments → `youtube`** に
   シークレットとして登録する。
   - `YOUTUBE_CLIENT_ID`
   - `YOUTUBE_CLIENT_SECRET`
   - `YOUTUBE_REFRESH_TOKEN`

   この Environment に required reviewer を足せば、投稿を人間の承認待ちにできる。
6. 疎通確認は `dry_run: true` で。認証・アーティファクト展開・ffprobe 検査までを
   quota を消費せずに通せる。

### 認証の優先順位

`pipeline/uploader.py` は **環境変数のリフレッシュトークン → `config/youtube_token.pickle`
→ ブラウザ同意** の順に試す。CI では 1 番目しか成立しない。
`CI` / `GITHUB_ACTIONS` が立っている状態で 3 番目に落ちたときは、`run_local_server()` を
呼ぶ前に明示的なエラーで止める（ランナー上でブラウザ待ちにハングさせないため）。

### quota

`videos.insert` は 1600 units、`thumbnails.set` は 50 units。既定の日次上限は 10,000 units
なので、**1日あたり約6本が上限**。`preset: preview` の確認レンダーまで毎回自動投稿すると
すぐ枯れるので、検証を繰り返すときは `sim` の入力 `upload` を `false` にする。

### 投稿されるメタデータ

concept YAML 由来。`caption` → タイトル（100文字で切り詰め）、`description` → 説明
（末尾に `#Shorts` と CI run の URL を付与）、`hashtags` → タグ（`Shorts` を追加）。
`categoryId` は `config/settings.yaml` の `youtube.category_id`。
登録者への通知は `notifySubscribers=False` で抑止している。

投稿後、`outputs/uploads/<slug>.json` にレシート（video id・URL・公開設定・run URL）が
残り、`upload-<slug>` アーティファクトとして30日保持される。

## プリセットとコストの制約

GitHub-hosted ランナーは CPU 4コアのみで、1ジョブ6時間の上限がある。

| preset | 解像度 | samples | 6秒尺の目安 | 30秒尺の目安 |
|---|---|---|---|---|
| `preview` | 540x960 / 30fps | 32 | 10〜20分 | 45〜90分 |
| `medium` | 1080x1920 / 60fps | 128 | 2〜4時間 | 8〜20時間 |
| `high` | 1080x1920 / 60fps | 512 | 6〜16時間 | 30〜80時間 |
| `ultra` | 1080x1920 / 60fps | 2048 | 1〜2.5日 | — |

このため:

- **ワークフローは必ず `--preset` を明示的に渡す。** `pipeline/renderer.py` は未指定時に
  企画YAMLの `render_preset` を使うが、`concepts/generated/` 以外の企画はすべて
  `high` かつ20〜30秒尺なので、そのままでは確実に6時間を超える。
- `high` / `ultra` は `allow_expensive: true` を付けない限りガードステップで即失敗する。
  6時間使い切ってから落ちるのを防ぐため。
- `max_frames`（既定900）が `CHAOSIM_MAX_FRAMES` としてフレーム数を打ち切る。
  `render_staged()` を持つシーン（`paper_to_cloth` / `cloth_drop_faces`）にも効くが、
  打ち切り方が違う。**段数（`face_counts`）は減らさず、1段あたりの
  `stage_duration_sec` を縮めて上限に収める。** 段階シーンは「面数を上げるほど布になる」
  という進行そのものが hook なので、段を落とすと判定材料にならないため。
  例: `max_frames=180` × 4段 → 1段45フレーム（1.5秒）。
  短すぎて動きが読めない場合は `max_frames` を上げて回し直す。

**本番画質（`medium` 以上）はローカル実行を推奨。**

## レンダーエンジン

`simulators/blender/runner.py` は既定で EEVEE → Cycles の順に試すが、EEVEE は GL コンテキストを
要求するためヘッドレスのランナーでは異常終了するか**黒フレームを出す**。黒フレームは mux に
成功してしまうのでジョブは緑になる。これを避けるため `sim.yml` は
`CHAOSIM_RENDER_ENGINE=CYCLES` を設定する。環境変数が未設定なら従来どおりの自動判定なので、
ローカルの挙動は変わらない。

## スタブ落ちの検知

`blender_available()` は Blender が無くても例外を投げず `False` を返し、`_stub_render()` が
`testsrc2` のダミー動画を書く。何もしなければ**中身がテスト映像のままジョブが緑になる**。
`sim.yml` は4段構えでこれを検知する。

1. `<slug>_concept.json` の存在。`renderer.py` はスタブ経路で先に return するため、
   その後に書かれるこのファイルはスタブでは絶対に生成されない（偽装不可の証拠）
2. `<slug>_events.json` の存在。Blender 内部の `runner.py` が完走した証拠
3. ログに `Blender not available` が無く、`Engine=<要求したエンジン>` が出ていること
4. `ffprobe` で h264・フレーム数>1・`preview` なら 540x960
   （スタブは常に 1080x1920 なので区別できる）

## artifact 契約（後続工程用）

各工程は `<stage>-<slug>` を publish し、**パスは repo root 起点**にする。こうすると下流ジョブが
`actions/download-artifact` に `path: .` を指定するだけで `pipeline/workflow.py` が前提とする
`outputs/` 構成がそのまま再現され、コード側の変更が要らない。

| artifact | 中身 |
|---|---|
| `sim-<slug>` | `outputs/renders/<slug>.{mp4,_events.json,_concept.json,_contact.png}` |
| `catalog-report` | `outputs/catalog/{catalog.json,concepts.csv}` + `docs/catalog/README.md` |
| `gate1-report` | `outputs/gate1/{gate1.json,gate1.csv}` + `docs/gate1/verdicts.yaml` + コンタクトシート |
| `material-<slug>` | `outputs/material/<slug>/**` |
| `narration-<slug>` | `outputs/audio/<slug>_narration.wav` |
| `compose-<slug>` | `outputs/final/<slug>_final.mp4` |
| `thumb-<slug>` | `outputs/final/<slug>_thumb.png` |
| `upload-<slug>` | `outputs/uploads/<slug>.json`（投稿レシート） |

単独 dispatch 時は入力 `run_id` を受け、`actions/download-artifact@v4` の
`run-id` + `github-token` で run をまたいで取得する（`permissions: actions: read` が必要）。
orchestrator 経由なら同一 run 内でそのまま解決される。`upload.yml` がこの形の実装例。

`upload.yml` は**アーティファクトの中身に依存しない**：`outputs/final/<slug>_final.mp4`
→ `outputs/renders/<slug>.mp4` → 最初に見つかった `*.mp4` の順に探す。
`compose-<slug>` が実装されたら `sim.yml` 側の `artifact:` を差し替えるだけで移行できる。

## 今後の工程で必要になる作業

- **material**: Node ＋ Chrome の解決が必要（HyperFrames は `puppeteer-core` を使う）。
  `setup-chaosim` の `node` / `npm-ci` 入力が受け皿として用意済み。
- **narration**: VOICEVOX を `services:` コンテナで起動し、`/version` を readiness poll する。
  でないと `voicevox_available()` が黙って `False` を返し無音になる。
- **compose**: `pipeline/workflow.py` は `stage_material()` を `stages` に関わらず無条件に呼び、
  かつ「出力が既にあればスキップ」のガードが無い。このままだと compose 専用ジョブが
  ダウンロード済み素材を捨てて再レンダーしてしまう。`stage_compose` はディレクトリではなく
  セグメントのリストを受け取るため、素材を再レンダーせずディスクから組み立てる
  `collect_material_segments()` 相当の追加が必要になる。
- **SFX**: 音源が macOS の `/System/Library/Sounds` 依存で Linux では鳴らない
  （警告を出して `None` を返すだけで落ちはしない）。`docs/sfx-design.md` の
  Proposal A/B が入るまで CI の完成動画は SFX 無しになる。
- **フレーム単位の再開**: `runner.py` は起動時に `frames_dir` を毎回削除するため、
  `docs/media-pipeline-playbook.md` §3 の再開設計を CI に持ち込むにはこの削除の抑止が必要。
- **upload の入力切り替え**: compose が CI 化されるまで、`upload` が投稿するのは生素材。
  `compose-<slug>` ができたら `sim.yml` の `upload` ジョブに渡す `artifact:` を
  そちらへ向ける（`upload.yml` 自体の変更は不要）。
