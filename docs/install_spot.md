# Installing SPOT (and MCMAS, NuSMV) for the W1 verification spine

The `[verify]` extra of `councilagent` enables hardware-accelerated LTL_f
monitoring via the **SPOT** library. SPOT is a C++ toolkit with Python bindings
written by the LRDE/EPITA group; it is **not** a pip package. This document
covers installation across Linux, macOS, and from source. We do **not** support
conda installations (per project convention — the development environment uses `uv`).

> **TL;DR:** without SPOT installed, `make_monitor()` falls back to the pure-Python
> `ProgressionMonitor`. SPOT is a performance optimisation; the no-extras path is
> always functional.

## SPOT — required for `[verify]` extra

### Ubuntu / Debian (recommended for project development)

```bash
sudo apt update
sudo apt install spot python3-spot libspot-dev
```

Verify:

```bash
python3 -c "import spot; print(spot.version())"
# Expected output: e.g. 2.13.2
```

If `python3-spot` is not in your distribution's package archive, see "Source build" below.

### Arch Linux

```bash
yay -S spot
# or with paru:
paru -S spot
```

The AUR `spot` package builds Python bindings by default.

### macOS (Homebrew)

```bash
brew install spot
# Spot's Homebrew formula installs the CLI tools but the Python bindings may
# require an extra step depending on your Python interpreter:
brew install --build-from-source --HEAD spot
# or use the upstream tarball below.
```

Verify:

```bash
python3 -c "import spot"
```

If `import spot` fails after `brew install`, fall back to the source build below
or use the LRDE-provided macOS wheel (when available; check
[spot.lre.epita.fr/install.html](https://spot.lre.epita.fr/install.html)).

### Source build (any platform with a recent C++17 compiler)

```bash
# 1. Get the latest tarball from https://spot.lre.epita.fr
curl -O https://www.lrde.epita.fr/dload/spot/spot-2.13.2.tar.gz
tar xzf spot-2.13.2.tar.gz
cd spot-2.13.2/

# 2. Configure with Python bindings
./configure --prefix=$HOME/.local

# 3. Build and install (parallel for speed)
make -j$(nproc) && make install

# 4. Add to your environment
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$HOME/.local/lib/python3.12/site-packages:$PYTHONPATH"
# (adjust the python3.X version to match your interpreter)

# 5. Verify
python3 -c "import spot; print(spot.version())"
```

For permanent installation, add the `export` lines to `~/.bashrc` or `~/.zshrc`.

### Verifying the install

After installing SPOT by any method, run the project's test suite:

```bash
uv run pytest tests/symbolic/verify/test_spot_backend.py -v
```

Tests that previously skipped (`@skipif(not is_spot_available())`) should now
execute and pass.

## MCMAS — required only for offline ISPL verification (PR6)

MCMAS verifies CTLK / ATL formulae over interpreted systems. Used in
`tests/integration/test_mcmas_offline.py` (gated by `RUN_INTEGRATION=1`).

### Linux

Download the latest binary from
[mcmas.org.uk/download.html](https://mcmas.org.uk/download.html):

```bash
wget https://mcmas.org.uk/files/mcmas-linux64.tgz
tar xzf mcmas-linux64.tgz
sudo mv mcmas /usr/local/bin/
mcmas --version
```

### macOS

The maintained Linux binary works under Rosetta 2; native arm64 macOS
binaries are not currently published. Build from source by cloning
[github.com/lomuscio/mcmas](https://github.com/lomuscio/mcmas).

## NuSMV — optional, alternative to MCMAS for SMV-format verification

```bash
# Ubuntu / Debian
sudo apt install nusmv

# macOS
brew install nusmv
```

Verify:

```bash
NuSMV -version
```

## Project configuration

The `[verify]` extra in `pyproject.toml` does not pin a `spot` package because
SPOT is a system install. The extra exists to reserve the namespace and to
document the system dependency. Installing the extra is a no-op:

```bash
uv pip install -e ".[verify]"
# (Confirms project install; does not install SPOT — see above.)
```

The runtime check `is_spot_available()` is the source of truth for whether
the SPOT-backed path is active.

## Troubleshooting

- `ModuleNotFoundError: No module named 'spot'` → SPOT not installed or
  `PYTHONPATH` does not include the SPOT site-packages directory.
- `import spot` succeeds but `spot.translate(...)` raises `AttributeError` →
  SPOT version too old (we target SPOT ≥ 2.10).
- `make: *** No rule to make target` during source build → C++17 compiler
  required (`g++` ≥ 7 or `clang++` ≥ 5).

## CI / publishing

The published package on PyPI does not depend on SPOT. CI runs the no-extras
test path (which uses `ProgressionMonitor`) by default; a separate CI matrix
job installs SPOT and runs the SPOTMonitor tests for regression coverage.
