# ComfyUI 経路 — プロンプトから素材を作る

企画 YAML の `source:` が、その1本の映像をどう作るかを決める。

| source | 映像 | 効果音のタイミング | 使いどころ |
|---|---|---|---|
| `blender`（既定） | 物理シミュレーション | ベイク由来（**正確**） | 数えられる／検証できる題材 |
| `comfyui` | プロンプトから生成 | キューシート＋オンセット実測 | 検証できない題材（砂・破砕・流体） |
| `hybrid` | Blender シミュ＋ComfyUI 生成の素材 | ベイク由来（**正確**） | シミュは通っているが画が弱い企画 |

3つとも最後は同じ2ファイルに着地する。

```
outputs/renders/<slug>.mp4          映像
outputs/renders/<slug>_events.json  いつ何が鳴るべきか
```

段の契約がこの2ファイルだけなので、`material` 以降（オーバーレイ・ナレーション・
合成・サムネ・投稿）はどの経路で作られたかを知らない。だから ComfyUI 対応は
差し替えではなく `renderer.py` の分岐1箇所で済んでいる。

---

## 1. セットアップ

ワークフロー JSON と実行系は別リポジトリ [`comfyui-sandbox`](https://github.com/testkun08080/comfyui-sandbox) にある。
chaosim はそこの `scripts/comfy_run.py` を**サブプロセスとして叩く**（Blender や
HyperFrames と同じ扱い）。検証・課金ガード・`--dry-run` は向こう側の実装をそのまま使う。

```bash
git clone https://github.com/testkun08080/comfyui-sandbox ../comfyui-sandbox
cd ../comfyui-sandbox
cp .env.example .env      # COMFY_API_KEY を書く（platform.comfy.org で発行）
uv sync
```

chaosim 側の `.env`:

```bash
COMFYUI_SANDBOX_PATH=../comfyui-sandbox
```

**API キーは chaosim には置かない。** `comfy_run.py` が sandbox の `.env` から読む。
鍵の置き場を1箇所に保つためで、chaosim 側に `COMFY_API_KEY` を書く必要はない。

sandbox が無い環境（CI・新しい手元・サンドボックス）では `comfyui_available()` が偽になり、
すべて ffmpeg のスタブに降格する。配線は最後まで検証されるが、画は出ない。

```bash
CHAOSIM_STUB=1 python scripts/chaosim.py run concepts/comfyui/sand_avalanche_asmr_comfy.yaml
```

---

## 2. 費用（これが設計を決めている）

動画生成は1カット $0.25 から。画像生成の一桁上なので、既定は全部低い方に倒してある。

| もの | 既定 | 目安 |
|---|---|---|
| Wan Image to Video | `480P` / 5秒 | 約 $0.05/秒 → 1カット **$0.25** |
| 同 720P | — | 約 $0.10/秒 → 1カット $0.50 |
| Recraft V4（キーフレーム） | `768x1344` | 1枚あたり数セント |
| ElevenLabs 効果音 | 0.3〜2.2秒 | 約 $0.14/分。1音は1セント未満 |

**投げる前に必ず値段を見る。**

```bash
# 何カット・何秒・いくらか（送信なし）
python scripts/chaosim.py render concepts/comfyui/<slug>.yaml --dry-run

# 効果音は何本生成するか（送信なし）
python scripts/chaosim.py sfx-build concepts/comfyui/<slug>.yaml --dry-run
```

全 ComfyUI 呼び出しを止める非常ブレーキ:

```bash
export CHAOSIM_COMFY_DRY_RUN=1
```

効果音の生成は `compose` では**既定で走らない**。`compose` が黙って40発ぶん課金するのは
事故なので、支払う場所は `sfx-build` に寄せてある。例外はサンドボックスが無いとき
（＝課金しようがないとき）で、そのときだけ無料のスタブ音でキャッシュを埋める。

---

## 3. `source: comfyui` — カット割りとキューシート

```yaml
source: comfyui
comfyui:
  recipe: generative_shots
  resolution: 480P
  seed: 4100
  shots:
    - name: shot_01_wall
      # 画だけを書く。動きの語を入れない
      keyframe_prompt: >
        Vertical 9:16 composition. A tall wall of fine dry orange sand ...
      # 動きだけを書く。カメラを止める指示を必ず入れる
      prompt: >
        The camera holds completely still. The face of the sand wall gives way ...
      duration: 5            # 5 / 10 / 15 のみ。他は丸められる
      cues:                  # このカットの先頭からの秒数
        - {t: 0.9, type: collapse, intensity: 0.95}
        - {t: 1.8, type: drop, intensity: 0.6}
```

### 2つの prompt を混ぜない

画像モデルは動きの語を**構図**として読み、動画モデルは構図の語を**カメラワーク**として読む。
混ぜると狙いと違う方向に両方が寄る。`keyframe_prompt` は素材・光・寄り引き、
`prompt` は「何がどう動くか」と「カメラを止めるかどうか」だけにする。

満足系ショートは固定カメラで成立するフォーマットなので、
`prompt` にはほぼ常に *The camera holds completely still.* を入れる。

### cue が唯一のタイミング情報

生成映像にはベイクが無い。`cues` を書かなければ、絵は出るが**音が一切鳴らない**。
`catalog --check` はこれを `no-cues` として警告する。

`type` は `impact` / `drop` / `collapse` / `whoosh` / `settle` / `tick`。
`intensity` は 0〜1 で、音量と soft/mid/hard の音源選択の両方に効く。

### 生成後にタイミングを測り直す

キューシートは**予測**にすぎない。レンダー後、映像のオンセット（画の急変）を実測して
各 cue を近傍のオンセットへスナップし、どちらで決まった時刻かを残す。

```json
{"t": 1.35, "type": "collapse", "intensity": 0.95,
 "object": "shot_01_wall", "source": "onset", "cue_t": 1.2}
```

`source: "cue"` のまま残ったものは、近くにオンセットが見つからなかったもの。
どれだけ動いたかは `sfx-report` の `onset_delta_ms` に出る。

---

## 4. `source: hybrid` — 画だけ生成する

シミュが通っていて画だけが弱い企画は、シミュを捨てる理由がない。捨てると
正確な衝突タイミング（＝効果音の当て先）まで一緒に失う。生成するのは素材だけにする。

```yaml
source: hybrid
scene_script: growing_ball
comfyui:
  recipe: look_assets
  assets:
    - param: backdrop_image      # 生成した PNG のパスがこの params キーに入る
      name: arena_backplate
      size: "1344x768"
      prompt: >
        A smooth deep teal to midnight blue gradient studio backdrop ...
params:
  backdrop_image: ...            # 生成が走ると差し替わる
```

生成物は `assets/generated/<slug>/<name>.png`（gitignore 済み）。
すでにファイルがあれば再生成しないので、2回目以降は無料。

シーン側は生成物であることを知らない。ただの params の値として受け取る。
`world_hdri` を使う場合、生成した PNG は LDR なので本物の HDRI のような
強いハイライトは出ない。環境の色と明暗の配置は決められる。

---

## 5. 新しいワークフローを足す

ワークフローは sandbox 側に置く。chaosim 側にはノード ID の対応表だけを足す。

1. `comfyui-sandbox/scripts/composite_specs.py` の `SPECS` に定義を書き、
   `uv run scripts/build_composites.py && uv run scripts/ui_to_api.py` で生成する
   （`widgets_values` は順番だけが頼りなので手書きしない）
2. `uv run scripts/validate_workflows.py` を通す（API キー不要・課金なし）
3. chaosim の `simulators/comfyui/__init__.py` の `WORKFLOW_INPUTS` に
   「論理名 → `<ノードID>.<入力名>`」を追加する

対応表を1箇所に集めてあるのは、sandbox 側でノードを振り直したときに
レシピを追いかけずに1行で直せるようにするため。

---

## 6. Phase 1（バーティカルスライス）の翻訳

`docs/production-plan.md` のフェーズ・ゲートはそのまま使える。安く試すやり方だけが違う。

| | blender | comfyui |
|---|---|---|
| スライス | `--preset preview`（サンプル32・解像度50%） | `480P` / 5秒 / **1カットだけ** |
| 安くする操作 | サンプル数と解像度を下げる | 解像度と尺とカット数を下げる |
| ゲートの5項目 | framing / look / sim / hook / duration | 同じ |

1カットだけ回すには `comfyui.max_shots: 1` を一時的に足す。

```bash
python scripts/chaosim.py render concepts/comfyui/<slug>.yaml --dry-run   # 値段を見る
python scripts/chaosim.py render concepts/comfyui/<slug>.yaml             # 投げる
```

ゲートを通るまで `720P` 以上と全カットには進まない。

---

## 7. 困ったとき

| 症状 | 原因 | 対処 |
|---|---|---|
| `workflow not found` | `COMFYUI_SANDBOX_PATH` が違う | パスを確認。`comfy_run.py` があるか見る |
| `unknown input '...'` | `WORKFLOW_INPUTS` に無い論理名 | 誤字。黙って既定値で回すと高くつくのでわざと落としている |
| 音が鳴らない | 音源が解決していない | `sfx-report` の `音源あり` 列を見る。0% なら `sfx-build` |
| `no-cues` 警告 | cue を書いていない | 絵は出るが無音になる。`cues:` を足す |
| onset ズレが大きい | 予測と生成映像が食い違っている | `sfx-report` の `実測率` が低ければ映像が暗くて拾えていない |
| 想定より高い | 解像度か尺か本数 | `--dry-run` で内訳を出す |
