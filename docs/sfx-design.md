# 効果音（SFX）設計・合成提案

物理シミュレーション系ショートの生命線は「動きと音の一致」。
崩れる・ぶつかる・着弾する瞬間に音がピタッと合うと満足感が跳ね上がる。
逆に音が汎用的だったりズレたりすると一気に安っぽくなる。
ここが本パイプラインで一番難しい部分なので、現状の整理と改善提案をまとめる。

参考動画の音の付け方（衝突ごとに硬質なヒット音＋低域の余韻、全体は静かなBGM）を到達目標とする:
https://www.youtube.com/watch?v=3Rh_qusBOTw

---

## 1. 現状の実装

効果音は既に動く。3系統ある（`pipeline/audio_assets.py` → `compositor.mix_tracks`）。

**(a) 固定アンカーキュー** — 動画テンプレ `templates/video/*.yaml` の `sfx.cues`。
`intro_start` / `sim_start` / `outro_start` の3点に音を置く。

```yaml
sfx:
  cues:
    - { at: intro_start, sound: Submarine }
    - { at: sim_start,   sound: Glass }
    - { at: outro_start, sound: Hero }
  scene_event_sound: Tink
  scene_events: true
```

**(b) シミュレーションイベント** — Blender 側 `collect_impact_events()` が衝突時刻を拾い、
`outputs/renders/<slug>_events.json` に `[{t, type, object}]` で書く。
`resolve_sfx_cues` がこれを1音（既定 `Tink`）に割り当て、連鎖の後半をわずかにフェードして重ねる。

**(c) ミックス** — `mix_tracks` が各キューを `adelay`（開始遅延）＋`volume` で本編音声に合成し、
ナレーション・BGM と `amix` する。

**音源** — 現状は macOS システムサウンド（`/System/Library/Sounds` の Submarine / Glass / Tink / Hero）を
`catalog.yaml` の役割エイリアス経由で参照。

---

## 2. 現状の課題（ここが難点）

| # | 課題 | 影響 |
|---|---|---|
| 1 | **音源が macOS システム音依存** | mac でしか鳴らない・音が「Mac っぽい」・YouTube 収益化やライセンス面で不安 |
| 2 | **イベント出力が一部シーンのみ** | `domino_chain` 中心。流体・砂・振り子・ローレンツは衝突音が付かない |
| 3 | **1イベント=1音の使い回し** | 同じ音が連打され機械的（マシンガン化）。強弱・音程のばらつきがない |
| 4 | **強度情報がない** | イベントが `{t,type,object}` のみ。大きい衝突も小さい衝突も同じ音量になる |
| 5 | **レイヤーがない** | 実物のヒット音は「アタック＋ボディ＋低域の余韻」。単発では軽い |
| 6 | **ダッキング/正規化なし** | BGM が効果音・ナレを潰す、または全体が突き刺さる。YouTube 基準（-14 LUFS）に未対応 |
| 7 | **同期の保証が弱い** | イベントを別ベイクすると、本番レンダーとシミュレーション初期値がズレる恐れ |

---

## 3. 提案（推奨案 A）— データ駆動の型付きイベント → SFXライブラリ → FFmpeg合成

現状の枠組み（イベントJSON → キュー → mix）は正しい。**中身を4点強化**する。

### 3-1. イベントスキーマを型＋強度付きに拡張

全シーンの `collect_impact_events()` が返す1イベントを次の形に統一する:

```json
{ "t": 2.35, "type": "impact", "intensity": 0.82, "object": "domino_07" }
```

- `type` — `impact`（衝突）/ `drop`（着弾）/ `collapse`（崩落開始）/ `whoosh`（高速移動）/ `settle`（静止）
- `intensity` — 0〜1。衝突相対速度や運動量から算出（音量・音源選択・低域量にマップ）

**同期の担保:** イベントは**本番レンダーと同じベイク**から出す。`t` は秒なので fps 非依存
（現状の設計は正しい）。`simulators/blender/runner.py` にベイク後 `collect_impact_events()` を呼んで
`<slug>_events.json` を書く処理を入れ、`bake_sfx_events.py` は「レンダーせず確認だけ」用に残す。

各シーンでの強度の取り方（例）:
- ドミノ/剛体: `object.rigid_body` の直前フレームとの速度差、または接触時の相対速度
- 砂崩壊: 崩落開始フレーム＝1発の `collapse`＋粒子の着地を間引いてサンプリング
- 流体インク: 液滴の水面着弾フレームを `drop` として検出（Z速度の符号反転）
- 振り子/ローレンツ: 衝突がないので原則ミュート。折返し極点に軽い `tick` を任意付与

### 3-2. 同梱 SFX ライブラリ（システム音依存を脱却）

`assets/audio/sfx/` にロイヤリティフリー音源を役割別に置き、`catalog.yaml` を拡張する。

```
assets/audio/sfx/
  impact_soft/   { wood_01.wav, wood_02.wav, ... }   # 木・軽い衝突
  impact_hard/   { glass_01.wav, metal_01.wav, ... } # 硬質・大きい衝突
  drop/          { water_01.wav, ... }               # 着弾・水滴
  whoosh/        { air_01.wav, ... }                 # 高速移動
  rumble/        { low_01.wav, ... }                 # 低域の余韻（レイヤー用）
  ui/            { tick_01.wav, ... }                # 極点・クリック
```

```yaml
# catalog.yaml 拡張案
sfx_events:
  impact:   { library: [impact_soft, impact_hard], layer_low: rumble }
  drop:     { library: [drop] }
  collapse: { library: [rumble], oneshot: true }
  whoosh:   { library: [whoosh] }
# intensity で impact_soft ↔ impact_hard を選び分ける
```

音源入手（各自でライセンスを確認して取得。**リポジトリに商用不可音源をコミットしない**）:
- Freesound（CC0 でフィルタ）/ Kenney（CC0 のゲーム用SFX）/ Sonniss GDC 版（毎年無料配布）
- macOS 依存は**フォールバック**として残す（`catalog.yaml` に無いときのみ）

### 3-3. 1発ごとに自然なばらつき（マシンガン化の回避）

`resolve_sfx_cues` / `mix_tracks` を次のように強化:

- **ラウンドロビン** — ライブラリ内の複数ファイルを順に/ランダムに使い分け
- **ピッチ±数%** — FFmpeg `asetrate=SR*R,aresample=SR`（`R≈0.94〜1.06`）で1発ごとに微妙に変える
- **強度→音量＆音源** — `intensity` を `volume` と soft/hard 選択にマップ
- **ポリフォニー制限** — 近接イベント（例 <40ms）を1発に間引き、重なりすぎの濁りを防ぐ
- **低域レイヤー** — 大きい `impact`/`collapse` に `rumble` を薄く重ねて「重さ」を出す

### 3-4. ミックスのFFmpegチェーン（レイヤー・ダッキング・正規化）

`mix_tracks` の合成方針。1発の効果音は「本体＋（強ければ）低域」を重ねる:

```
# 1発の impact（強度0.8）: 本体を少しピッチ変え、低域を薄く足す
[hit] asetrate=48000*1.03,aresample=48000,adelay=D|D,volume=0.8[hitv]
[low] volume=0.25,adelay=D|D[lowv]
[hitv][lowv] amix=inputs=2[ev]
```

BGM は効果音とナレの瞬間だけ自動で下げる（サイドチェイン・ダッキング）:

```
# ナレ+効果音を鍵に BGM を踏む
[bgm][keys] sidechaincompress=threshold=0.05:ratio=8:attack=5:release=250[bgmducked]
```

最終段でラウドネスを YouTube 基準に正規化（Phase 4 の書き出しに組み込む）:

```
loudnorm=I=-14:LRA=11:TP=-1.5
```

**設計上の狙い:** 効果音は前に出す／BGMは踏んで沈める／全体は -14 LUFS で揃える。
これで「衝突が気持ちよく刺さり、BGM は邪魔しない」参考動画の質感に寄る。

---

## 4. 代替案

| 案 | 内容 | 使いどころ |
|---|---|---|
| **B プロシージャル合成** | 衝突音を都度合成（減衰ノイズ＋トーン、`sfxr`/簡易シンセ）。ライセンス完全クリア・パラメトリック | CI・完全自動・音源を持ちたくない時のフォールバック。現状のシステム音スタブの置き換えに最適 |
| **C 手作業（DAW）** | 本番素材の音だけ Reaper/Audition 等で手置き。最高品質 | 「勝負回」のヒーロー動画。自動化はしない |
| **D 外部SFX MCP/API** | 効果音生成APIをMCP経由で叩き、イベントごとに生成音を取得 | 将来拡張。イベントJSONの `type/intensity` をそのままプロンプト化できる |

**推奨:** 日常の量産は **A**、音源を持ち込めない環境の自動フォールバックに **B**、
ヒーロー回だけ **C**。A と B は `catalog.yaml` に音源があるかで自動分岐させる（現状のスタブ思想と同じ）。

---

## 5. コンポジットにおける「効果音の付け方」まとめ（結論）

1. **タイミングはシミュレーションが決める** — 手打ちしない。Blender のベイクから
   型付き・強度付きイベント（`<slug>_events.json`）を本番と同じ計算で吐く。
2. **音源はライブラリから型で引く** — イベント `type`＋`intensity` → `catalog.yaml` の役割 →
   ロイヤリティフリー音源。macOS 音はフォールバックに降格。
3. **1発ごとに揺らす** — ラウンドロビン＋ピッチ/音量ランダム＋ポリフォニー制限で機械感を消す。
4. **重ねる** — 大きい衝突は本体＋低域レイヤーで重量感を出す。
5. **BGMを踏む** — 効果音・ナレの瞬間だけサイドチェインで BGM を下げる。
6. **最後に揃える** — `loudnorm=I=-14` で YouTube 基準に正規化してから書き出す。

### 実装の着手順（最小差分で効果大）

1. `loudnorm` を最終エンコードに追加（1行、全動画が即改善）
2. `collect_impact_events` に `intensity` を追加 → 音量マップ
3. 1発ごとのピッチ/音量ランダム＋ポリフォニー制限を `resolve_sfx_cues` に追加
4. `assets/audio/sfx/` ＋ `catalog.yaml.sfx_events` を用意し system 音から移行
5. BGM サイドチェイン・ダッキングを `mix_tracks` に追加
6. イベント出力を全シーンへ展開（流体・砂・振り子）
