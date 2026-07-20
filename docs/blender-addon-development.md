# Blender アドオン開発ガイド（Chaosim 向け）

Chaosim プロジェクトで Blender 用ツール（アドオン）を作り、チームで共有するための実践ガイドです。

## 目次

1. [3 種類のスクリプトの違い](#1-3-種類のスクリプトの違い)
2. [UI の作り方](#2-ui-の作り方)
3. [Operator（実行処理）の書き方](#3-operator実行処理の書き方)
4. [ファイルの置き場所](#4-ファイルの置き場所)
5. [プロジェクトごとの共有方法](#5-プロジェクトごとの共有方法)
6. [インストールと有効化](#6-インストールと有効化)
7. [開発サイクル](#7-開発サイクル)
8. [Chaosim 内のサンプルアドオン](#8-chaosim-内のサンプルアドオン)

---

## 1. 3 種類のスクリプトの違い

Chaosim では Blender 向け Python を **用途別に 3 層** に分けます。

| 種類 | 置き場所 | 実行方法 | UI | 用途 |
|------|----------|----------|-----|------|
| **シーンスクリプト** | `simulators/blender/scenes/` | `blender --background --python runner.py` | なし | パイプライン自動レンダー |
| **ユーティリティ** | `simulators/blender/utils.py` | scenes から import | なし | 共通処理（カメラ・ライト等） |
| **アドオン** | `simulators/blender/addons/` | Blender 内で常駐 | あり | 手作業の LookDev・シーン調整 |

### シーンスクリプト（バッチ用）

パイプラインが **GUI なし** で呼び出します。`runner.py` が YAML を読み、対応する `scenes/*.py` を動的ロードします。

```bash
blender --background --python simulators/blender/runner.py -- concepts/sample_001.yaml output.mp4 medium
```

各シーンは次の 2 関数を実装します。

```python
def setup_scene(params: dict) -> None: ...
def run_simulation() -> None: ...
```

**相対 import は不可**（Blender 内で `importlib` ロードされるため）。必要な処理はファイル内に書くか、`utils.py` を同様にロードします。

### アドオン（インタラクティブ用）

Blender を **GUI で開いたまま** 使うツールです。サイドバーパネル・メニュー・ショートカットを提供します。

- LookDev 用マテリアル切り替え → `lookdev_material_tool`
- レンダー設定・Shorts 向けセットアップ → `chaosim_scene_tools`

---

## 2. UI の作り方

Blender の UI は **Panel / Menu / Header** クラスで定義します。レイアウトは `layout` オブジェクトで組み立てます。

### 最小構成

```python
import bpy
from bpy.types import Panel

class CHAOSIM_PT_example(Panel):
    bl_label = "Chaosim Tools"       # パネルタイトル
    bl_idname = "CHAOSIM_PT_example" # 一意 ID（英数字・アンダースコア）
    bl_space_type = "VIEW_3D"        # 3D ビューポート
    bl_region_type = "UI"            # サイドバー（N キー）
    bl_category = "Chaosim"          # タブ名

    def draw(self, context):
        layout = self.layout
        layout.label(text="Hello from Chaosim")
        layout.operator("chaosim.apply_shorts_setup", icon="RENDER_STILL")
```

`bl_category` がサイドバーのタブ名になります。**LookDev** タブ、`Chaosim` タブなどプロジェクトごとに分けられます。

### よく使う layout パターン

```python
def draw(self, context):
    layout = self.layout
    props = context.scene.chaosim_scene

    # プロパティ（Enum, Float, Pointer 等）
    layout.prop(props, "render_preset")
    layout.prop(props, "duration_sec")

    # ボタン（Operator）
    layout.operator("chaosim.apply_render_preset", icon="RENDER_ANIMATION")

    # 横並び
    row = layout.row(align=True)
    row.operator("chaosim.apply_shorts_setup")
    row.operator("chaosim.reset_frame_range", icon="TIME")

    # グループ枠
    box = layout.box()
    box.label(text="Render Info", icon="INFO")
    box.label(text=f"Frames: {context.scene.frame_start}-{context.scene.frame_end}")
```

### PropertyGroup（パネルとデータをつなぐ）

UI の値は `bpy.types.PropertyGroup` に保持し、`Scene` などに `PointerProperty` でぶら下げます。

```python
from bpy.props import EnumProperty, FloatProperty, PointerProperty
from bpy.types import PropertyGroup

class ChaosimSceneProperties(PropertyGroup):
    render_preset: EnumProperty(
        name="Preset",
        items=[
            ("preview", "Preview", "Fast check"),
            ("medium", "Medium", "Default"),
            ("high", "High", "Production"),
        ],
        default="medium",
    )
    duration_sec: FloatProperty(name="Duration (sec)", default=15.0, min=1.0, max=120.0)

# register() 内
bpy.utils.register_class(ChaosimSceneProperties)
bpy.types.Scene.chaosim_scene = PointerProperty(type=ChaosimSceneProperties)
```

`update=callback` を付けると、スライダー変更時に即座にマテリアル等へ反映できます（`lookdev_material_tool` 参照）。

---

## 3. Operator（実行処理）の書き方

ボタンやメニューから呼ばれる処理は **Operator** です。

```python
from bpy.types import Operator

class CHAOSIM_OT_apply_shorts_setup(Operator):
    bl_idname = "chaosim.apply_shorts_setup"  # layout.operator() で使う ID
    bl_label = "Shorts Setup"                  # ボタン表示名
    bl_description = "1080x1920, Cycles, black background"
    bl_options = {"REGISTER", "UNDO"}          # UNDO で Ctrl+Z 可能に

    def execute(self, context):
        scene = context.scene
        scene.render.resolution_x = 1080
        scene.render.resolution_y = 1920
        scene.render.engine = "CYCLES"
        self.report({"INFO"}, "Shorts setup applied")
        return {"FINISHED"}   # 成功
        # return {"CANCELLED"}  # 失敗時
```

### bl_idname の命名規則

`{prefix}.{action}` 形式が一般的です。

- `chaosim.apply_render_preset`
- `lookdev.setup_materials`

**プロジェクト内で一意** にしてください。他アドオンと衝突すると予期しない動作になります。

### コンテキスト（context）の注意

Operator は **現在のモード・選択・エリア** に依存します。

- メッシュ編集系: `context.mode == "EDIT_MESH"` を確認
- `bpy.ops` は副作用で選択が変わることがある → 対象オブジェクトは変数に保持
- バックグラウンド CLI では UI Operator は使えない（`bpy` データ API を直接使う）

---

## 4. ファイルの置き場所

### 推奨ディレクトリ構成

```
simulators/blender/
├── runner.py              # バッチエントリポイント
├── utils.py               # シーン脚本用ユーティリティ
├── scenes/                # パイプライン用（UI なし）
│   └── double_pendulum.py
└── addons/                # インタラクティブツール（Git 管理）
    ├── chaosim_scene_tools/
    │   ├── __init__.py    # bl_info, register/unregister
    │   ├── properties.py
    │   ├── operators.py
    │   └── panels.py
    └── lookdev_material_tool/
        └── __init__.py
```

### bl_info（アドオンのメタデータ）

各アドオンの `__init__.py` 先頭に必須です。

```python
bl_info = {
    "name": "Chaosim Scene Tools",
    "author": "Chaosim",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Chaosim",
    "description": "Apply render presets and Shorts setup",
    "category": "Render",
}
```

### register / unregister

Blender は有効化時に `register()`、無効化時に `unregister()` を呼びます。

```python
classes = (ChaosimSceneProperties, CHAOSIM_OT_apply_shorts_setup, CHAOSIM_PT_panel)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.chaosim_scene = PointerProperty(type=ChaosimSceneProperties)

def unregister():
    del bpy.types.Scene.chaosim_scene
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
```

**登録順**: PropertyGroup → Operator → Panel  
**解除順**: その逆（`reversed(classes)`）

---

## 5. プロジェクトごとの共有方法

### 方針: Git でソース管理 + シンボリックリンクでインストール

アドオン本体は **リポジトリ内** `simulators/blender/addons/` に置き、Blender の addons フォルダへ **symlink** します。

メリット:

- コード変更が即 Blender に反映（再インストール不要）
- プロジェクトごとに異なるツールセットを Git で管理できる
- チーム全員が同じパス構成になる

```
chaosim/simulators/blender/addons/chaosim_scene_tools/
        ↓ symlink
~/Library/Application Support/Blender/4.2/scripts/addons/chaosim_scene_tools/
```

### インストールスクリプト

```bash
python scripts/install_blender_addons.py
# または Blender パス指定
BLENDER_PATH=/Applications/Blender.app/Contents/MacOS/Blender python scripts/install_blender_addons.py
```

全アドオンを一括リンクします。`--remove` でリンク削除。

### プロジェクトルートの解決

アドオンから `config/render_presets.yaml` 等を読む場合、AddonPreferences でプロジェクトルートを設定できます。未設定時はアドオンファイル位置から自動推定します。

```
addons/chaosim_scene_tools/__init__.py
  → 親を 3 段上がる → chaosim/（リポジトリルート）
```

### .blend ファイルへの埋め込み（非推奨を基本）

スクリプトを `.blend` に embed することもできますが、**バージョン管理・共有が難しい** ため Chaosim では使いません。アドオン + Git が標準です。

### 複数プロジェクトを使う場合

| 方法 | 説明 |
|------|------|
| **symlink 差し替え** | プロジェクト切替時に `install_blender_addons.py` を再実行 |
| **Preferences パス** | 各アドオンの Preferences で project_root をプロジェクトごとに設定 |
| **名前空間** | `bl_idname` を `chaosim.*` / `lookdev.*` のように prefix で分離 |

---

## 6. インストールと有効化

### 手順

1. **Bootstrap**（初回のみ）: PyYAML を Blender Python に入れる

   ```bash
   python scripts/blender_bootstrap.py
   ```

2. **アドオンリンク**

   ```bash
   python scripts/install_blender_addons.py
   ```

3. **Blender で有効化**

   Edit → Preferences → Add-ons → 検索（"Chaosim" / "LookDev"）→ チェック ON

4. **UI の場所**

   - 3D Viewport → サイドバー（`N` キー）→ **Chaosim** / **LookDev** タブ

### 開発中のリロード

コードを編集したあと:

1. Preferences → Add-ons → 該当アドオンを一度 OFF → ON  
   または
2. Blender 再起動

（F3 → "Reload Scripts" も使えますが、完全な register/unregister には OFF/ON が確実です。）

---

## 7. 開発サイクル

```
┌─────────────────┐
│  addons/ に実装  │
└────────┬────────┘
         ▼
┌─────────────────┐
│ install script   │  symlink
└────────┬────────┘
         ▼
┌─────────────────┐
│ Blender GUI      │  OFF→ON でリロード
│ パネルで動作確認  │
└────────┬────────┘
         ▼
┌─────────────────┐
│ git commit       │  チーム共有
└─────────────────┘
```

### バックグラウンドでのテスト

アドオン全体ではなく **ロジック単体** を CLI で試す場合:

```bash
blender --background --python-expr "
import bpy
# データ API のみテスト
bpy.context.scene.render.resolution_x = 1080
print('OK')
"
```

UI 付き Operator は GUI セッションで確認してください。

---

## 8. Chaosim 内のサンプルアドオン

### chaosim_scene_tools（入門〜実務向け）

**場所**: `simulators/blender/addons/chaosim_scene_tools/`

| 機能 | Operator | 説明 |
|------|----------|------|
| レンダープリセット適用 | `chaosim.apply_render_preset` | `config/render_presets.yaml` を読み込み Cycles 設定 |
| Shorts セットアップ | `chaosim.apply_shorts_setup` | 1080×1920・黒背景・60fps ベース |
| フレームレンジ更新 | `chaosim.set_frame_range` | duration_sec から frame_end を計算 |

モジュール分割例（小さくてもこの形を推奨）:

- `properties.py` — PropertyGroup
- `operators.py` — 実行処理
- `panels.py` — UI
- `__init__.py` — bl_info, register

### lookdev_material_tool（応用例）

**場所**: `simulators/blender/addons/lookdev_material_tool/`

- マテリアルプリセット 5 種（Principled / Toon / Glass / Clay / Emission）
- パラメータ UI とシェーダーノードの双方向 sync
- `update` コールバックでリアルタイム反映

LookDev 作業で「1 パネルから見た目を試す」用途向けです。

---

## クイックリファレンス

| やりたいこと | 使うもの |
|-------------|----------|
| サイドバーにパネル | `bpy.types.Panel` |
| ボタン処理 | `bpy.types.Operator` + `execute()` |
| スライダー・ドロップダウン | `PropertyGroup` + `layout.prop()` |
| 設定を Blender に保存 | `AddonPreferences` |
| パイプライン自動実行 | `scenes/*.py` + `runner.py` |
| チーム共有 | Git + `install_blender_addons.py` |

## 参考リンク

- [Blender Python API — Addon Tutorial](https://docs.blender.org/api/current/info/getting_started.html)
- [bpy.types.Operator](https://docs.blender.org/api/current/bpy.types.Operator.html)
- [bpy.types.Panel](https://docs.blender.org/api/current/bpy.types.Panel.html)
