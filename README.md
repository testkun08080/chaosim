# chaosim

カオスシミュレーション動画の自動生成・投稿パイプライン。  
企画 → Blender シミュレーション → レンダリング → YouTube Shorts アップロードまでを一本のコマンドで実行できる。

## クイックスタート

```bash
pip install -r requirements.txt
cp .env.example .env  # ANTHROPIC_API_KEY, BLENDER_PATH を設定

# サンプル企画を全工程実行
python scripts/chaosim.py run concepts/sample_001_double_pendulum.yaml
```

## ドキュメント

| ドキュメント | 内容 |
|---|---|
| [docs/production-plan.md](docs/production-plan.md) | 制作ガイド（セットアップ・運用＋企画→スライス→展開→合成→投稿のフェーズ＆ゲート） |
| [docs/media-pipeline-playbook.md](docs/media-pipeline-playbook.md) | 生成メディア自動化パイプラインの再利用可能な設計原則（プロジェクト非依存） |
| [docs/sfx-design.md](docs/sfx-design.md) | 効果音の設計・合成提案（現状の課題と改善案） |
| [docs/ci.md](docs/ci.md) | GitHub Actions での実行（ワークフロー構成・プリセットのコスト制約・artifact 契約） |
| [docs/project-structure.md](docs/project-structure.md) | ディレクトリ構成と各モジュールの役割 |
| [docs/concepts-guide.md](docs/concepts-guide.md) | サンプル企画 5 本の解説と YAML フィールド一覧 |