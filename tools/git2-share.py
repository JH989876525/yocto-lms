#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
#
# Share the bitbake git2/ mirror directory between releases.
#
# Before:  <lms>/<rel>/downloads/git2/<repo>          (one real copy per release)
# After:   <lms>/git2/<repo>                           (shared, real)
#          <lms>/<rel>/downloads/git2 -> ../git2       (relative symlink)
#          <lms>/<rel>/git2           -> ../git2       (so the link also resolves on the host)
#
# Inside kas-container DL_DIR is mounted as /downloads, so the link resolves to
# /git2: the container must mount <lms>/git2 there (the `kas-container` wrapper
# in lms.sh does this).
#
# Repos present in only one release are moved (rename, instant). For repos present
# in several releases the largest copy is moved and the others' refs are fetched
# into it under refs/lms/<rel>/* so every object stays reachable (never pruned).
# The merged-away copies are kept in <rel>/downloads/git2.old until --purge-old.
#
# Default is dry-run. Usage:
#   tools/git2-share.py                # plan only
#   tools/git2-share.py --apply        # merge (keeps git2.old)
#   tools/git2-share.py --purge-old    # delete git2.old after you verified builds

import argparse
import os
import shutil
import subprocess
import sys

GIB = 1024 ** 3


def du(path):
    total = 0
    for dp, _, fn in os.walk(path):
        for f in fn:
            try:
                total += os.lstat(os.path.join(dp, f)).st_size
            except OSError:
                pass
    return total


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)


def busy(lms):
    out = subprocess.run(["pgrep", "-af", "docker run|bitbake|kas-container"],
                         capture_output=True, text=True).stdout
    return [l for l in out.splitlines()
            if lms in l and "git2-share" not in l and "pgrep" not in l]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lms", default=os.environ.get("LMS_HOME", "/mnt/2025/lms"))
    ap.add_argument("--releases", nargs="+", default=["scarthgap", "wrynose"])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--purge-old", action="store_true")
    args = ap.parse_args()

    lms = args.lms
    shared = os.path.join(lms, "git2")

    if args.purge_old:
        for r in args.releases:
            old = os.path.join(lms, r, "downloads", "git2.old")
            if os.path.isdir(old):
                print(f"removing {old} ({du(old) / GIB:.1f} GiB)")
                shutil.rmtree(old)
        return

    src = {}
    for r in args.releases:
        d = os.path.join(lms, r, "downloads", "git2")
        if os.path.islink(d):
            sys.exit(f"{d} is already a symlink; nothing to do for {r}")
        if not os.path.isdir(d):
            sys.exit(f"{d} not found")
        src[r] = {e.name: e.path for e in os.scandir(d) if e.is_dir(follow_symlinks=False)}
    if os.path.exists(shared) and os.listdir(shared):
        sys.exit(f"{shared} already exists and is not empty")

    names = sorted(set().union(*[set(v) for v in src.values()]))
    plan = []  # (name, base_rel, [other_rels])
    saved = 0
    moved_only = 0
    for n in names:
        have = [r for r in args.releases if n in src[r]]
        if len(have) == 1:
            plan.append((n, have[0], []))
            moved_only += 1
        else:
            sizes = {r: du(src[r][n]) for r in have}
            base = max(sizes, key=sizes.get)
            others = [r for r in have if r != base]
            saved += sum(sizes[r] for r in others)  # upper bound, objects overlap
            plan.append((n, base, others))
    common = len(plan) - moved_only

    print(f"repos: {len(names)} total, {moved_only} in one release only (move), {common} common (merge)")
    print(f"upper bound of space freed after --purge-old: {saved / GIB:.1f} GiB "
          f"(real saving is lower by the objects unique to the smaller copy)")

    if not args.apply:
        print("dry-run: nothing changed. Re-run with --apply (stop all kas-container / bitbake first).")
        return

    b = busy(lms)
    if b:
        sys.exit("something still uses the lms dirs, stop it first:\n" + "\n".join(b))

    os.makedirs(shared, exist_ok=True)
    failed = []
    for i, (n, base, others) in enumerate(plan, 1):
        dst = os.path.join(shared, n)
        os.rename(src[base][n], dst)
        done = src[base][n] + ".done"  # bitbake's per-clone stamp sits next to the repo
        if os.path.exists(done):
            os.rename(done, dst + ".done")
        for r in others:
            res = git("fetch", "--quiet", "--no-tags", src[r][n],
                      f"+refs/*:refs/lms/{r}/*", cwd=dst)
            if res.returncode != 0:
                failed.append((n, r, res.stderr.strip()))
        if i % 50 == 0 or i == len(plan):
            print(f"[{i}/{len(plan)}] {n}", flush=True)

    # failed merges: the loser copy is still in git2.old, and the shared base lacks
    # its refs. Report; do NOT purge until handled.
    for r in args.releases:
        d = os.path.join(lms, r, "downloads")
        os.rename(os.path.join(d, "git2"), os.path.join(d, "git2.old"))
        os.symlink("../git2", os.path.join(d, "git2"))
        rl = os.path.join(lms, r, "git2")
        if not os.path.lexists(rl):
            os.symlink("../git2", rl)

    print(f"merged. original leftovers kept in <rel>/downloads/git2.old")
    if failed:
        print(f"{len(failed)} merge(s) FAILED (copy kept in git2.old):")
        for n, r, e in failed:
            print(f"  {r}/{n}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
