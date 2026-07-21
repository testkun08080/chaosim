# 制作ガイド — カオスシム・ショート量産パイプライン

Kawaken_3DCG / Kintsugi_3DCG のような 3DCG 物理シミュレーション系ショート動画を、
本リポジトリ（Blender + HyperFrames + FFmpeg + VOICEVOX）で企画から投稿まで一貫制作するための
**セットアップ・運用手順**と、**フェーズ・ゲート制の制作計画**を1つにまとめたガイド。
すべて既存の CLI（`scripts/chaosim.py`）に紐付けてある。

- **参考チャンネル:** [@Kawaken_3DCG](https://www.youtube.com/@Kawaken_3DCG/videos) / [@Kintsugi_3DCG](https://www.youtube.com/@Kintsugi_3DCG)
- **参考動画（構成・音の付け方）:** https://www.youtube.com/watch?v=3Rh_qusBOTw
- **効果音の設計:** [docs/sfx-design.md](./sfx-design.md)（本ガイドの Phase 3 の中身）
- **横断的な設計原則（他プロジェクト流用版）:** [docs/media-pipeline-playbook.md](./media-pipeline-playbook.md)

> このガイドは 2 部構成。**第 I 部**が環境構築と日々の運用（旧 workflow.md）、
> **第 II 部**がフェーズ・ゲート制の制作計画。初めての1本は第 II 部のフェーズ順で回し、
> 量産に入ってから第 I 部の全自動パターンに移る。

---

# 第 I 部 — セットアップと運用

## 全体の流れ（最短経路）

```
[トピック入力]
      │
      ▼
 1. plan   ── Claude API ──▶  concepts/generated/xxx.yaml
      │
      ▼
 2. render ── Blender ──────▶  outputs/renders/xxx.mp4
      │
      ▼
 3. compose ── HyperFrames + FFmpeg ──▶  outputs/final/xxx_final.mp4
      │
      ▼
 4. upload ── YouTube API ──▶  https://youtube.com/shorts/xxx
```

## セットアップ

### 1. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

```bash
cp .env.example .env
# .env を開いて各値を埋める
```

| 変数 | 説明 |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API キー（企画生成に使用） |
| `BLENDER_PATH` | Blender 実行ファイルのパス（例: `/usr/bin/blender`） |
| `HYPERFRAMES_PATH` | HyperFrames CLI（既定 `./node_modules/.bin/hyperframes`） |
| `HYPERFRAMES_FFMPEG_PATH` | 必要時のみ。static-ffmpeg v8 非互換の回避用 |
| `YOUTUBE_CLIENT_SECRET_PATH` | YouTube OAuth2 クライアントシークレット JSON のパス |
| `VOICEVOX_URL` | VOICEVOX エンジンの URL（既定 `http://localhost:50021`） |
| `RENDER_DEVICE` | `GPU` または `CPU`（デフォルト: CPU） |

### 3. Blender の確認

```bash
python scripts/blender_bootstrap.py /path/to/blender
```

Blender の Python 環境に PyYAML が自動でインストールされる。

> **注意（環境依存の落とし穴）:** HTML→動画レンダー（HyperFrames）は node を、合成は ffmpeg を必要とする。
> GUI や非対話シェルから起動したサブプロセスは PATH が貧弱で node/ffmpeg を見失うことがある。
> その場合はログイン対話シェル（`zsh -l -i -c ...`）で起動して PATH を揃える。詳細は
> [media-pipeline-playbook.md](./media-pipeline-playbook.md) 第5・6章。

## 運用パターン

### パターン A — 全自動（量産フェーズ向け）

トピックから作った企画を、企画以外の全ステージ一括で回す。

```bash
# 動画だけ作る
python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml

# YouTube まで（private でアップロード）
python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml --upload

# 一部ステージだけ回す（例: 素材＋合成のみ、sim は既存を流用）
python scripts/chaosim.py run concepts/generated/<slug>.yaml --stages material,compose
```

### パターン B — ステップごとに実行（初回・調整向け）

```bash
# Step 1: 企画を AI 生成（生成物は concepts/generated/<slug>.yaml）
python scripts/chaosim.py plan --topic "三重振り子"

# Step 2: レンダリング（品質は --preset で切替）
python scripts/chaosim.py render concepts/generated/triple_pendulum.yaml --preset preview

# Step 3: YouTube にアップロード
python scripts/chaosim.py upload outputs/final/triple_pendulum_final.mp4 \
    --concept concepts/generated/triple_pendulum.yaml \
    --privacy private
```

初回アップロードは OAuth2 ブラウザ認証が開く。以降はトークンが `config/youtube_token.pickle` に
キャッシュされる（スコープを変えた場合はこのファイルを削除して再認証）。

### パターン C — サンプル企画をそのまま使う

```bash
python scripts/chaosim.py list-concepts        # 一覧確認
make sample-run                                # sample_001 を全工程実行
python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml
```

## Makefile ショートカット

```bash
make install          # 依存インストール
make sample-run       # sample_001 を全工程実行
make render CONCEPT=concepts/sample_002_fluid_ink.yaml
make plan TOPIC="ローレンツアトラクター"
make upload VIDEO=outputs/final/xxx_final.mp4
make clean            # outputs/ を掃除
```

## 新しいシミュレーションを追加する

1. **シーンスクリプトを作る** — `simulators/blender/scenes/my_sim.py` に
   `setup_scene(params)` と `run_simulation()` を実装（比較デモなら `render_staged` も）。
   Blender 内で動くので相対 import は使わない（自己完結）。

2. **登録する**

   ```python
   # simulators/blender/__init__.py
   AVAILABLE_SCENES = [
       ...,
       "my_sim",   # 追加
   ]
   ```

3. **企画 YAML を書く**

   ```yaml
   # concepts/my_sim_concept.yaml
   scene_script: my_sim
   params:
     my_param: 42
   ```

4. **実行**

   ```bash
   python scripts/chaosim.py render concepts/my_sim_concept.yaml --preset preview
   ```

## Claude Code / Cursor との連携

プロジェクトルートの `CLAUDE.md` に主要コマンドとアーキテクチャが書いてあり、
Claude Code がセッション開始時に自動で読み込む。よくある依頼例:

```
「simulators/blender/scenes/ に磁気振り子のシミュレーションを追加して」
「"ダブルロータリーペンデュラム" の企画 YAML を生成して」
「sample_001 の pendulum_count を 20 にしたバリエーション YAML を作って」
```

---

# 第 II 部 — フェーズ・ゲート制の制作計画

## 0. 全体方針

ショート1本を「使い捨てのレンダリング」ではなく、**フェーズ・ゲート制**で作る。
各フェーズには「ここを通過しないと次に進まない」チェック基準（ゲート）を置き、
**重いフル解像度レンダリングは Phase 1（バーティカルスライス）を通過してから**しか回さない。
これにより、画角・質感が決まっていない状態での高コストな作り直しを防ぐ。

```
Phase 0 企画        →  Phase 1 バーティカルスライス  →  Phase 2 バリエーション展開
（YAML1枚）            （1本を低解像度で画づくり検証）    （当たりを量産・本番レンダー）
                                                              │
Phase 4 仕上げ・投稿  ←  Phase 3 コンポジット  ←──────────────┘
（サムネ・書き出し・投稿） （字幕・ナレーション・効果音・BGM）
```

制作単位は **1企画 = 1 YAML = 1本**。バリエーションは YAML を複製してパラメータだけ変える。

---

## Phase 0 — 企画（Concept）

**目的:** 「何を・どう見せて・なぜバズるか」を YAML 1枚に落とす。

```bash
# AI 企画生成（ANTHROPIC_API_KEY 使用）
python scripts/chaosim.py plan --topic "三重振り子"

# API を使わずローカルテンプレートで即レンダー可能な企画を出す
python scripts/chaosim.py plan --topic "colorful domino" --local
```

生成物は `concepts/generated/<slug>.yaml`。手編集して確定させる。
主要フィールドは [concepts-guide.md](./concepts-guide.md) を参照。企画段階で必ず埋めるもの:

| フィールド | 企画上の意味 |
|---|---|
| `hook` | 最初の3秒で何が起きるか（離脱を防ぐ核） |
| `scene_script` | 使うシミュレーター（`simulators/blender/scenes/*.py` に存在必須） |
| `duration_sec` | 尺（Shorts は 59 秒以下、まずは 6〜15 秒を推奨） |
| `viral_angle` | バズ仮説（参考チャンネルのどの型に寄せるか） |
| `params` | シーンに渡す物理パラメータ |

**ゲート 0 → 1（企画レビュー）**

- [ ] `hook` が一文で言える（「壁が消えた瞬間に崩れる」等）
- [ ] `scene_script` が実在する（`python scripts/chaosim.py list-concepts` で確認）
- [ ] 尺と縦横比（9:16）が決まっている
- [ ] 参考チャンネルの類似構成が1つ言える（差別化ポイントも）

---

## Phase 1 — バーティカルスライス（画づくり検証）

**目的:** 1本だけを**低解像度・数フレーム**で回し、**画角（カメラ）と質感（マテリアル/ライティング）**を
確定させる。ここが全工程で最もやり直しコストの高い部分なので、安いうちに潰す。

### 1-a. シーン構築とルックデブ（インタラクティブ）

Blender を GUI で開き、同梱アドオンで画角・質感を詰める。

- `simulators/blender/addons/chaosim_scene_tools/` — レンダープリセット・Shorts 縦画面設定
- `simulators/blender/addons/lookdev_material_tool/` — LookDev マテリアル切替

アドオンのインストールと開発は [blender-addon-development.md](./blender-addon-development.md) を参照。
Blender MCP が接続されていれば、`render_viewport_to_path` / `render_thumbnail_to_path` で
ビューポートの当たりを即キャプチャして画角を検討できる。

### 1-b. 低解像度スライスレンダー（自動・ゲート用）

`preview` プリセット（サンプル32・解像度50%・30fps）でシミュレーションを回し、
**代表フレーム数枚**を静止画として書き出してコンタクトシート化する。

```bash
python scripts/chaosim.py render concepts/generated/<slug>.yaml --preset preview
```

> **仕様追加提案（未実装）:** 数フレームだけを書き出す軽量サブコマンド `slice` を追加する。
> 全編を焼かず「頭・中間・末尾」の3〜5フレームだけを PNG 出力し、質感/画角の確認を秒で回す。
>
> ```bash
> python scripts/chaosim.py slice concepts/generated/<slug>.yaml \
>     --frames "1,mid,last" --preset preview
> # → outputs/slices/<slug>/frame_XXXX.png（＋コンタクトシート .png）
> ```
>
> 実装は `bake_sfx_events.py` と同じく Blender をバックグラウンド起動し、
> `setup_scene`→`run_simulation` の後に指定フレームだけ `bpy.ops.render.render(write_still=True)`。

### 1-c. 効果音の同時ベイク（任意・早期確認）

このフェーズで衝突イベントを一度ベイクしておくと、Phase 3 の音付けが早い。

```bash
blender --background --python scripts/bake_sfx_events.py -- \
    <concept.json> outputs/renders/<slug>_events.json
```

**ゲート 1 → 2（画づくり承認）**

- [ ] カメラの画角・寄り引きが 9:16 で決まった（被写体が縦画面で映える）
- [ ] マテリアル/ライティングの方向性が確定（グロー・背景色・反射など）
- [ ] シミュレーションが破綻していない（貫通・爆発・停止がない）
- [ ] `hook` が preview の数フレームで成立している（最初の見せ場が画角内）
- [ ] 想定尺に収まる動きになっている

**このゲートを通るまで `medium`/`high`/`ultra` は回さない。**

---

## Phase 2 — バリエーション展開・本番レンダー

**目的:** 承認された画づくりを土台に、`params` を振ってバリエーションを増やし、
本番品質でレンダーして「当たり」を選ぶ。

1. Phase 1 の YAML を複製し、`slug` と `params` だけを変える（色・個数・初期角・粘性など）。
2. まず `medium` で複数本を回して比較 → 良いものだけ `high`（本番）/`ultra`（アーカイブ）へ。

```bash
# バリエーションを medium で確認
python scripts/chaosim.py render concepts/generated/<slug>_v2.yaml --preset medium
# 当たりを本番品質へ
python scripts/chaosim.py render concepts/generated/<slug>_v2.yaml --preset high
```

| プリセット | 用途 |
|---|---|
| `preview` | Phase 1 の画づくり検証（速い） |
| `medium` | バリエーション比較 |
| `high` | 本番投稿用 |
| `ultra` | アーカイブ・コンペ用 |

> **比較デモの分割レンダー:** 面数比較のように複数ステージを1本に収める場合は、
> ステージ別サブディレクトリ（連番フレーム）→ ステージ毎に `seg_*.mp4` → 最後に concat、
> という分割構成にすると、途中で落ちても未完のステージだけ焼き直せる。ベイクは連続性が要るので、
> 途中フレームを描き足すときは当該ステージを丸ごと再ベイクしてから欠損レンジを描く。

**ゲート 2 → 3（本番素材確定）**

- [ ] 投稿する本数分の `outputs/renders/<slug>.mp4` が揃った
- [ ] 各本で最も映えるバリエーションを選定済み
- [ ] （音を付けるなら）`<slug>_events.json` が本番と同じシミュレーションからベイクされている

---

## Phase 3 — コンポジット（字幕・ナレーション・効果音・BGM）

**目的:** シミュレーション素材に、タイトル/アウトロ、日本語ナレーションと字幕、
**効果音**、BGM を重ねて完成尺にする。詳細な効果音設計は [docs/sfx-design.md](./sfx-design.md)。

パイプライン内部の流れ（`pipeline/workflow.py` / `compositor.py`）:

```
1. base 連結    intro（HyperFrames）→ sim（Blender）→ outro を縦画面で連結
2. overlay      透過 HyperFrames クリップを時間指定で重畳（ロワーサード・面数カウント等）
3. captions     ナレーション行を drawtext で焼き込み（sim 開始に同期）
4. audio mix    ナレーション + BGM + 効果音キュー を映像下にミックス
5. shorts encode 9:16・尺制限に整形（ensure_shorts_format）
```

```bash
# 素材（intro/outro/overlay）だけ先に確認
python scripts/chaosim.py material concepts/generated/<slug>.yaml

# ナレーション音声だけ生成（VOICEVOX）
python scripts/chaosim.py narrate concepts/generated/<slug>.yaml --speaker 3

# 一括コンポジット（sim→material→narration→compose）
python scripts/chaosim.py compose concepts/generated/<slug>.yaml
```

オーバーレイ（面数カウント等）は concept の `segments:` に `track: overlay` として宣言する
（テンプレートは `templates/hyperframes/*.j2`）。データ駆動なので数字や位置は YAML で決まる。

> **透過オーバーレイの落とし穴（実際に踏んだもの）:** 透過は「アルファのメタがある」だけでは
> 合成で透けない。VP9/webm はデコード時に `-c:v libvpx-vp9` を明示しないとアルファ面が捨てられ、
> 背景が真っ黒になる。また透過出力に解像度プリセットを併用すると HyperFrames がエラーになる。
> 詳細は [media-pipeline-playbook.md](./media-pipeline-playbook.md) 第6章。

音の3系統は `templates/video/<template>.yaml` と `config/settings.yaml` の
`compositing:` で制御する:

| 系統 | 制御元 | 既定音量 |
|---|---|---|
| ナレーション | 企画 `narration.lines` ＋ VOICEVOX | 1.0 |
| BGM | `music_mood` → `assets/audio/catalog.yaml` | 0.18 |
| 効果音（SFX） | 動画テンプレの `sfx.cues` ＋ `<slug>_events.json` | 0.55 |

**ゲート 3 → 4（コンポジット確認）**

- [ ] 字幕がナレーションと合っている（尺・改行・読みやすさ）
- [ ] 効果音がイベント（衝突・着弾・崩落）と同期している（詳細は sfx-design.md のチェック）
- [ ] BGM がナレーション/効果音を潰していない（ダッキング確認）
- [ ] 全体音量が突き刺さらない（Phase 4 のラウドネス正規化前提）

---

## Phase 4 — 仕上げ・書き出し・投稿

**目的:** サムネイル生成、最終エンコード、YouTube への限定公開→レビュー→公開。

```bash
# サムネイル
python scripts/chaosim.py thumbnail concepts/generated/<slug>.yaml

# フルパイプライン（compose まで＋サムネ）をまとめて
python scripts/chaosim.py run concepts/generated/<slug>.yaml

# 限定公開でアップロード（まず private）
python scripts/chaosim.py upload outputs/final/<slug>_final.mp4 \
    --concept concepts/generated/<slug>.yaml --privacy private
```

**ゲート 4（公開前チェック）**

- [ ] `outputs/final/<slug>_final.mp4` が 9:16・59秒以内・音声ありで再生できる
- [ ] サムネイルが縦画面で見て強い
- [ ] `caption` / `hashtags` が埋まっている
- [ ] private で実機（スマホ）確認 → 問題なければ public へ

---

## フェーズ ↔ コマンド早見表

| Phase | 目的 | コマンド |
|---|---|---|
| 0 企画 | YAML生成 | `chaosim.py plan --topic ... [--local]` |
| 1 スライス | 画角・質感検証 | `chaosim.py render ... --preset preview`（+ 提案 `slice`） |
| 2 展開 | 本番レンダー | `chaosim.py render ... --preset medium/high` |
| 3 コンポジット | 音・字幕合成 | `chaosim.py material` / `narrate` / `compose` |
| 4 仕上げ | サムネ・投稿 | `chaosim.py thumbnail` / `run` / `upload` |

`run` は 0 を除く全ステージを一括実行できるが、**初回の1本は必ずフェーズを分けて**回し、
各ゲートを人の目で通す。量産フェーズに入ってから `run` で自動化する。

---

## エンジン拡張ポイント

| エンジン | 対応方法 |
|---|---|
| Houdini | `simulators/houdini/` を追加し `base.py` を継承 |
| Unreal Engine 5 | `simulators/unreal/` を追加。concept YAML の `simulator: unreal` で切り替え |
| Unity | 同上 |

`pipeline/renderer.py` の `render_concept()` が `concept["simulator"]` の値でバックエンドを分岐する
構造にすることで、コア部分を変えずに拡張できる。

---

## 未実装・拡張バックログ（仕様提案・優先度順）

1. **`slice` サブコマンド** — Phase 1 用の数フレーム静止画レンダー＋コンタクトシート（上記 1-b）。
2. **イベント出力の全シーン対応と本番同時ベイク** — 現状 `collect_impact_events` は
   `domino_chain` 中心。全シーンで統一スキーマ（型＋強度付き）のイベントを、レンダーと同じベイクから
   出力する（sfx-design.md 参照）。
3. **SFX ライブラリの同梱** — macOS システムサウンド依存を、リポジトリ同梱のロイヤリティフリー
   SFX に置き換え（ポータビリティ・ライセンス・音質）。詳細は sfx-design.md。
4. **ラウドネス正規化** — 最終エンコードで YouTube 基準（-14 LUFS）に loudnorm を適用。
5. **バリエーション一括生成** — 1つの基準 YAML から `params` を振った複数 YAML を吐く
   `variants` サブコマンド。
6. **YouTube アップロードの検証** — OAuth2 認証（`youtube_client_secret.json` 設置＋初回認証）を通し、
   `upload` を実データで一度通す（現状このリンクのみ未検証）。
