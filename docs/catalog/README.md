# 企画カタログ / 健康診断

`concepts/**/*.yaml` を、それが名指しするコード（`simulators/blender/scenes/*.py` と
`simulators/comfyui/recipes/*.py`）と突き合わせた自動生成ビュー。
**このファイルは編集しない** — `python scripts/chaosim.py catalog` で再生成される。
（生成日時はあえて埋めていない。毎回の実行で中身の変わらない差分が出るため。
更新時刻は git のコミット履歴で追う）

| | |
|---|---|
| 企画数 | 30 |
| source 内訳 | blender 24 / comfyui 4 / hybrid 2 |
| error | 0 |
| warning | 2 |
| params 到達率 | **297 / 299 (99%)** |

> **2 個の params が YAML に書かれているだけでコードに届いていない。**
> `runner.py` は `run_simulation()` に params を渡さないため、`setup_scene()` の外で
> 物理値を使っているシーンでは YAML をいくら調整しても絵が変わらない。
> 該当する企画は下の「指摘の詳細」で `dead-params` が付いているもの。

## 企画一覧

error / warning の多い順。

| 企画 | source | 駆動するコード | 尺 | preset | params / cue | 状態 |
|---|---|---|---:|---|---:|---|
| [`sample_002_fluid_ink`](#sample_002_fluid_ink) | blender | `fluid_ink` | 20s | high | 4/5 | ⚠️ warn 1 |
| [`sample_003_sand_collapse`](#sample_003_sand_collapse) | blender | `sand_collapse` | 25s | high | 5/6 | ⚠️ warn 1 |
| [`branding_channel`](#branding_channel) | blender | `branding_assets` | 1s | medium | 13/13 | ✅ |
| [`branding_character`](#branding_character) | blender | `branding_assets` | 1s | medium | 9/9 | ✅ |
| [`cloth_by_faces`](#cloth_by_faces) 📄 | blender | `cloth_drop_faces` ⧉ | 20s | high | 29/29 | ✅ |
| [`cloth_by_faces_hybrid`](#cloth_by_faces_hybrid) | hybrid | `cloth_drop_faces` ⧉ + `look_assets` 🎞 | 20s | preview | 29/29 | ✅ |
| [`double_spiral_domino`](#double_spiral_domino) 📄 | blender | `domino_chain` | 18s | preview | 6/6 | ✅ |
| [`funnel_vortex_marbles`](#funnel_vortex_marbles) 📄 | blender | `funnel_vortex` | 18s | preview | 14/14 | ✅ |
| [`glass_fracture_wall`](#glass_fracture_wall) 📄 | blender | `glass_fracture_wall` | 10s | preview | 14/14 | ✅ |
| [`glass_fracture_wall_comfy`](#glass_fracture_wall_comfy) | comfyui | `generative_shots` 🎞 | 15s | preview | 3カット/9cue | ✅ |
| [`growing_ball_bounce`](#growing_ball_bounce) 📄 | blender | `growing_ball` | 20s | preview | 14/14 | ✅ |
| [`growing_ball_bounce_hybrid`](#growing_ball_bounce_hybrid) | hybrid | `growing_ball` + `look_assets` 🎞 | 20s | preview | 19/19 | ✅ |
| [`local_colorful_domino`](#local_colorful_domino) | blender | `domino_chain` | 6s | preview | 6/6 | ✅ |
| [`local_local_domino`](#local_local_domino) | blender | `domino_chain` | 6s | preview | 6/6 | ✅ |
| [`magnetic_pendulum_ufo`](#magnetic_pendulum_ufo) 📄 | blender | `magnetic_pendulum` | 15s | preview | 8/8 | ✅ |
| [`marble_elimination_race`](#marble_elimination_race) 📄 | blender | `marble_race` | 18s | preview | 14/14 | ✅ |
| [`paper_to_cloth`](#paper_to_cloth) 📄 | blender | `paper_to_cloth` ⧉ | 24s | preview | 10/10 | ✅ |
| [`planet_crush_asmr_comfy`](#planet_crush_asmr_comfy) | comfyui | `generative_shots` 🎞 | 15s | preview | 3カット/9cue | ✅ |
| [`press_crush_showdown`](#press_crush_showdown) 📄 | blender | `press_crush` | 15s | preview | 13/13 | ✅ |
| [`press_crush_showdown_comfy`](#press_crush_showdown_comfy) | comfyui | `generative_shots` 🎞 | 15s | preview | 3カット/8cue | ✅ |
| [`pyramid_collapse_100`](#pyramid_collapse_100) 📄 | blender | `pyramid_collapse` | 15s | preview | 14/14 | ✅ |
| [`quick_domino_chain`](#quick_domino_chain) | blender | `domino_chain` | 6s | preview | 6/6 | ✅ |
| [`ring_escape_5rings`](#ring_escape_5rings) 📄 | blender | `ring_escape` | 12s | preview | 8/8 | ✅ |
| [`ring_escape_tall`](#ring_escape_tall) 📄 | blender | `ring_escape` | 14s | preview | 13/13 | ✅ |
| [`sample_001_double_pendulum`](#sample_001_double_pendulum) | blender | `double_pendulum` | 30s | high | 7/7 | ✅ |
| [`sample_004_lorenz_attractor`](#sample_004_lorenz_attractor) | blender | `lorenz_attractor` | 30s | high | 7/7 | ✅ |
| [`sample_005_domino_chain`](#sample_005_domino_chain) | blender | `domino_chain` | 20s | high | 6/6 | ✅ |
| [`sand_avalanche_asmr`](#sand_avalanche_asmr) 📄 | blender | `sand_collapse` | 15s | preview | 5/5 | ✅ |
| [`sand_avalanche_asmr_comfy`](#sand_avalanche_asmr_comfy) | comfyui | `generative_shots` 🎞 | 15s | preview | 3カット/7cue | ✅ |
| [`soft_body_torus_compare`](#soft_body_torus_compare) 📄 | blender | `soft_body_torus_compare` | 12s | preview | 18/18 | ✅ |

<sub>📄 = `docs/gate1/` にコンタクトシートあり ／ ⧉ = 段階シーン（`render_staged`）／ 🎞 = ComfyUI レシピ</sub>

## 指摘の詳細

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

### branding_channel

Chaos Sim — Channel Art
`concepts/branding_channel.yaml`
> Simple shapes, clear channel identity

指摘なし。

### branding_character

Chaos Sim — Character Thumbnail
`concepts/branding_character.yaml`
> Round mascot thumb

指摘なし。

### cloth_by_faces

面数で変わる布 — Cloth by Faces
`concepts/cloth_by_faces.yaml`
> 面数16のカクカクした金属シートが、面数を上げるほど布のように垂れ込む

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/cloth_by_faces_contact.png`](../gate1/cloth_by_faces_contact.png)

### cloth_by_faces_hybrid

面数で変わる布 — Hybrid
`concepts/comfyui/cloth_by_faces_hybrid.yaml`
> 面数16のカクカクした金属シートが、面数を上げるほど布のように垂れ込む

指摘なし。

### double_spiral_domino

120 Dominoes, One Tight Spiral
`concepts/generated/double_spiral_domino.yaml`
> フレーム5で最初の1枚が倒れ、そこから連鎖が途切れずに巻き込んでいく

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/double_spiral_domino_contact.png`](../gate1/double_spiral_domino_contact.png)

### funnel_vortex_marbles

160 Marbles Down the Vortex
`concepts/generated/funnel_vortex_marbles.yaml`
> フレーム1から玉が落ち始め、最初の1周が0.5秒以内に見える

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/funnel_vortex_marbles_contact.png`](../gate1/funnel_vortex_marbles_contact.png)

### glass_fracture_wall

Glass Wall Shatter — Sphere Impact
`concepts/generated/glass_fracture_wall.yaml`
> 衝突はフレーム10。そこから亀裂が外へ走り出すまでが最初の0.5秒

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/glass_fracture_wall_contact.png`](../gate1/glass_fracture_wall_contact.png)

### glass_fracture_wall_comfy

Glass Wall Shatter — ComfyUI
`concepts/comfyui/glass_fracture_wall_comfy.yaml`
> 1カット目の1秒手前、まだ無傷のガラスに球が入ってくる

指摘なし。

### growing_ball_bounce

The Ball Grows Every Bounce
`concepts/generated/growing_ball_bounce.yaml`
> フレーム1から跳ね始める。2バウンド目には既に目に見えて大きくなっている

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/growing_ball_bounce_contact.png`](../gate1/growing_ball_bounce_contact.png)

### growing_ball_bounce_hybrid

The Ball Grows Every Bounce — Hybrid
`concepts/comfyui/growing_ball_bounce_hybrid.yaml`
> フレーム1から跳ね始める。2バウンド目には既に目に見えて大きくなっている

指摘なし。

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

### magnetic_pendulum_ufo

Magnetic Chaos Pendulum — UFO Type
`concepts/generated/magnetic_pendulum_ufo.yaml`
> Bob released from a random spot — the glowing trail immediately starts wandering unpredictably between the three magnets

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/magnetic_pendulum_ufo_contact.png`](../gate1/magnetic_pendulum_ufo_contact.png)

### marble_elimination_race

24 Marbles, 6 Ramps — Who Reaches the Bottom First?
`concepts/generated/marble_elimination_race.yaml`
> フレーム1で全マーブルが落下開始。最初のコーナーの詰まりが0.5秒以内に来る

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/marble_elimination_race_contact.png`](../gate1/marble_elimination_race_contact.png)

### paper_to_cloth

紙が布になるまで — 面数デモ
`concepts/generated/paper_to_cloth.yaml`
> 面数が増えるたびにシートの動きが布っぽくなる

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/paper_to_cloth_contact.png`](../gate1/paper_to_cloth_contact.png)

### planet_crush_asmr_comfy

Crushing a Tiny Planet — ComfyUI
`concepts/comfyui/planet_crush_asmr_comfy.yaml`
> 1カット目、手のひらサイズの惑星の真上からプレス面が入ってくる

指摘なし。

### press_crush_showdown

Hydraulic Press vs 48 Blocks
`concepts/generated/press_crush_showdown.yaml`
> フレーム12でプレスが降り始める。最初のブロックが横に飛ぶまで1秒かからない

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/press_crush_showdown_contact.png`](../gate1/press_crush_showdown_contact.png)

### press_crush_showdown_comfy

Hydraulic Press vs Blocks — ComfyUI
`concepts/comfyui/press_crush_showdown_comfy.yaml`
> 1カット目、ブロックの山の真上からプレス面が入ってくる

指摘なし。

### pyramid_collapse_100

285-Block Pyramid vs One Wrecking Ball
`concepts/generated/pyramid_collapse_100.yaml`
> フレーム14で鉄球が最下層に到達。そこから全体が自重で落ちる

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/pyramid_collapse_100_contact.png`](../gate1/pyramid_collapse_100_contact.png)

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

### ring_escape_tall

Can the Ball Escape All 7 Rings?
`concepts/generated/ring_escape_tall.yaml`
> フレーム1でボールが最上段に落ちる。1枚目を抜けられるかが即座に分かる

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/ring_escape_tall_contact.png`](../gate1/ring_escape_tall_contact.png)

### sample_001_double_pendulum

10 Pendulums — Chaos Begins
`concepts/sample_001_double_pendulum.yaml`
> All 10 pendulums move together... then chaos erupts at 3 seconds

指摘なし。

### sample_004_lorenz_attractor

The Butterfly That Broke Physics
`concepts/sample_004_lorenz_attractor.yaml`
> Five glowing trails begin the same path, then split apart at 2 seconds

指摘なし。

### sample_005_domino_chain

50 Dominos — Spiral Chain Reaction
`concepts/sample_005_domino_chain.yaml`
> First domino tips at frame 5 — chain begins immediately

指摘なし。

### sand_avalanche_asmr

Sand Wall Collapse — 3000 Grains
`concepts/generated/sand_avalanche_asmr.yaml`
> フレーム30で壁が消え、崩落が始まるまで一瞬の静止がある

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/sand_avalanche_asmr_contact.png`](../gate1/sand_avalanche_asmr_contact.png)

### sand_avalanche_asmr_comfy

Sand Wall Collapse — ComfyUI
`concepts/comfyui/sand_avalanche_asmr_comfy.yaml`
> 1カット目、静止した砂の壁が1秒で崩れ始める

指摘なし。

### soft_body_torus_compare

0% vs 100% Soft Body — Torus Edition
`concepts/generated/soft_body_torus_compare.yaml`
> 落下は1フレーム目から。着地の瞬間に左右で結果が割れる

指摘なし。

Phase 1 コンタクトシート: [`docs/gate1/soft_body_torus_compare_contact.png`](../gate1/soft_body_torus_compare_contact.png)

## シーン契約マトリクス

`runner.py` は `hasattr()` でこれらを feature-detect する。
`render_staged` があれば `setup_scene` / `run_simulation` は呼ばれない。
`collect_impact_events` が無いシーンは `events.json` が空になり、SFX の当て先が無い。

| scene_script | setup_scene | run_simulation | render_staged | collect_impact_events | params | 使っている企画 |
|---|:-:|:-:|:-:|:-:|---:|---|
| `branding_assets` | ✅ | ✅ | — | — | 12 | `branding_channel`, `branding_character` |
| `cloth_drop_faces` | ✅ | ✅ | ✅ | ✅ | 40 | `cloth_by_faces`, `cloth_by_faces_hybrid` |
| `domino_chain` | ✅ | ✅ | — | ✅ | 6 | `double_spiral_domino`, `local_colorful_domino`, `local_local_domino`, `quick_domino_chain`, `sample_005_domino_chain` |
| `double_pendulum` | ✅ | ✅ | — | — | 7 | `sample_001_double_pendulum` |
| `fluid_ink` | ✅ | ✅ | — | — | 4 | `sample_002_fluid_ink` |
| `funnel_vortex` | ✅ | ✅ | — | — | 14 | `funnel_vortex_marbles` |
| `glass_fracture_wall` | ✅ | ✅ | — | ✅ | 14 | `glass_fracture_wall` |
| `growing_ball` | ✅ | ✅ | — | ✅ | 22 | `growing_ball_bounce`, `growing_ball_bounce_hybrid` |
| `lorenz_attractor` | ✅ | ✅ | — | — | 7 | `sample_004_lorenz_attractor` |
| `magnetic_pendulum` | ✅ | ✅ | — | — | 8 | `magnetic_pendulum_ufo` |
| `marble_race` | ✅ | ✅ | — | ✅ | 14 | `marble_elimination_race` |
| `paper_to_cloth` | ✅ | ✅ | ✅ | — | 10 | `paper_to_cloth` |
| `press_crush` | ✅ | ✅ | — | ✅ | 13 | `press_crush_showdown` |
| `pyramid_collapse` | ✅ | ✅ | — | ✅ | 14 | `pyramid_collapse_100` |
| `ring_escape` | ✅ | ✅ | — | ✅ | 14 | `ring_escape_5rings`, `ring_escape_tall` |
| `sand_collapse` | ✅ | ✅ | — | — | 5 | `sample_003_sand_collapse`, `sand_avalanche_asmr` |
| `soft_body_torus_compare` | ✅ | ✅ | — | ✅ | 18 | `soft_body_torus_compare` |

`runner.py` が直接読む params: `face_counts`, `resolution`, `stage_duration_sec`, `still`（段階シーンはこれで尺が決まるので、YAML に書いても死に設定にはならない）

## ComfyUI レシピ契約マトリクス

`pipeline/comfyui_render.py` が呼ぶ契約。`build_jobs` が仕事の一覧を、
`apply_assets` が「作った素材をどの params に差し込むか」を決める。
`apply_assets` を持つレシピだけが `source: hybrid` の裏に立てる。

| recipe | build_jobs | apply_assets | 読む項目 | 使っている企画 |
|---|:-:|:-:|---:|---|
| `generative_shots` | ✅ | — | 15 | `glass_fracture_wall_comfy`, `planet_crush_asmr_comfy`, `press_crush_showdown_comfy`, `sand_avalanche_asmr_comfy` |
| `look_assets` | ✅ | ✅ | 10 | `cloth_by_faces_hybrid`, `growing_ball_bounce_hybrid` |

## 判定の仕方

- **error** — レンダーが失敗するか、成果物が想定と変わる。直してから回す。
- **warn** — 回るが企画の意図どおりにならない可能性がある。とくに `dead-params` /
  `dead-comfyui-keys` は「YAML に書いた値が効いていない」ので、
  パラメータ調整で直そうとしても徒労になる。
- `no-cues` は `source: comfyui` 固有。生成映像にはベイクが無く、cue が唯一の
  タイミング情報なので、これが無いと絵は出ても音が一切鳴らない。

`python scripts/chaosim.py catalog --check` は error が1件でもあれば exit 1 する。