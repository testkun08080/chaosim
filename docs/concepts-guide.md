# サンプル企画 5 選

AI 生成の企画テンプレート兼、そのまま実行できるサンプル。

---

## 001 — ダブルペンデュラム「10本の振り子、カオスへ」

**ファイル:** `concepts/sample_001_double_pendulum.yaml`

ほぼ同じ初期角度から始めた 10 本の二重振り子が、数秒後に完全に異なる軌跡を描く。  
カオス理論の「初期値鋭敏性」をそのまま視覚化した古典的な題材。

- **フック:** 最初の 3 秒は全員同じ動き → 突然バラバラに
- **バズ要因:** カオス理論の教科書的ビジュアル。理系 SNS で定番の拡散ネタ
- **前例:** YouTube に数十万再生の類似動画多数。見せ方（グローライン、背景黒）で差別化

```yaml
params:
  pendulum_count: 10
  initial_angle1_deg: 120   # ここを変えるだけで別の絵になる
```

---

## 002 — 流体インク「3色、1つのタンク」

**ファイル:** `concepts/sample_002_fluid_ink.yaml`

赤・青・緑のインクを静止した水に同時に落とす。Blender の FLIP Fluid ソルバーで本物の流体拡散をシミュレート。

- **フック:** 3 滴が水面に着弾する瞬間
- **バズ要因:** 流体シミュレーションは Shorts / TikTok で最も視聴完了率が高いジャンルの 1 つ。ASMR 的な静かな満足感
- **前例:** ink in water 系は再生数億超えのバイラル動画が複数存在

```yaml
params:
  ink_drops: 3
  viscosity: 0.001   # 下げると水っぽく、上げると粘性流体になる
  ink_colors:
    - [0.0, 0.0, 1.0]  # 青
    - [1.0, 0.0, 0.0]  # 赤
    - [0.0, 1.0, 0.0]  # 緑
```

---

## 003 — 砂崩壊「壁が消えた瞬間」

**ファイル:** `concepts/sample_003_sand_collapse.yaml`

壁で押さえていた 2000 個の砂粒子。壁が消えた瞬間、雪崩のように崩れ落ちる。高さ方向に色グラデーションをかけることで、崩落の動きが視覚的に際立つ。

- **フック:** 壁消滅 → 即座に崩落開始（フレーム 1）
- **バズ要因:** 「崩壊 ASMR」系。スロー演出との相性が良い
- **前例:** sand pile collapse 系の動画は TikTok で安定してバズる

```yaml
params:
  particle_count: 2000   # 増やすほどリッチだが重くなる
  stack_height: 4.0
  restitution: 0.1       # 弾み係数。上げると粒子が飛び跳ねる
```

---

## 004 — ローレンツアトラクター「蝶の方程式」

**ファイル:** `concepts/sample_004_lorenz_attractor.yaml`

ローレンツ方程式で定義される「ストレンジアトラクター」。5 本のグローする軌跡が宇宙の星雲のような蝶形を描く。カメラがゆっくり周回することで立体感を強調。

- **フック:** 5 本の軌跡が同じところから始まり、2 秒後に分岐
- **バズ要因:** バタフライ効果の由来図形として知名度が高い。数学・科学クラスタへのリーチ大
- **前例:** 3Blue1Brown、Veritasium 系の教育コンテンツで何度も登場

```yaml
params:
  sigma: 10.0
  rho: 28.0     # この値が 28 のとき混沌が最大
  beta: 2.667
  n_trajectories: 5
```

---

## 005 — ドミノ連鎖「50 個のレインボースパイラル」

**ファイル:** `concepts/sample_005_domino_chain.yaml`

虹色に塗られた 50 個のドミノをスパイラル状に配置。一押しで始まる連鎖反応をカメラがゆっくりと引きながら追う。

- **フック:** 最初の一押し（フレーム 5）から即座に連鎖開始
- **バズ要因:** ドミノ倒しは永遠に視聴される「満足感コンテンツ」の筆頭。レインボーカラーが映える
- **前例:** ドミノ動画は YouTube で数億再生クラスが定期的に出る

```yaml
params:
  domino_count: 50
  curve_radius: 3.0   # 0 = 直線、3.0 = 円弧スパイラル
  spacing: 0.35
```

---

## 企画 YAML のフィールド一覧

| フィールド | 型 | 説明 |
|---|---|---|
| `title` | string | 動画タイトル（内部管理用） |
| `slug` | string | ファイル名に使うスネークケース識別子 |
| `simulator` | string | `blender` / `houdini` / `unreal` |
| `scene_script` | string | `simulators/blender/scenes/` 内のファイル名（拡張子なし） |
| `duration_sec` | int | 動画の長さ（秒）。59 以下推奨 |
| `hook` | string | 最初の 3 秒で起きること |
| `viral_angle` | string | バズる理由の仮説 |
| `params` | dict | シーンスクリプトに渡すパラメーター |
| `render_preset` | string | `preview` / `medium` / `high` / `ultra` |
| `music_mood` | string | BGM の雰囲気メモ（手動で楽曲選定する際の参考） |
| `caption` | string | YouTube タイトル（100 文字以内） |
| `hashtags` | list | YouTube / TikTok 用ハッシュタグ |
