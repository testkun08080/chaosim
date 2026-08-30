# 効果音レポート — 音は絵に合っているか

`python scripts/chaosim.py sfx-report` が生成する。**このファイルは編集しない。**
判定の記録（なぜ不合格にしたか）は `docs/sfx/verdicts.yaml` に手で書く。

このレポートが答える問いは1つ。
**生成映像（`source: comfyui`）の効果音は、Blender 版と比べてどれだけ絵に合っているか。**

Blender 版はイベントを本番ベイクから吐くので、`onset ズレ` は構造上ゼロになる。
つまりこの表の blender 行は「理論値」で、comfyui 行がそれとどれだけ離れているかが
生成経路の実用性そのものになる。

| | |
|---|---|
| 企画数 | 5 |
| source 内訳 | comfyui 3 / hybrid 2 |
| イベント総数 | 24 |
| ミックスに乗ったキュー | 24 |
| onset ズレ 中央値 | **0.0 ms** |
| 音源が付いた割合 | 100% |


## 企画別

onset ズレの大きい順。

| 企画 | source | イベント | キュー | 実測率 | 音源あり | onset ズレ 中央/p95/最大 (ms) | 同時発音 | LUFS |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| [`cloth_by_faces_hybrid`](#cloth_by_faces_hybrid) | hybrid | 0 | 0 | 0% | 0% | 0.0 / 0.0 / 0.0 | 0 | -14.01 |
| [`glass_fracture_wall_comfy`](#glass_fracture_wall_comfy) | comfyui | 9 | 9 | 0% | 100% | 0.0 / 0.0 / 0.0 | 1 | -16.69 ⚠️ |
| [`growing_ball_bounce_hybrid`](#growing_ball_bounce_hybrid) | hybrid | 0 | 0 | 0% | 0% | 0.0 / 0.0 / 0.0 | 0 | -13.93 |
| [`press_crush_showdown_comfy`](#press_crush_showdown_comfy) | comfyui | 8 | 8 | 0% | 100% | 0.0 / 0.0 / 0.0 | 1 | -16.42 ⚠️ |
| [`sand_avalanche_asmr_comfy`](#sand_avalanche_asmr_comfy) | comfyui | 7 | 7 | 0% | 100% | 0.0 / 0.0 / 0.0 | 1 | -17.07 ⚠️ |

<sub>
**実測率** = 時刻が映像のオンセット実測で決まったイベントの割合。残りは企画が書いたキューシートのまま。
Blender 版はベイク由来なのでどちらも 0%（スナップしていない＝ズレていない）。<br>
**音源あり** = ライブラリか生成で音が付いたキューの割合。残りは macOS システム音頼みで、Linux では無音。<br>
**同時発音** = 0.25 秒の窓に重なった最大キュー数。多いほど濁る。<br>
**LUFS** = 書き出し後の実測。目標 -14。⚠️ は ±1 LU を超えたもの。
</sub>

## 企画別の内訳

### cloth_by_faces_hybrid

面数で変わる布 — Hybrid
`concepts/comfyui/cloth_by_faces_hybrid.yaml`

- source: **hybrid**／イベント 0 → キュー 0
- 型の内訳: - 必要な音源 0 種／キャッシュ済み 0（ヒット率 0%）
- BGM: `assets/audio/bgm/ambient.mp3`
- 書き出し後 -14.01 LUFS（目標 -14 に対して -0.01）

### glass_fracture_wall_comfy

Glass Wall Shatter — ComfyUI
`concepts/comfyui/glass_fracture_wall_comfy.yaml`

- source: **comfyui**／イベント 9 → キュー 9
- 型の内訳: `drop`×4, `impact`×3, `settle`×1, `whoosh`×1- 必要な音源 7 種／キャッシュ済み 7（ヒット率 100%）
- BGM: `assets/audio/bgm/ambient.mp3`
- 書き出し後 -16.69 LUFS（目標 -14 に対して -2.69）

### growing_ball_bounce_hybrid

The Ball Grows Every Bounce — Hybrid
`concepts/comfyui/growing_ball_bounce_hybrid.yaml`

- source: **hybrid**／イベント 0 → キュー 0
- 型の内訳: - 必要な音源 0 種／キャッシュ済み 0（ヒット率 0%）
- BGM: `assets/audio/bgm/ambient.mp3`
- 書き出し後 -13.93 LUFS（目標 -14 に対して 0.07）

### press_crush_showdown_comfy

Hydraulic Press vs Blocks — ComfyUI
`concepts/comfyui/press_crush_showdown_comfy.yaml`

- source: **comfyui**／イベント 8 → キュー 8
- 型の内訳: `collapse`×1, `impact`×5, `settle`×1, `whoosh`×1- 必要な音源 7 種／キャッシュ済み 7（ヒット率 100%）
- BGM: `assets/audio/bgm/ambient.mp3`
- 書き出し後 -16.42 LUFS（目標 -14 に対して -2.42）

### sand_avalanche_asmr_comfy

Sand Wall Collapse — ComfyUI
`concepts/comfyui/sand_avalanche_asmr_comfy.yaml`

- source: **comfyui**／イベント 7 → キュー 7
- 型の内訳: `collapse`×1, `drop`×3, `settle`×2, `tick`×1- 必要な音源 4 種／キャッシュ済み 4（ヒット率 100%）
- BGM: `assets/audio/bgm/ambient.mp3`
- 書き出し後 -17.07 LUFS（目標 -14 に対して -3.07）

## 読み方

- **onset ズレが大きい** — キューシートの予測と生成映像が食い違っている。
  企画のカット尺どおりに動いていないか、映像が暗くてオンセットが拾えていないかのどちらか。
  `実測率` が低ければ後者。
- **実測率 0% で source が comfyui** — 音は鳴るが、タイミングは全部予測のまま。
  1フレーム抜いて目で確かめる価値がある。
- **同時発音が多い** — 音が団子になる。`POLYPHONY_MIN_GAP_SEC` を上げるか、
  企画側の cue を減らす。
- **LUFS が目標から離れている** — 素材のラウドネスレンジが広すぎて
  `loudnorm` が線形正規化に入れていない。効果音か BGM のどちらかが小さすぎる。