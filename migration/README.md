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
