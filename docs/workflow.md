# ワークフロー

## 全体の流れ

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
 3. postprocess ── FFmpeg ──▶  outputs/final/xxx_final.mp4
      │
      ▼
 4. upload ── YouTube API ──▶  https://youtube.com/shorts/xxx
```

---

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
| `YOUTUBE_CLIENT_SECRET_PATH` | YouTube OAuth2 クライアントシークレット JSON のパス |
| `RENDER_DEVICE` | `GPU` または `CPU`（デフォルト: CPU） |

### 3. Blender の確認

```bash
python scripts/blender_bootstrap.py /path/to/blender
```

Blender の Python 環境に PyYAML が自動でインストールされる。

---

## 使い方

### パターン A — 全自動（おすすめ）

トピックを渡すだけで企画〜アップロードまで全部動く。

```bash
python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml --upload
```

YouTube にアップロードせず動画だけ作る場合：

```bash
python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml
```

---

### パターン B — ステップごとに実行

#### Step 1: 企画を AI 生成する

```bash
python scripts/chaosim.py plan --topic "三重振り子"
# → concepts/generated/triple_pendulum.yaml が生成される
```

生成された YAML を確認・手編集してからレンダリングへ。

#### Step 2: レンダリング

```bash
python scripts/chaosim.py render concepts/generated/triple_pendulum.yaml
# → outputs/renders/triple_pendulum.mp4

# 品質を下げて素早く確認したい場合
python scripts/chaosim.py render concepts/generated/triple_pendulum.yaml --preset preview
```

#### Step 3: YouTube にアップロード

```bash
python scripts/chaosim.py upload outputs/final/triple_pendulum_final.mp4 \
    --concept concepts/generated/triple_pendulum.yaml \
    --privacy private
```

初回は OAuth2 ブラウザ認証が開く。以降はトークンが `config/youtube_token.pickle` にキャッシュされる。

---

### パターン C — サンプル企画をそのまま使う

```bash
# 一覧確認
python scripts/chaosim.py list-concepts

# サンプルを実行
make sample-run
# または
python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml
```

---

## Makefile ショートカット

```bash
make install          # 依存インストール
make sample-run       # sample_001 を全工程実行
make render CONCEPT=concepts/sample_002_fluid_ink.yaml
make plan TOPIC="ローレンツアトラクター"
make upload VIDEO=outputs/final/xxx_final.mp4
make clean            # outputs/ を掃除
```

---

## 新しいシミュレーションを追加する

1. **シーンスクリプトを作る**

```bash
# simulators/blender/scenes/my_sim.py を作成
# setup_scene(params) と run_simulation() を実装する
```

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

---

## 将来的な拡張ポイント

| エンジン | 対応方法 |
|---|---|
| Houdini | `simulators/houdini/` を追加し `base.py` を継承 |
| Unreal Engine 5 | `simulators/unreal/` を追加。concept YAML の `simulator: unreal` で切り替え |
| Unity | 同上 |

`pipeline/renderer.py` の `render_concept()` が `concept["simulator"]` の値を見てどのバックエンドを呼ぶか分岐する構造にすることで、コア部分を変えずに拡張できる。

---

## Claude Code / Cursor との連携

### CLAUDE.md
プロジェクトルートの `CLAUDE.md` に主要コマンドとアーキテクチャが書いてある。  
Claude Code がセッション開始時に自動で読み込むため、コンテキストなしで作業を依頼できる。

### よくある依頼例

```
# 新しいシミュレーターを追加してほしい場合
「simulators/blender/scenes/ に磁気振り子のシミュレーションを追加して」

# 企画だけ生成して中身を確認したい
「"ダブルロータリーペンデュラム" の企画 YAML を生成して」

# パラメーターを変えてバリエーションを出す
「sample_001 の pendulum_count を 20 にしたバリエーション YAML を作って」
```
