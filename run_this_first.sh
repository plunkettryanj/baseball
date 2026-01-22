#!/usr/bin/env bash
set -euo pipefail

# change to script directory (project root)
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VENV_DIR="baseball-env"
REQ_FILE="requirements.txt"

# Prefer pyenv if available, otherwise use built-in venv
if command -v pyenv >/dev/null 2>&1; then
    PY_VERSION="3.11.4"
    # ensure python version and venv exist (no-op if already present)
    pyenv install -s "${PY_VERSION}"
    if ! pyenv virtualenvs --bare | grep -qx "${VENV_DIR}"; then
        pyenv virtualenv "${PY_VERSION}" "${VENV_DIR}"
    fi
    # activate for current shell
    if pyenv commands | grep -q "activate"; then
        pyenv activate "${VENV_DIR}"
    else
        pyenv shell "${VENV_DIR}"
    fi
else
    # find a python executable
    if command -v python3 >/dev/null 2>&1; then
        PY_CMD=python3
    elif command -v python >/dev/null 2>&1; then
        PY_CMD=python
    else
        echo "Python not found in PATH. Install Python first."
        exit 1
    fi

    # create venv if missing
    if [[ ! -d "${VENV_DIR}" ]]; then
        "${PY_CMD}" -m venv "${VENV_DIR}"
        echo "Created venv at ${VENV_DIR}"
    fi

    # activate venv for this shell (Git Bash on Windows uses Scripts/activate)
    if [[ -f "${VENV_DIR}/Scripts/activate" ]]; then
        # shellcheck source=/dev/null
        source "${VENV_DIR}/Scripts/activate"
    elif [[ -f "${VENV_DIR}/bin/activate" ]]; then
        # shellcheck source=/dev/null
        source "${VENV_DIR}/bin/activate"
    else
        echo "Activation script not found in ${VENV_DIR}; activate manually."
    fi
fi

# ensure pip from the active environment is used
python -m pip install --upgrade pip
if [[ -f "${REQ_FILE}" ]]; then
    python -m pip install -r "${REQ_FILE}"
else
    echo "No ${REQ_FILE} found; skipping requirements install."
fi

echo "Done. To activate this environment in your current shell run:"
echo "  source ${VENV_DIR}/Scripts/activate    # Git Bash on Windows"
echo "Current VIRTUAL_ENV=${VIRTUAL_ENV-}"