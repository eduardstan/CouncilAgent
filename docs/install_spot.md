# Installing SPOT, MCMAS, and NuSMV for the W1 verification spine

> **Status (2026-04-29):** SPOT 2.15.1 is verified working from source on
> Ubuntu 24.04 (this document was written and tested on that system). MCMAS
> access is currently blocked — see [ADR 0003](../specs/adrs/0003-mcmas-access-deferred.md).
> NuSMV is available but not via apt; download from <https://nusmv.fbk.eu>.

The `[verify]` extra of `councilagent` enables hardware-accelerated LTL_f
monitoring via the **SPOT** library. SPOT is a C++17 toolkit with Python
bindings written by the LRDE/EPITA group; **it is not a pip package**.
Without SPOT installed, `make_monitor()` falls back to the pure-Python
`ProgressionMonitor`, so SPOT is a performance optimisation. The no-extras
path is always functional.

## Critical: do NOT `pip install spot`

The PyPI package named `spot` is **not** the SPOT model checker — it is an
unrelated DotCloud / MongoDB / Redis service helper. If you `pip install spot`
your tests will silently use the wrong package, then `import spot` will
expose a `Dotcloud / Mongodb / ...` namespace, and the `is_spot_available()`
detector will report True while behaviours fail mysteriously.

Always use either the apt-repository path or the source-build path documented
below.

## SPOT — required for `[verify]` extra

### Path A: apt repository (recommended if you have sudo)

The LRE/EPITA group at EPITA hosts a Debian apt repository for SPOT. As of
2026-04-29 it tracks SPOT 2.15.1 (released 2026-04-25). The repo is built for
Debian Trixie (stable) — Ubuntu 22.04 / 24.04 are compatible.

```bash
# 1. Add the LRE-EPITA GPG key
sudo wget -q -O /etc/apt/keyrings/lre-epita.gpg \
  https://www.lre.epita.fr/repo/debian.gpg

# 2. Add the apt source
echo "deb [signed-by=/etc/apt/keyrings/lre-epita.gpg] http://www.lre.epita.fr/repo/debian/ stable/" \
  | sudo tee /etc/apt/sources.list.d/lre-epita.list

# 3. Install (any subset of these)
sudo apt-get update
sudo apt-get install spot libspot-dev spot-doc python3-spot

# 4. Verify
python3 -c "import spot; print(spot.version())"
# Expected: 2.15.1 (or later)
```

GPG fingerprint (per the official site, valid until 2032):
`209B 7362 CFD6 FECF B41D 717F 03D9 9E74 44F2 A84A`

For the development branch (unstable), replace `stable/` with `unstable/`.

### Path B: source build (no sudo required) — **VERIFIED 2026-04-29**

This path was used today to install SPOT 2.15.1 into `~/.local` and was
verified by running our SPOT-gated tests successfully (13 of 13 passed).

#### Prerequisites

```bash
sudo apt install build-essential libpython3-dev
g++ --version    # must be 10.0 or later for C++20
```

#### Build steps

```bash
# 1. Download the latest tarball (check https://spot.lre.epita.fr for newer)
mkdir -p /tmp/spot-build && cd /tmp/spot-build
curl -LO https://www.lre.epita.fr/dload/spot/spot-2.15.1.tar.gz
tar xzf spot-2.15.1.tar.gz
cd spot-2.15.1/

# 2. Configure — point at the project's venv Python so `import spot` works in
# the project. Replace the .venv path below with yours.
PROJECT_VENV=/home/USER/Dropbox/Projects/CouncilAgent/.venv
PYTHON=$PROJECT_VENV/bin/python3 ./configure \
  --prefix=$HOME/.local \
  --with-pythondir=$PROJECT_VENV/lib/python3.12/site-packages

# 3. Build (5–15 minutes on a modern laptop; uses all CPU cores)
make -j$(nproc)

# 4. Install (binaries to ~/.local/bin, libraries to ~/.local/lib,
# Python module to your project venv)
make install

# 5. Add ~/.local/bin to PATH for the CLI tools (optional)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

# 6. Verify
uv run python -c "import spot; print(spot.version())"
# Expected: 2.15.1
```

**Why `--with-pythondir=$PROJECT_VENV/...`?** SPOT's `configure` defaults to
the system or conda Python — its bindings end up where your project venv
cannot see them. Pointing at the project venv's `site-packages` puts the
bindings exactly where `uv run python` finds them.

#### After install

Run the SPOT-gated tests:

```bash
uv run pytest tests/symbolic/verify/test_spot_backend.py -v
```

Tests previously skipped (`@skipif(not is_spot_available())`) should now run
and pass.

## MCMAS — verified install (see ADR 0004)

MCMAS 1.3.0 (Linux x86_64, 2018-07-10) is hosted at
<https://sail.doc.ic.ac.uk/software/mcmas/>. The download is gated by an
HTTP `Referer` check; below are two install paths.

> **Status (2026-04-30):** Verified installed and working today on Ubuntu
> 24.04. Both the W1 acceptance test and the T3 counterexample test
> (gated by `RUN_INTEGRATION=1`) pass. See
> [ADR 0004](../specs/adrs/0004-mcmas-resolved.md) for the full decision
> record (this supersedes the earlier ADR 0003 "deferred" framing).

### Path A: form-tracked download (recommended for academic citation)

The maintainers' download form at
<https://www.doc.ic.ac.uk/download/?package=mcmas-linux64> records your
institution + email so the project can cite usage in their research output.
Recommended for your first install, because it credits the maintainers.

1. Open the URL in a browser.
2. Fill in name, institution, email; submit.
3. Save the resulting `mcmas-linux64-download.tgz`.
4. Continue with the extract / install steps in Path B.

### Path B: direct URL (suitable for automated CI / scripted install)

The form's `downloadurl` hidden field exposes the same tarball at a stable
direct URL. The Apache server requires a `Referer` header pointing at the
project page; without it the server returns "No web referer given".

```bash
# 1. Download the linux64 tarball (827 KB; Last-Modified 2018-07-10)
mkdir -p /tmp/mcmas-install && cd /tmp/mcmas-install
curl -L -H "Referer: https://sail.doc.ic.ac.uk/software/mcmas/" \
  -o mcmas-linux64.tgz \
  "https://sail.doc.ic.ac.uk/software/mcmas/mcmas-linux64-download.tgz"

# 2. Extract — the tarball contains a single ELF executable named
# `mcmas-linux64-1.3.0` (no surrounding directory)
tar xzf mcmas-linux64.tgz

# 3. Install to ~/.local/bin/mcmas (no sudo required)
mkdir -p ~/.local/bin
cp mcmas-linux64-1.3.0 ~/.local/bin/mcmas
chmod +x ~/.local/bin/mcmas

# 4. Ensure ~/.local/bin is on PATH (most distros do this for login shells;
# add to ~/.bashrc / ~/.zshrc if needed)
export PATH="$HOME/.local/bin:$PATH"

# 5. Verify
mcmas    # prints the v1.3.0 banner and usage
which mcmas   # → /home/<you>/.local/bin/mcmas
```

### Run the W1 acceptance + T3 counterexample tests

```bash
RUN_INTEGRATION=1 uv run pytest tests/integration/test_mcmas_offline.py \
                                tests/integration/test_mcmas_t3_counterexample.py -v
```

Expected output: 3 passed (`EventuallyDecide` and `RefutationReachable`
verified TRUE on the W1 4-agent / 4-round trace; `ProvenanceCompleteness`
verified FALSE on the T3 counterexample trace; sanity-check verified TRUE
on a non-empty-evidence variant).

### Manual (highly recommended)

The MCMAS v1.2.2 user manual at
<https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf> documents the ISPL
syntax (§3.2), the reserved keywords (§3.2.3), and the BNF grammar (§3.2.4).
Our ISPL emitter (`council/symbolic/verify/ispl.py`) is grounded in this
manual; future emitter changes should cite the relevant manual section in
their commit message.

### Eclipse plug-in (optional, not used by this project)

The page also offers `org.mcmas.ui_1.2.2.jar` for the MCMAS Eclipse GUI.
We do not use it — the headless `mcmas` CLI is sufficient for batch
verification and integrates with our pytest suite.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `mcmas: command not found` | `~/.local/bin` not on PATH | `export PATH="$HOME/.local/bin:$PATH"` and add to your shell rc |
| `mcmas: error while loading shared libraries: ...` | Missing 32-bit / arch-mismatch on a non-x86_64 host | Use a different MCMAS variant (linux32 or build from source via `mcmas@imperial.ac.uk`) |
| Download returns the form HTML instead of a tarball | No `Referer` header | Use the curl command above with the `-H Referer:` flag |
| `RUN_INTEGRATION=1` test still skips | `which mcmas` returns nothing | Check the install steps; the test gate is `mcmas` on PATH AND `RUN_INTEGRATION=1` |

## NuSMV — interim CTL path (optional)

For the CTL fragment (which covers W1's `EventuallyDecide` and
`RefutationReachable` acceptance properties) NuSMV is a workable interim
substitute. NuSMV does **not** support CTLK/ATL (those need MCMAS); use it
only for plain-CTL checks.

NuSMV 2.7.1 is the latest release (2026-04-29) and is available at
<https://nusmv.fbk.eu>. The project is alive and maintained at FBK's Tools
group.

```bash
# Visit https://nusmv.fbk.eu and follow "Downloads"
#   - Source code: free, requires academic-use form
#   - Pre-compiled binaries: free for Linux x86_64, macOS

# After install, check it's on PATH:
NuSMV -version
```

**Licence:** free for academic / educational research. Commercial use needs a
separate agreement with FBK.

NuSMV input is generated by [`council/symbolic/verify/smv.py`](../council/symbolic/verify/smv.py) — see
the structural tests in `tests/symbolic/verify/test_smv.py` for example
output.

## CI / publishing

The published package on PyPI does not depend on SPOT, MCMAS, or NuSMV. CI
runs the no-extras test path (which uses `ProgressionMonitor`) by default; a
separate CI matrix job installs SPOT and runs the SPOT-gated tests for
regression coverage. MCMAS / NuSMV integration tests are gated by
`RUN_INTEGRATION=1` and run only on systems where the binary is present.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'spot'` | SPOT not installed, or installed for a different Python | Reinstall with `--with-pythondir=$VENV/lib/python3.X/site-packages` |
| `import spot` succeeds but `spot.version()` looks like `Dotcloud / Mongodb` | You did `pip install spot` and got the wrong PyPI package | `uv pip uninstall spot`; then follow Path A or Path B above |
| `import buddy` fails | SPOT installed but BuDDy bindings missing | The source build installs both; `apt install python3-spot` should pull `python3-buddy` as a dependency |
| `make: *** No rule to make target` during source build | C++20 compiler missing or too old | `sudo apt install build-essential` then `g++ --version` ≥ 10 |
| `RUN_INTEGRATION=1` test skips silently | `mcmas` not on PATH | Either install MCMAS (see ADR 0003) or run the NuSMV-substitute path manually |

## Why apt-repo (Path A) is generally preferred over source build (Path B)

- Path A: ~30 seconds of work, system-wide install, automatic updates via apt
- Path B: ~10 minutes of work, user-space install, manual update each release

Use Path B when you don't have sudo (e.g., shared servers) or when you need a
specific SPOT version that's no longer in the apt repo.
