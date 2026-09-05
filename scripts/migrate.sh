#!/usr/bin/env bash
# =============================================================================
# RPent migration helper
#
# One-click export of the RPent environment manifest(s) and push of the large
# data artifacts (Pi0.5 VLA weights, SAM 3.0 checkpoint, LIBERO(-PRO) assets)
# to an external registry -- ModelScope (reachable in CN) or a GitHub release.
#
# Usage:
#   ./scripts/migrate.sh manifest                    # write manifests to ./migration/
#   ./scripts/migrate.sh pack                        # conda-pack the whole env (heavy, ~15GB)
#   ./scripts/migrate.sh push-ms <ns>/<model>        # push data to ModelScope
#   ./scripts/migrate.sh push-gh <repo> <tag>        # push data to a GitHub release
#
# Data locations are read from env vars (with local defaults):
#   PI05_CHECKPOINT_PATH   Pi0.5 VLA checkpoint directory
#   SAM3_CHECKPOINT_PATH   path to sam3.pt
#   LIBERO_ASSETS_DIR      LIBERO(-PRO) simulator assets directory
#   VLA_CONDA_ENV          conda env name to export (default: active env)
#
# Notes
#   - The manifests are text and belong in the repo. The packed env tarball is
#     ~15GB and must NOT be committed; keep it out of git (see .gitignore).
#   - The full stack is pinned to torch==2.7.1 upstream. On glibc < 2.28 hosts
#     we override it to torch==2.6.0 (see README of the migration dir); a
#     modern host (glibc >= 2.28) can install the official stack directly, so
#     prefer "manifest" over "pack" unless the target is also glibc < 2.28.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIG_DIR="$REPO_ROOT/migration"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PI05_CHECKPOINT_PATH="${PI05_CHECKPOINT_PATH:-/vla_test/yjx/rpent_data/checkpoints/pi05}"
SAM3_CHECKPOINT_PATH="${SAM3_CHECKPOINT_PATH:-/vla_test/yjx/rpent_data/checkpoints/sam3/sam3.pt}"
LIBERO_ASSETS_DIR="${LIBERO_ASSETS_DIR:-}"

PY="${VLA_PYTHON:-python3}"

log()  { echo -e "\033[1;34m[migrate]\033[0m $*"; }
die()  { echo -e "\033[1;31m[migrate:error]\033[0m $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# manifest -- export conda + pip manifests
# ---------------------------------------------------------------------------
cmd_manifest() {
    mkdir -p "$MIG_DIR"
    log "writing pip manifest -> $MIG_DIR/requirements-pinned.txt"
    "$PY" -m pip freeze > "$MIG_DIR/requirements-pinned.txt"
    if command -v conda >/dev/null 2>&1; then
        log "writing conda manifest -> $MIG_DIR/environment.yml"
        conda env export > "$MIG_DIR/environment.yml"
    else
        log "conda not on PATH; skipping environment.yml (pip freeze written)"
    fi
    cat > "$MIG_DIR/README.md" <<'EOF'
# RPent migration artifacts

- `requirements-pinned.txt` -- exact pip dependency set of the working env.
- `environment.yml`         -- full conda + pip environment export.

## Reproducing

- **On a modern host (glibc >= 2.28):** just
  `pip install -e ".[full]"` -- the upstream pins (torch==2.7.1 etc.) install
  directly. Do NOT carry the overrides below.
- **On glibc < 2.28 hosts** (e.g. Ubuntu 18.04): the official wheels are
  manylinux_2_28-only and will not install. The working env here applies:
  - `torch==2.6.0` + `torchvision==0.21.0` (last manylinux1 builds),
    installed in place of the pinned `torch==2.7.1`
  - `h5py==3.9.0` (last manylinux2014 build)
  - `jax[cuda12]==0.5.3`, `flax==0.10.2`, `numpy<2`
  - install the rlinf/* packages with `--no-deps` first, then the manifest
  - `conda pack` (see `./scripts/migrate.sh pack`) is the only way to
    reproduce the full stack 1:1 on another glibc-2.27 host
EOF
    log "manifests ready in $MIG_DIR"
}

# ---------------------------------------------------------------------------
# pack -- conda-pack the whole environment (same-glibc reproduction only)
# ---------------------------------------------------------------------------
cmd_pack() {
    command -v conda >/dev/null 2>&1 || die "conda not found"
    ENV="${VLA_CONDA_ENV:-}"
    if [ -z "$ENV" ]; then
        ENV="$("$PY" -c 'import sys,os;print(os.path.basename(sys.prefix))')"
    fi
    mkdir -p "$MIG_DIR"
    command -v conda-pack >/dev/null 2>&1 || {
        log "installing conda-pack"
        conda install -y -n base conda-pack >/dev/null
    }
    log "packing env '$ENV' (this takes a while, ~15GB)"
    conda pack -n "$ENV" -o "$MIG_DIR/rpent-$ENV-env.tar.gz"
    log "packed -> $MIG_DIR/rpent-$ENV-env.tar.gz"
    log "restore on a same-glibc host: mkdir -p ~/rpent-vla && tar -xzf rpent-$ENV-env.tar.gz -C ~/rpent-vla && source ~/rpent-vla/bin/activate"
}

# ---------------------------------------------------------------------------
# stage_data -- build a single directory with weights + assets for upload
# ---------------------------------------------------------------------------
stage_data() {
    STAGE="$MIG_DIR/data-staging"
    rm -rf "$STAGE"; mkdir -p "$STAGE"
    [ -d "$PI05_CHECKPOINT_PATH" ] || die "Pi0.5 checkpoint not found: $PI05_CHECKPOINT_PATH (set PI05_CHECKPOINT_PATH)"
    [ -f "$SAM3_CHECKPOINT_PATH" ] || die "SAM3 checkpoint not found: $SAM3_CHECKPOINT_PATH (set SAM3_CHECKPOINT_PATH)"

    log "staging Pi0.5 -> $STAGE/rlinf-pi05-libero-130-fullshot-sft"
    cp -r "$PI05_CHECKPOINT_PATH" "$STAGE/rlinf-pi05-libero-130-fullshot-sft"
    log "staging SAM3  -> $STAGE/sam3/sam3.pt"
    mkdir -p "$STAGE/sam3"; cp "$SAM3_CHECKPOINT_PATH" "$STAGE/sam3/sam3.pt"

    if [ -z "$LIBERO_ASSETS_DIR" ]; then
        LIBERO_ASSETS_DIR="$("$PY" -c 'import os,liberopro.liberopro as l; print(l.get_default_path_dict()["assets"])' 2>/dev/null || true)"
    fi
    if [ -n "$LIBERO_ASSETS_DIR" ] && [ -d "$LIBERO_ASSETS_DIR" ]; then
        log "staging LIBERO assets -> $STAGE/libero-pro-assets"
        cp -r "$LIBERO_ASSETS_DIR" "$STAGE/libero-pro-assets"
    else
        log "WARNING: LIBERO assets dir not found, skipping (set LIBERO_ASSETS_DIR)"
    fi
    echo "$STAGE"
}

# ---------------------------------------------------------------------------
# push-ms -- push staged data to ModelScope
# ---------------------------------------------------------------------------
cmd_push_ms() {
    [ $# -eq 1 ] || die "usage: ./scripts/migrate.sh push-ms <namespace>/<model-name>"
    MODEL_ID="$1"
    : "${MODELSCOPE_API_TOKEN:?set MODELSCOPE_API_TOKEN (modelscope.cn -> user avatar -> access token)}"
    STAGE="$(stage_data)"
    "$PY" -c 'import modelscope' 2>/dev/null || {
        log "installing modelscope SDK"
        "$PY" -m pip install -q modelscope
    }
    log "pushing $STAGE -> ModelScope:$MODEL_ID"
    "$PY" - "$MODEL_ID" "$STAGE" "$MODELSCOPE_API_TOKEN" <<'PY'
import sys
from modelscope.hub.api import HubApi
model_id, local_dir, token = sys.argv[1], sys.argv[2], sys.argv[3]
api = HubApi()
api.login(token)
try:
    api.create_model_repo(model_id=model_id, visibility="public")
except Exception as e:  # repo already exists
    print(f"[migrate] create_model_repo note: {e}")
api.push_model(model_id=model_id, local_dir=local_dir, commit_message="RPent data: Pi0.5 VLA + SAM3 + LIBERO-PRO assets")
print(f"[migrate] pushed -> https://www.modelscope.cn/models/{model_id}")
PY
}

# ---------------------------------------------------------------------------
# push-gh -- push staged data to a GitHub release
# ---------------------------------------------------------------------------
cmd_push_gh() {
    [ $# -eq 2 ] || die "usage: ./scripts/migrate.sh push-gh <owner/repo> <tag>"
    command -v gh >/dev/null 2>&1 || die "gh CLI not installed (see https://cli.github.com)"
    gh auth status >/dev/null 2>&1 || die "gh not authenticated (run: gh auth login)"
    REPO="$1"; TAG="$2"
    STAGE="$(stage_data)"
    TBZ="$MIG_DIR/rpent-data-$TAG.tar.gz"
    log "creating tarball $TBZ"
    tar -czf "$TBZ" -C "$STAGE" .
    log "creating release $REPO:$TAG"
    gh release create "$TAG" "$TBZ" --repo "$REPO" --title "RPent data: $TAG" --generate-notes 2>/dev/null || \
        gh release upload "$TAG" "$TBZ" --repo "$REPO" --clobber
    log "pushed -> https://github.com/$REPO/releases/tag/$TAG"
}

case "${1:-}" in
    manifest) shift; cmd_manifest "$@" ;;
    pack)     shift; cmd_pack "$@" ;;
    push-ms)  shift; cmd_push_ms "$@" ;;
    push-gh)  shift; cmd_push_gh "$@" ;;
    *)
        sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
        exit 1
        ;;
esac
