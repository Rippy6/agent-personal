FROM python:3.12-slim

WORKDIR /app

# メタデータ
LABEL maintainer="agent-personal contributors"
LABEL description="完全自律AIエージェント — 自分で考え、判断し、行動する分身"

# セキュリティ: 非rootユーザー
RUN groupadd -r agent && useradd -r -g agent -d /app -s /bin/bash agent

# 依存インストール（オプション: Claude/OpenAI API使用時）
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[all-brains]" 2>/dev/null || pip install --no-cache-dir -e .

# アプリケーションコピー
COPY . .

# データディレクトリ
RUN mkdir -p /app/data && chown -R agent:agent /app

USER agent

# ダッシュボードポート
EXPOSE 8080

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=5s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/state')" || exit 1

# デフォルト: ダッシュボード付きで自律モード起動
ENTRYPOINT ["python", "main.py"]
CMD ["--dashboard"]
