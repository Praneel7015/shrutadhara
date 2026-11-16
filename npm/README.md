# Unpublished npm convenience launcher

This MIT-licensed private local package starts the same native Python/GTK recorder. It has no Electron/browser runtime, install hooks, automatic downloads, recording or service setup. No registry name or public availability is promised. Choose repository/registry identity before publication.

Build a reviewed wheel at the project root with `uv build`, then use `npm install --global ./npm --ignore-scripts`. Run `shruta setup-native /absolute/path/to/dist/shrutadhara-0.1.0-py3-none-any.whl`. Setup explicitly creates a user-local Python venv with system packages visible and installs the local wheel; pip may download Python dependencies. Install distribution Python venv/pip support, GTK 4/PyGObject, FFmpeg and pactl yourself first. This command never installs system packages or enables services. For an existing native install, set `SHRUTA_NATIVE_EXECUTABLE` to its absolute executable path. Do not point it to this wrapper.

Run `shruta doctor` and `shruta show`. Desktop integration is separately explicit: `shruta install-desktop`. Use `shruta shortcuts` for manual compositor bindings. Recording and AI upload require their ordinary explicit actions.

Setup requires the wheel version matching this launcher. Repeating explicit setup reinstalls that reviewed wheel in the managed runtime, including a locally rebuilt wheel with the same development version. Python dependencies may be downloaded again; the application artifact itself is never fetched automatically.

Setup uses prebuilt Python dependency wheels and bounded network retries; it does not start a compiler/toolchain build. If a matching dependency wheel is unavailable, use a supported Python/distribution package installation. Each setup subprocess has a three-minute deadline; normal recording/GUI commands do not inherit that deadline.

`npm uninstall --global shrutadhara` removes the wrapper. After stopping work, remove only the managed runtime at `${XDG_DATA_HOME:-$HOME/.local/share}/shrutadhara/npm-runtime` and any explicitly installed user desktop entry/launcher if desired. Recordings/configuration are separate and must be retained. Never remove a native package manager's installation. Node is required for this wrapper, not for native installations.
