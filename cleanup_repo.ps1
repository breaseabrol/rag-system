<#
cleanup_repo.ps1

Trims the rag-system repo down to the minimal "weekend backend" scope:
FastAPI + Postgres/pgvector + BM25 + sentence-transformers + Ollama,
no queue, no frontend, no observability dashboard, no CI.

Usage:
  1. Copy this file into the ROOT of your repo (next to README.md).
  2. Open PowerShell in that folder.
  3. .\cleanup_repo.ps1
     (If scripts are blocked, run once:
        Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
      then re-run this script.)

Safe to re-run — skips anything already missing.
Uses `git rm` when inside a git repo (so deletions are staged),
falls back to plain Remove-Item otherwise.
#>

$ErrorActionPreference = "Stop"
$Root = "."

# ---- sanity check: run this from the repo root -----------------------------
if (-not (Test-Path "$Root/README.md") -or -not (Test-Path "$Root/backend")) {
    Write-Host "Error: run this script from the repo root (README.md and backend/ not found here)." -ForegroundColor Red
    exit 1
}

$IsGitRepo = $false
try {
    git rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -eq 0) { $IsGitRepo = $true }
} catch {
    $IsGitRepo = $false
}

function Remove-RepoPath {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        Write-Host "  skip (already gone): $Path"
        return
    }

    if ($IsGitRepo) {
        git rm -r -q -f "$Path" *> $null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  git rm: $Path"
            return
        }
        # not tracked by git (e.g. untracked file) -- fall back to plain delete
    }

    Remove-Item -Path $Path -Recurse -Force
    Write-Host "  rm: $Path"
}

Write-Host "Removing files/folders out of scope for the minimal weekend backend..."
Write-Host ""

Write-Host "-- accidental / stray files --"
Remove-RepoPath "$Root/backend/get-pip.py"
Remove-RepoPath "$Root/scaffold.ps1"

Write-Host ""
Write-Host "-- async ingestion (queue/worker) --"
Remove-RepoPath "$Root/backend/app/ingestion/worker.py"
Remove-RepoPath "$Root/backend/app/ingestion/tasks.py"

Write-Host ""
Write-Host "-- observability dashboard --"
Remove-RepoPath "$Root/backend/app/api/routes_admin.py"
Remove-RepoPath "$Root/backend/app/observability"

Write-Host ""
Write-Host "-- optional stretch goal --"
Remove-RepoPath "$Root/backend/app/core/reranker.py"

Write-Host ""
Write-Host "-- frontend --"
Remove-RepoPath "$Root/frontend"

Write-Host ""
Write-Host "-- CI workflows --"
Remove-RepoPath "$Root/.github/workflows"

Write-Host ""
Write-Host "-- migrations scaffold (using init_db.py directly instead) --"
Remove-RepoPath "$Root/backend/alembic"

Write-Host ""
Write-Host "-- redundant build config --"
Remove-RepoPath "$Root/backend/pyproject.toml"

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host ""

if ($IsGitRepo) {
    Write-Host "Changes are staged. Review with:"
    Write-Host "  git status"
    Write-Host "then commit with:"
    Write-Host "  git commit -m `"Trim repo to minimal weekend-scope RAG backend`""
} else {
    Write-Host "Not a git repo (or git not initialized here) -- files were deleted directly, no staging to review."
}
