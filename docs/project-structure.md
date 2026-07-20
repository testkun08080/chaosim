# プロジェクト構造

## ディレクトリ全体図

```
chaosim/
├── docs/                        # ドキュメント (このフォルダ)
│
├── concepts/                    # 動画の企画書 (YAML)
│   ├── sample_001_double_pendulum.yaml
│   ├── sample_002_fluid_ink.yaml
│   ├── sample_003_sand_collapse.yaml
│   ├── sample_004_lorenz_attractor.yaml
│   ├── sample_005_domino_chain.yaml
│   └── generated/               # AI生成された企画 (自動作成)
│
├── pipeline/                    # パイプライン処理モジュール
│   ├── planner.py               # Claude API で企画を自動生成
│   ├── renderer.py              # Blender をサブプロセスで起動・レンダリング
│   ├── postprocess.py           # FFmpeg で動画を Shorts 仕様に変換
│   ├── uploader.py              # YouTube API でアップロード
│   └── workflow.py              # 全工程をつなぐオーケストレーター
│
├── simulators/
│   ├── base.py                  # シミュレーター基底クラス (抽象)
│   └── blender/
│       ├── runner.py            # Blender 内で実行されるエントリポイント
│       ├── utils.py             # カメラ・ライト・シーンのユーティリティ
│       ├── addons/              # インタラクティブ用アドオン (Git 管理)
│       │   ├── chaosim_scene_tools/   # レンダープリセット・Shorts 設定
│       │   └── lookdev_material_tool/ # LookDev マテリアル切替
│       └── scenes/              # シミュレーション種別ごとのスクリプト
│           ├── double_pendulum.py
│           ├── fluid_ink.py
│           ├── sand_collapse.py
│           ├── lorenz_attractor.py
│           └── domino_chain.py
│
├── config/
│   ├── settings.yaml            # パス・解像度・FPS などのグローバル設定
│   └── render_presets.yaml      # レンダリング品質プリセット (preview〜ultra)
│
├── scripts/
│   ├── chaosim.py               # メイン CLI (plan / render / run / upload)
│   ├── blender_bootstrap.py     # Blender 環境の初期セットアップ
│   └── install_blender_addons.py # アドオンを symlink インストール
│
├── outputs/                     # gitignore 済み・生成物の置き場
│   ├── renders/                 # Blender が出力した生の動画
│   ├── final/                   # FFmpeg 変換済みの最終動画
│   └── uploads/                 # アップロード済みのログ
│
├── .env.example                 # 環境変数のテンプレート
├── pyproject.toml               # Python パッケージ設定
├── requirements.txt             # 依存ライブラリ
├── Makefile                     # よく使うコマンドのショートカット
└── CLAUDE.md                    # Claude Code 向けプロジェクト情報
```

## 各層の役割

### concepts/ — 企画書レイヤー
動画 1 本 = YAML 1 ファイル。何をどう作るかをすべて記述する。
Claude API が生成することも、手書きすることも可能。

| フィールド | 役割 |
|---|---|
| `scene_script` | どのシミュレーターを使うか |
| `params` | シーンに渡すパラメーター（重力・粒子数など） |
| `render_preset` | 品質設定 |
| `caption` / `hashtags` | YouTube 投稿時のメタデータ |

### pipeline/ — 処理レイヤー
企画 YAML を受け取って動画にするまでの各ステップ。

```
planner.py   →  Claude API で YAML を生成
renderer.py  →  Blender をバックグラウンド起動してレンダリング
postprocess.py → FFmpeg で 9:16 / 59秒以内に整形
uploader.py  →  YouTube Data API v3 でアップロード
workflow.py  →  上記を順番に呼び出すだけ
```

### simulators/blender/ — Blender レイヤー
Blender の Python 環境内で動くスクリプト群。  
`runner.py` が YAML を読んで対応する `scenes/*.py` を動的にロードする。

**2 種類の Python スクリプト:**

| 種類 | パス | 実行 |
|------|------|------|
| バッチ（パイプライン） | `scenes/*.py` | `runner.py` 経由・GUI なし |
| アドオン（手作業ツール） | `addons/*/` | Blender 内サイドバー UI |

アドオン開発の詳細は [blender-addon-development.md](./blender-addon-development.md) を参照。

各 `scenes/*.py` は必ず 2 つの関数を実装する：

```python
def setup_scene(params: dict) -> None:
    # カメラ・ライト・オブジェクトをセット
    ...

def run_simulation() -> None:
    # 物理演算のベイクやキーフレーム挿入
    ...
```

### config/ — 設定レイヤー
コードを変えずに挙動を調整できる部分をここに集約。

`render_presets.yaml` のプリセット一覧：

| プリセット | サンプル数 | 解像度 | 用途 |
|---|---|---|---|
| `preview` | 32 | 50% | 動作確認・高速チェック |
| `medium` | 128 | 100% | 日常の開発確認 |
| `high` | 512 | 100% | 本番投稿用 |
| `ultra` | 2048 | 100% | アーカイブ・コンペ用 |
