# Phase 1 — 画づくり判定シート（Gate 1→2）

`sim.yml` の preview レンダーから集めたコンタクトシート。
等間隔6フレームを 3x2 で並べたもの。判定基準は
`docs/production-plan.md` の Gate 1→2 の5項目。

> mp4 は Actions の `sim-<slug>` アーティファクトから取得する
> （`outputs/` は意図的に gitignore なので動画はコミットしない）。

生成: `gate-review` workflow — 2026-07-29 07:26 UTC

## `ring_escape_5rings`

_コンタクトシートなし（レンダー失敗）_

## `magnetic_pendulum_ufo`

_コンタクトシートなし（レンダー失敗）_

## `paper_to_cloth`

![paper_to_cloth](./paper_to_cloth_contact.png)

```
CHAOSIM_MAX_FRAMES=180: truncating frame_end 720 -> 180
Engine=CYCLES frames=1-180 res%=50 fps=30
CHAOSIM_MAX_FRAMES=180: stage_duration_sec -> 1.500s x 4 stages
Staged frame_end override -> 180
Render complete: /home/runner/work/chaosim/chaosim/outputs/renders/paper_to_cloth.mp4
```

## `cloth_by_faces`

![cloth_by_faces](./cloth_by_faces_contact.png)

```
CHAOSIM_MAX_FRAMES=180: truncating frame_end 600 -> 180
Engine=CYCLES frames=1-180 res%=50 fps=30
CHAOSIM_MAX_FRAMES=180: stage_duration_sec -> 1.500s x 4 stages
Staged frame_end override -> 180
Render complete: /home/runner/work/chaosim/chaosim/outputs/renders/cloth_by_faces.mp4
```

