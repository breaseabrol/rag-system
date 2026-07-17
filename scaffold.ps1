$Root = "."

Write-Host "Scaffolding $Root ..."

$Dirs = @(
    "$Root/backend/app/api",
    "$Root/backend/app/core",
    "$Root/backend/app/db",
    "$Root/backend/app/ingestion",
    "$Root/backend/app/observability",
    "$Root/backend/app/schemas",
    "$Root/backend/eval",
    "$Root/backend/tests",
    "$Root/backend/scripts",
    "$Root/backend/alembic",
    "$Root/frontend/src/api",
    "$Root/frontend/src/components",
    "$Root/frontend/src/hooks",
    "$Root/.github/workflows"
)

foreach ($d in $Dirs) {
    New-Item -ItemType Directory -Path $d -Force | Out-Null
}

$Files = @(
    "$Root/backend/app/__init__.py",
    "$Root/backend/app/main.py",
    "$Root/backend/app/config.py",

    "$Root/backend/app/api/__init__.py",
    "$Root/backend/app/api/routes_query.py",
    "$Root/backend/app/api/routes_ingest.py",
    "$Root/backend/app/api/routes_admin.py",

    "$Root/backend/app/core/__init__.py",
    "$Root/backend/app/core/chunking.py",
    "$Root/backend/app/core/embeddings.py",
    "$Root/backend/app/core/retrieval.py",
    "$Root/backend/app/core/generation.py",
    "$Root/backend/app/core/reranker.py",

    "$Root/backend/app/db/__init__.py",
    "$Root/backend/app/db/models.py",
    "$Root/backend/app/db/session.py",
    "$Root/backend/app/db/vector_store.py",

    "$Root/backend/app/ingestion/__init__.py",
    "$Root/backend/app/ingestion/loader.py",
    "$Root/backend/app/ingestion/worker.py",
    "$Root/backend/app/ingestion/tasks.py",

    "$Root/backend/app/observability/__init__.py",
    "$Root/backend/app/observability/logger.py",
    "$Root/backend/app/observability/tracer.py",
    "$Root/backend/app/observability/metrics.py",

    "$Root/backend/app/schemas/__init__.py",
    "$Root/backend/app/schemas/models.py",

    "$Root/backend/eval/__init__.py",
    "$Root/backend/eval/build_eval_set.py",
    "$Root/backend/eval/run_eval.py",
    "$Root/backend/eval/metrics.py",
    "$Root/backend/eval/eval_dataset.jsonl",

    "$Root/backend/tests/__init__.py",
    "$Root/backend/tests/test_chunking.py",
    "$Root/backend/tests/test_retrieval.py",
    "$Root/backend/tests/test_api.py",
    "$Root/backend/tests/test_eval_regression.py",

    "$Root/backend/scripts/compare_chunking.py",
    "$Root/backend/scripts/compare_embeddings.py",

    "$Root/backend/alembic/.gitkeep",

    "$Root/backend/requirements.txt",
    "$Root/backend/Dockerfile",
    "$Root/backend/pyproject.toml",

    "$Root/frontend/src/main.tsx",
    "$Root/frontend/src/App.tsx",
    "$Root/frontend/src/api/client.ts",

    "$Root/frontend/src/components/ChatWindow.tsx",
    "$Root/frontend/src/components/SourceCitations.tsx",
    "$Root/frontend/src/components/UploadPanel.tsx",
    "$Root/frontend/src/components/EvalDashboard.tsx",

    "$Root/frontend/src/hooks/useStreamingQuery.ts",
    "$Root/frontend/src/types.ts",

    "$Root/frontend/index.html",
    "$Root/frontend/package.json",
    "$Root/frontend/vite.config.ts",
    "$Root/frontend/tsconfig.json",

    "$Root/.github/workflows/ci.yml",
    "$Root/.github/workflows/eval-regression.yml",

    "$Root/docker-compose.yml",
    "$Root/README.md"
)

foreach ($f in $Files) {
    New-Item -ItemType File -Path $f -Force | Out-Null
}

@"
# Python
__pycache__/
*.pyc
.venv/
venv/
*.egg-info/

# Node
node_modules/
dist/
.env
.env.local

# DB / data
*.db
*.sqlite3

# OS
.DS_Store
"@ | Out-File -FilePath "$Root/.gitignore" -Encoding utf8

Write-Host "Done. Structure created under ./$Root"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  cd $Root"
Write-Host "  git init"
Write-Host "  git add ."
Write-Host "  git commit -m 'Initial project scaffold'"
Write-Host "  git branch -M main"
Write-Host "  git remote add origin https://github.com/<your-username>/<repo-name>.git"
Write-Host "  git push -u origin main"
