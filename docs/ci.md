# GitHub Actions での実行

企画（`plan`）はローカルのまま、それ以降の工程を GitHub Actions 上で回すための構成。
成果物は各 run の Artifacts からダウンロードできる。

現在実装済みなのは **`ci`（配線チェック）** と **`sim`（シミュレーション）** の2本。
material / narration / composite / thumbnail と、それらを束ねる orchestrator は今後追加する。

## ワークフロー一覧

| ワークフロー | トリガ | 用途 | 所要 |
|---|---|---|---|
| `ci.yml` | push(main) / PR / 手動 | スタブモードで全工程を通し、配線と共通セットアップを検証 | 約2〜5分 |
| `sim.yml` | 手動 / `workflow_call` | Blender シミュレーション＋レンダー | preview 6秒尺で約10〜20分 |

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
  ただし `render_staged()` を持つシーン（`paper_to_cloth` / `cloth_drop_faces`）は
  自前で `frame_end` を決めるため対象外。

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
| `material-<slug>` | `outputs/material/<slug>/**` |
| `narration-<slug>` | `outputs/audio/<slug>_narration.wav` |
| `compose-<slug>` | `outputs/final/<slug>_final.mp4` |
| `thumb-<slug>` | `outputs/final/<slug>_thumb.png` |

単独 dispatch 時は入力 `upstream_run_id` を受け、`actions/download-artifact@v4` の
`run-id` + `github-token` で run をまたいで取得する（`permissions: actions: read` が必要）。
orchestrator 経由なら同一 run 内でそのまま解決される。

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
