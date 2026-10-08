#!/bin/bash
# Install lms: prepare the directory layout and hook lms.sh into ~/.bashrc.
# Safe to run more than once. Never deletes or moves cache data.
#
# Usage: ./install.sh [release ...]      (default: scarthgap wrynose)

set -e
LMS_HOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASES=("$@")
[ ${#RELEASES[@]} -gt 0 ] || RELEASES=(scarthgap wrynose)
BASHRC="${HOME}/.bashrc"
BEGIN="# >>> lms >>>"
END="# <<< lms <<<"

for tool in python3 git; do
    command -v "$tool" >/dev/null || { echo "error: $tool is required"; exit 1; }
done
command -v kas-container >/dev/null || echo "warning: kas-container not found (only needed for container builds)"

# layout: <rel>/{downloads,sstate-cache} and the shared git2/
mkdir -p "${LMS_HOME}/git2"
for r in "${RELEASES[@]}"; do
    mkdir -p "${LMS_HOME}/${r}/downloads" "${LMS_HOME}/${r}/sstate-cache"
    # relative links so they resolve on the host and inside kas-container (/downloads/../git2)
    if [ -d "${LMS_HOME}/${r}/downloads/git2" ] && [ ! -L "${LMS_HOME}/${r}/downloads/git2" ]; then
        echo "note: ${r}/downloads/git2 is a real directory; to share it run: ${LMS_HOME}/tools/git2-share.py"
    else
        [ -e "${LMS_HOME}/${r}/downloads/git2" ] || ln -s ../git2 "${LMS_HOME}/${r}/downloads/git2"
        [ -e "${LMS_HOME}/${r}/git2" ] || ln -s ../git2 "${LMS_HOME}/${r}/git2"
    fi
done

# ~/.bashrc hook
touch "$BASHRC"
if grep -qF "$BEGIN" "$BASHRC"; then
    echo "~/.bashrc already has the lms block, left unchanged"
elif grep -qE '^[^#]*source[[:space:]]+[^ ]*/lms\.sh' "$BASHRC"; then
    echo "~/.bashrc already sources an lms.sh, left unchanged"
else
    if grep -qE '^function lms\(\)|^lms\(\)' "$BASHRC"; then
        echo "warning: ~/.bashrc defines its own lms() function; remove it, it would override this one"
    fi
    printf '\n%s\n[ -f "%s/lms.sh" ] && source "%s/lms.sh"\n%s\n' \
        "$BEGIN" "$LMS_HOME" "$LMS_HOME" "$END" >> "$BASHRC"
    echo "added the lms block to ~/.bashrc"
fi

echo "done. Open a new shell (or: source ~/.bashrc), then try: lms 6 && lms status"
