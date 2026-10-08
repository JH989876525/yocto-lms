#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
#
# Prune a Yocto sstate cache.
#
# An sstate object (tarball + its .siginfo, identified by hash) is KEPT if any
# of these is true:
#   1. its hash is referenced by the stamps of a current build (--stamps-dir)
#   2. it was accessed/modified within the last --days days
#   3. it is one of the newest --keep-newest objects of its
#      (recipe, pkgarch, sstate arch, task) group
# Everything else is a removal candidate.
#
# Default is dry-run: nothing is deleted, the candidate list is written to
# --list. Pass --apply to really delete.
#
# With --min-free GiB the script does nothing while the filesystem holding the
# cache still has at least that much free space.
#
# Part of /mnt/2025/lms (sstate-cache & downloads management). Normally run via
# the `lms` shell function (see ../README.md); runs on the host, not in kas-container.
#
# Configuration comes from the environment:
#   SSTATE_DIR  sstate cache to prune (required, or --cache-dir)
#   BUILDDIR    $BUILDDIR/tmp/stamps is used when no --stamps-dir is given
#
# Usage:
#   lms 6 && lms prune                   # dry-run
#   tools/sstate-prune.py --stamps-dir <build>/tmp/stamps [--stamps-dir ...] \
#       [--days 14] [--keep-newest 5] [--min-free 150] [--list prune.list] [--apply]

import argparse
import collections
import os
import re
import shutil
import sys
import time

HASH_RE = re.compile(r"[0-9a-f]{64}")
TASK_RE = re.compile(r"[0-9a-f]{64}_([A-Za-z0-9_]+?)\.")
SSTATE_SUFFIXES = (".tar.zst", ".tar.zst.siginfo", ".siginfo", ".tar.xz", ".tar.gz")
GIB = 1024 ** 3


def collect_used_hashes(stamps_dirs):
    used = set()
    for top in stamps_dirs:
        if not os.path.isdir(top):
            sys.exit(f"stamps dir not found: {top}")
        for _, _, files in os.walk(top):
            for name in files:
                used.update(HASH_RE.findall(name))
    return used


def group_key(name):
    # sstate:<pn>:<pkgarch>:<pv>:<pr>:<sstate arch>:<ver>:<hash>_<task>.tar.zst
    parts = name.split(":")
    task = TASK_RE.search(name)
    if len(parts) < 8 or not task:
        return None
    return (parts[1], parts[2], parts[5], task.group(1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache-dir", default=os.environ.get("SSTATE_DIR"),
                    help="default: $SSTATE_DIR")
    ap.add_argument("--stamps-dir", action="append", default=[],
                    help="build tmp/stamps dir; may be repeated (default: $BUILDDIR/tmp/stamps)")
    ap.add_argument("--days", type=int, default=14,
                    help="keep objects accessed within this many days (default 14)")
    ap.add_argument("--keep-newest", type=int, default=5,
                    help="per (recipe, arch, task) keep this many newest unused objects (default 5)")
    ap.add_argument("--min-free", type=float, default=0,
                    help="GiB; do nothing while free space on the cache filesystem is >= this")
    ap.add_argument("--list", default="sstate-prune.list",
                    help="where to write the candidate list")
    ap.add_argument("--apply", action="store_true", help="really delete (default: dry-run)")
    args = ap.parse_args()

    if not args.cache_dir:
        sys.exit("SSTATE_DIR is not set and --cache-dir was not given")
    if not args.stamps_dir and os.environ.get("BUILDDIR"):
        args.stamps_dir = [os.path.join(os.environ["BUILDDIR"], "tmp", "stamps")]
    if not args.stamps_dir:
        sys.exit("no stamps dir: set BUILDDIR or pass --stamps-dir for every build "
                 "that still needs this cache, otherwise they are protected only by age")
    if not os.path.isdir(args.cache_dir):
        sys.exit(f"cache dir not found: {args.cache_dir}")

    free = shutil.disk_usage(args.cache_dir).free / GIB
    print(f"free space on cache fs  : {free:.1f} GiB")
    if args.min_free and free >= args.min_free:
        print(f"free space >= --min-free {args.min_free:g} GiB, nothing to do")
        return

    used = collect_used_hashes(args.stamps_dir)
    print(f"hashes referenced by current builds: {len(used)}")
    if not used:
        sys.exit("no hashes found in stamps dirs; refusing to continue")

    cutoff = time.time() - args.days * 86400
    total_size = 0
    kept_used = kept_recent = 0
    # group -> hash -> [newest time, size, [paths]]  (unused, not recent objects only)
    groups = collections.defaultdict(dict)

    for root, _, files in os.walk(args.cache_dir):
        for name in files:
            if not name.endswith(SSTATE_SUFFIXES):
                continue
            path = os.path.join(root, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            total_size += st.st_size
            m = HASH_RE.search(name)
            if not m:
                continue
            h = m.group(0)
            if h in used:
                kept_used += 1
                continue
            t = max(st.st_atime, st.st_mtime)
            key = group_key(name)
            if key is None:
                # unknown naming: fall back to age only
                key = ("?", "?", "?", h)
            ent = groups[key].setdefault(h, [0.0, 0, []])
            ent[0] = max(ent[0], t)
            ent[1] += st.st_size
            ent[2].append(path)

    cand = []
    cand_size = 0
    kept_newest = 0
    for key, objs in groups.items():
        # newest first; the first --keep-newest are protected
        ordered = sorted(objs.values(), key=lambda e: e[0], reverse=True)
        for i, (t, size, paths) in enumerate(ordered):
            if i < args.keep_newest:
                kept_newest += len(paths)
            elif t >= cutoff:
                kept_recent += len(paths)
            else:
                cand.extend(paths)
                cand_size += size

    cand.sort()
    with open(args.list, "w") as f:
        f.write("\n".join(cand) + ("\n" if cand else ""))

    print(f"total sstate size       : {total_size / GIB:.1f} GiB")
    print(f"kept (used by builds)   : {kept_used}")
    print(f"kept (newest {args.keep_newest} per group): {kept_newest}")
    print(f"kept (accessed < {args.days}d)  : {kept_recent}")
    print(f"prune candidates        : {len(cand)} files, {cand_size / GIB:.1f} GiB")
    print(f"candidate list          : {args.list}")

    if not args.apply:
        print("dry-run: nothing deleted. Review the list, then re-run with --apply.")
        return

    removed = 0
    for path in cand:
        try:
            os.remove(path)
            removed += 1
        except OSError as e:
            print(f"failed: {path}: {e}", file=sys.stderr)
    print(f"deleted {removed} files")


if __name__ == "__main__":
    main()
