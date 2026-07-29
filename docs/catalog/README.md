# 企画カタログ / 健康診断

`concepts/**/*.yaml` と `simulators/blender/scenes/*.py` を突き合わせた自動生成ビュー。
**このファイルは編集しない** — `python scripts/chaosim.py catalog` で再生成される。
（生成日時はあえて埋めていない。毎回の実行で中身の変わらない差分が出るため。
更新時刻は git のコミット履歴で追う）

| | |
|---|---|
| 企画数 | 14 |
| error | 0 |
| warning | 10 |
| params 到達率 | **78 / 104 (75%)** |
| params 検証不能 | 18（scene_script が無い企画のぶん。上の母数には入れていない） |

> **26 個の params が YAML に書かれているだけでコードに届いていない。**
> `runner.py` は `run_simulation()` に params を渡さないため、`setup_scene()` の外で
> 物理値を使っているシーンでは YAML をいくら調整しても絵が変わらない。
> 該当する企画は下の「指摘の詳細」で `dead-params` が付いているもの。

## 企画一覧

error / warning の多い順。

| 企画 | scene_script | 尺 | preset | params | 状態 |
|---|---|---:|---|---:|---|
| [`glass_fracture_wall`](#glass_fracture_wall) | `glass_fracture_wall` | 10s | preview | 0/9 | ⚠️ warn 2 |
| [`soft_body_torus_compare`](#soft_body_torus_compare) | `soft_body_torus_compare` | 15s | preview | 0/9 | ⚠️ warn 2 |
| [`magnetic_pendulum_ufo`](#magnetic_pendulum_ufo) 📄 | `magnetic_pendulum` | 15s | preview | 2/8 | ⚠️ warn 1 |
| [`paper_to_cloth`](#paper_to_cloth) 📄 | `paper_to_cloth` ⧉ | 24s | preview | 6/10 | ⚠️ warn 1 |
| [`sample_001_double_pendulum`](#sample_001_double_pendulum) | `double_pendulum` | 30s | high | 0/7 | ⚠️ warn 1 |
| [`sample_002_fluid_ink`](#sample_002_fluid_ink) | `fluid_ink` | 20s | high | 4/5 | ⚠️ warn 1 |
| [`sample_003_sand_collapse`](#sample_003_sand_collapse) | `sand_collapse` | 25s | high | 5/6 | ⚠️ warn 1 |
| [`sample_004_lorenz_attractor`](#sample_004_lorenz_attractor) | `lorenz_attractor` | 30s | high | 0/7 | ⚠️ warn 1 |
| [`cloth_by_faces`](#cloth_by_faces) 📄 | `cloth_drop_faces` ⧉ | 20s | high | 29/29 | ✅ |
| [`local_colorful_domino`](#local_colorful_domino) | `domino_chain` | 6s | preview | 6/6 | ✅ |
| [`local_local_domino`](#local_local_domino) | `domino_chain` | 6s | preview | 6/6 | ✅ |
| [`quick_domino_chain`](#quick_domino_chain) | `domino_chain` | 6s | preview | 6/6 | ✅ |
| [`ring_escape_5rings`](#ring_escape_5rings) 📄 | `ring_escape` | 12s | preview | 8/8 | ✅ |
| [`sample_005_domino_chain`](#sample_005_domino_chain) | `domino_chain` | 20s | high | 6/6 | ✅ |

<sub>📄 = `docs/gate1/` にコンタクトシートあり ／ ⧉ = 段階シーン（`render_staged`）</sub>

## 指摘の詳細

### glass_fracture_wall

Glass Wall Shatter — Sphere Impact
`concepts/generated/glass_fracture_wall.yaml`
> Sphere makes contact with the glass at frame ~15 — instant fracture cascade

- ⚠️ warn `missing-scene` — scene_script `glass_fracture_wall.py` が存在しない（status: blocked のため警告どまり）
- ⚠️ warn `blocked` — status: blocked — レンダー対象外

### soft_body_torus_compare

0% vs 100% Soft Body — Torus Edition
`concepts/generated/soft_body_torus_compare.yaml`
> 0% version: hard clack. 100% version: it swallows the object like jelly

- ⚠️ warn `missing-scene` — scene_script `soft_body_torus_compare.py` が存在しない（status: blocked のため警告どまり）
- ⚠️ warn `blocked` — status: blocked — レンダー対象外

### magnetic_pendulum_ufo

Magnetic Chaos Pendulum — UFO Type
`concepts/generated/magnetic_pendulum_ufo.yaml`
> Bob released from a random spot — the glowing trail immediately starts wandering unpredictably between the three magnets

- ⚠️ warn `dead-params` — 6/8 の params がコードに届いていない: `bob_height`, `bob_start_x`, `bob_start_y`, `damping`, `magnet_strength`, `spring`

Phase 1 コンタクトシート: [`docs/gate1/magnetic_pendulum_ufo_contact.png`](../gate1/magnetic_pendulum_ufo_contact.png)

### paper_to_cloth

紙が布になるまで — 面数デモ
`concepts/generated/paper_to_cloth.yaml`
> 面数が増えるたびにシートの動きが布っぽくなる

- ⚠️ warn `dead-params` — 4/10 の params がコードに届いていない: `camera_distance`, `camera_height`, `camera_lens`, `camera_pitch_deg`

Phase 1 コンタクトシート: [`docs/gate1/paper_to_cloth_contact.png`](../gate1/paper_to_cloth_contact.png)

### sample_001_double_pendulum

10 Pendulums — Chaos Begins
`concepts/sample_001_double_pendulum.yaml`
> All 10 pendulums move together... then chaos erupts at 3 seconds

- ⚠️ warn `dead-params` — 7/7 の params がコードに届いていない: `arm1_length`, `arm2_length`, `initial_angle1_deg`, `initial_angle2_deg`, `mass1`, `mass2`, `pendulum_count`

### sample_002_fluid_ink

Ink Chaos — 3 Colors, One Tank
`concepts/sample_002_fluid_ink.yaml`
> Three drops hit the water simultaneously at frame 1

- ⚠️ warn `dead-params` — 1/5 の params がコードに届いていない: `viscosity`

### sample_003_sand_collapse

10,000 Sand Grains — Wall Collapse
`concepts/sample_003_sand_collapse.yaml`
> Wall disappears at frame 1 — instant avalanche

- ⚠️ warn `dead-params` — 1/6 の params がコードに届いていない: `color_gradient`

### sample_004_lorenz_attractor

The Butterfly That Broke Physics
`concepts/sample_004_lorenz_attractor.yaml`
> Five glowing trails begin the same path, then split apart at 2 seconds

- ⚠️ warn `dead-params` — 7/7 の params がコードに届いていない: `beta`, `dt`, `n_trajectories`, `rho`, `scale`, `sigma`, `trail_width`

### cloth_by_faces

面数で変わる布 — Cloth by Faces
`concepts/cloth_by_faces.yaml`
> 面数16のカクカクした金属シートが、面数を上げるほど布のように垂れ込む

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/cloth_by_faces_contact.png`](../gate1/cloth_by_faces_contact.png)

### local_colorful_domino

colorful_domino — ドミノ連鎖
`concepts/generated/local_colorful_domino.yaml`
> 最初のドミノが倒れた瞬間から連鎖が始まる

指摘なし。

### local_local_domino

カラフルドミノ — ドミノ連鎖
`concepts/generated/local_local_domino.yaml`
> 最初のドミノが倒れた瞬間から連鎖が始まる

指摘なし。

### quick_domino_chain

カラフルドミノ連鎖
`concepts/generated/quick_domino_chain.yaml`
> 最初のドミノが倒れた瞬間から連鎖が始まる

指摘なし。

### ring_escape_5rings

Can the Ball Escape? — 5 Spinning Rings
`concepts/generated/ring_escape_5rings.yaml`
> Ball drops onto the top ring immediately — will the gap be there?

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/ring_escape_5rings_contact.png`](../gate1/ring_escape_5rings_contact.png)

### sample_005_domino_chain

50 Dominos — Spiral Chain Reaction
`concepts/sample_005_domino_chain.yaml`
> First domino tips at frame 5 — chain begins immediately

指摘なし。

## シーン契約マトリクス

`runner.py` は `hasattr()` でこれらを feature-detect する。
`render_staged` があれば `setup_scene` / `run_simulation` は呼ばれない。
`collect_impact_events` が無いシーンは `events.json` が空になり、SFX の当て先が無い。

| scene_script | setup_scene | run_simulation | render_staged | collect_impact_events | params | 使っている企画 |
|---|:-:|:-:|:-:|:-:|---:|---|
| `cloth_drop_faces` | ✅ | ✅ | ✅ | ✅ | 40 | `cloth_by_faces` |
| `domino_chain` | ✅ | ✅ | — | ✅ | 6 | `local_colorful_domino`, `local_local_domino`, `quick_domino_chain`, `sample_005_domino_chain` |
| `double_pendulum` | ✅ | ✅ | — | — | 0 | `sample_001_double_pendulum` |
| `fluid_ink` | ✅ | ✅ | — | — | 4 | `sample_002_fluid_ink` |
| `lorenz_attractor` | ✅ | ✅ | — | — | 0 | `sample_004_lorenz_attractor` |
| `magnetic_pendulum` | ✅ | ✅ | — | — | 2 | `magnetic_pendulum_ufo` |
| `paper_to_cloth` | ✅ | ✅ | ✅ | — | 6 | `paper_to_cloth` |
| `ring_escape` | ✅ | ✅ | — | — | 9 | `ring_escape_5rings` |
| `sand_collapse` | ✅ | ✅ | — | — | 5 | `sample_003_sand_collapse` |

`runner.py` が直接読む params: `face_counts`, `stage_duration_sec`（段階シーンはこれで尺が決まるので、YAML に書いても死に設定にはならない）

## 判定の仕方

- **error** — レンダーが失敗するか、成果物が想定と変わる。直してから回す。
- **warn** — 回るが企画の意図どおりにならない可能性がある。とくに `dead-params` は
  「YAML に書いた値が効いていない」ので、パラメータ調整で直そうとしても徒労になる。

`python scripts/chaosim.py catalog --check` は error が1件でもあれば exit 1 する。