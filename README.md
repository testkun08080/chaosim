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
| [docs/project-structure.md](docs/project-structure.md) | ディレクトリ構成と各モジュールの役割 |
| [docs/workflow.md](docs/workflow.md) | セットアップ手順・使い方・拡張方法 |
| [docs/concepts-guide.md](docs/concepts-guide.md) | サンプル企画 5 本の解説と YAML フィールド一覧 |