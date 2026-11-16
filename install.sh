#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v uv >/dev/null; then
    printf '%s\n' 'Install uv first, or follow the manual venv instructions in README.md.' >&2
    exit 3
fi
if [[ ! -x "$project_dir/.venv/bin/python" ]]; then
    uv venv --python /usr/bin/python --system-site-packages "$project_dir/.venv"
fi
uv pip install --python "$project_dir/.venv/bin/python" -e "$project_dir"
"$project_dir/.venv/bin/python" "$project_dir/install.py" "$@"
