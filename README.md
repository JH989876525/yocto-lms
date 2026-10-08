# yocto-lms — Local Mirror Server for Yocto

[繁體中文](doc/README_zh_tw.md)

Shared `DL_DIR` / `SSTATE_DIR` for the Yocto builds on this machine: one
downloads + sstate-cache set per release, a single shared `git2/` mirror
directory, and a tool to prune stale sstate objects.

`lms` is a shell function (`lms.sh`) that selects a release and exports
`DL_DIR` / `SSTATE_DIR`; it is meant for `kas-container` builds.

## Layout

```
<lms>/                      the directory containing this README
├── lms.sh                  `lms` and `kas-container` shell functions
├── tools/
│   └── sstate-prune.py     sstate pruning utility
├── git2/                   shared bitbake git mirrors
├── scarthgap/
│   ├── downloads/          git2 -> ../git2
│   ├── sstate-cache/
│   └── git2 -> ../git2
├── wrynose/                same as scarthgap/
├── sstate-prune.list       prune candidates (generated, git-ignored)
└── doc/                    README_zh_tw.md
```

`.gitignore` excludes the per-release directories and `git2/` (cache data) and
the generated `*.list`.

## Prerequisites

- bash, python3
- `kas-container` (only for container builds)
- Disk space: the caches are large; `lms status` shows usage and free space.

## Quick start

```bash
echo 'source <lms>/lms.sh' >> ~/.bashrc    # then open a new shell

lms 6            # select wrynose (5 = scarthgap); creates and exports DL_DIR and SSTATE_DIR
lms status       # sizes of the selected release and free disk space
kas-container build ...                     # build as usual
```

`kas-container` forwards `DL_DIR` and `SSTATE_DIR` into the container.

Configuration (environment variables):

| Variable | Default | Purpose |
|---|---|---|
| `LMS_HOME` | directory of `lms.sh` | root of the cache layout |
| `LMS_STAMPS_GLOB` | `/mnt/2026/*/build*/tmp*/stamps` | where `prune` looks for build stamps |
| `LMS_STAMPS` | auto-detected | colon-separated stamps dirs; overrides the glob |

## Workflow

### 1. Select a release

```bash
lms 5            # scarthgap
lms 6            # wrynose
```

### 2. Prune sstate-cache

An sstate object is kept if any of these is true:

1. its hash is referenced by the stamps of a current build,
2. it was accessed within `--days` (default 14),
3. it is among the newest `--keep-newest` (default 5) of its recipe/arch/task.

Everything else is a candidate. `prune` runs on the host and auto-detects the
stamps of every build matching `LMS_STAMPS_GLOB`.

| Option | Meaning |
|---|---|
| `--apply` | actually delete (default is dry-run) |
| `--days N` | keep objects accessed within N days |
| `--keep-newest N` | keep the newest N per recipe/arch/task |
| `--min-free GiB` | do nothing while there is enough free space |

```bash
lms prune                              # dry-run, writes <lms>/sstate-prune.list
lms prune --days 30 --keep-newest 10   # more conservative dry-run
lms prune --min-free 500               # only prune when free space is below 500 GiB
lms prune --apply                      # delete the candidates
lms prune --days 7 --min-free 300 --apply
LMS_STAMPS=/work/a/build/tmp/stamps:/work/b/build/tmp/stamps lms prune   # explicit stamps dirs
```

Always review `sstate-prune.list` before `--apply`. `prune` only handles
sstate; downloads are not pruned automatically.

### 3. Add a release

```bash
mkdir -p <lms>/<rel>/{downloads,sstate-cache}
ln -s ../git2 <lms>/<rel>/downloads/git2
ln -s ../git2 <lms>/<rel>/git2
```

Then add the release to the `case` in `lms.sh`.

## Shared git2/

`git2/` (bitbake's bare git mirrors, the bulk of downloads) is shared by all
releases through relative symlinks; everything else under `downloads/` stays
per release.

- **kas-container** only mounts `DL_DIR` (as `/downloads`), so the link resolves
  to `/git2` in the container. The `kas-container` function in `lms.sh` adds
  `-v <lms>/git2:/git2`; calling `/usr/bin/kas-container` directly (scripts,
  cron) bypasses it and the link dangles.
- **Rollback**: `rm <rel>/downloads/git2 && cp -a <lms>/git2 <rel>/downloads/git2`
- `<rel>/downloads/git2.old` are leftovers of the one-time merge; delete them
  once builds are verified.
