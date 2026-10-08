# lms — sstate-cache & downloads management

Shared `DL_DIR` / `SSTATE_DIR` for the Yocto builds on this machine.

```
/mnt/2025/lms/
├── lms.sh                  # `lms` shell function, sourced from ~/.bashrc
├── tools/sstate-prune.py   # sstate pruning utility
├── scarthgap/{downloads,sstate-cache}
└── wrynose/{downloads,sstate-cache}
```

## Install
```bash
./install.sh [release ...]     # default: scarthgap wrynose; safe to re-run
```
Creates `<rel>/{downloads,sstate-cache}` and the shared `git2/` links, and adds a
block to `~/.bashrc` that sources `lms.sh` (skipped if `~/.bashrc` already sources
an `lms.sh`). It never moves or deletes cache data. Open a new shell afterwards.
`LMS_HOME` is derived from the location of `lms.sh`; `LMS_STAMPS_GLOB` (default
`/mnt/2026/*/build*/tmp*/stamps`) tells `prune` where to find the builds' stamps.

## Usage
```bash
lms 6            # select wrynose (5 = scarthgap); exports DL_DIR and SSTATE_DIR
lms status       # sizes of the selected release and free disk space
lms prune        # dry-run: writes /mnt/2025/lms/sstate-prune.list, deletes nothing
lms prune --apply
```
Build as usual after selecting a release, e.g. `kas-container build ...`
(kas-container forwards `DL_DIR` and `SSTATE_DIR` into the container).

## sstate prune rule
An sstate object is kept if any of these is true:
1. its hash is referenced by the stamps of a current build,
2. it was accessed within `--days` (default 14),
3. it is among the newest `--keep-newest` (default 5) of its recipe/arch/task.

Everything else is a candidate. `prune` runs on the host and auto-detects the
stamps of every build under `/mnt/2026/*/build*/tmp*/stamps`; set `LMS_STAMPS`
(colon separated) to override. Other options: `--min-free GiB` (do nothing while
there is enough free space).

Always review `sstate-prune.list` before `--apply`.

## Shared git2/
`git2/` (bitbake's bare git mirrors, the bulk of downloads) is shared by all releases:

```
/mnt/2025/lms/git2/                      real, shared
/mnt/2025/lms/<rel>/downloads/git2  ->  ../git2
/mnt/2025/lms/<rel>/git2            ->  ../git2   (makes the link resolve on the host)
```
Everything else under `downloads/` stays per release, because some release-specific
tarballs share a file name but differ in content (e.g. Qualcomm camx / chicdk / video-ctrl).

- **kas-container**: it only mounts `DL_DIR` (as `/downloads`) and `SSTATE_DIR`, so
  the relative link resolves to `/git2` inside the container. The `kas-container`
  shell function in `lms.sh` adds `-v /mnt/2025/lms/git2:/git2`. Calling
  `/usr/bin/kas-container` directly (scripts, cron) bypasses it and the link dangles.
- **Merge**: repos in both releases were merged into one; the other release's refs
  live under `refs/lms/<release>/*` so no object is ever garbage collected.
- **Tool**: `tools/git2-share.py` (dry-run by default; `--apply`, `--purge-old`).
  `--apply` keeps the merged-away copies in `<rel>/downloads/git2.old` until
  `--purge-old` removes them.
- **Rollback**: replace the symlink with a copy (`rm downloads/git2 && cp -a git2 downloads/git2`).

Verified: wrynose `bitbake --runall=fetch qcom-multimedia-proprietary-image` + unpack of
`opencv`/`linux-qcom` in kas-container; scarthgap bitbake 2.8.1 offline fetch and unpack of a
commit that only existed in scarthgap's old copy.

`prune` only handles sstate. Downloads are not pruned automatically.
