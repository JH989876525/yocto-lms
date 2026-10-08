# lms: sstate-cache & downloads management. Source this file from ~/.bashrc.
#
#   lms 5|6            select scarthgap|wrynose (exports DL_DIR, SSTATE_DIR)
#   lms status         sizes of the selected release and free disk space
#   lms prune [args]   prune sstate-cache of the selected release (dry-run unless --apply)
#
# LMS_STAMPS (colon separated) overrides the auto-detected stamps dirs used by prune;
# LMS_STAMPS_GLOB changes where they are searched.

LMS_HOME="${LMS_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
# where prune looks for the stamps of builds that still use the cache
LMS_STAMPS_GLOB="${LMS_STAMPS_GLOB:-/mnt/2026/*/build*/tmp*/stamps}"

function lms(){
    local cmd="${1}"
    case "${cmd}" in
        5|scarthgap)
            export DL_DIR="${LMS_HOME}/scarthgap/downloads"
            export SSTATE_DIR="${LMS_HOME}/scarthgap/sstate-cache"
            echo "DL_DIR=$DL_DIR"
            echo "SSTATE_DIR=$SSTATE_DIR"
            ;;
        6|wrynose)
            export DL_DIR="${LMS_HOME}/wrynose/downloads"
            export SSTATE_DIR="${LMS_HOME}/wrynose/sstate-cache"
            echo "DL_DIR=$DL_DIR"
            echo "SSTATE_DIR=$SSTATE_DIR"
            ;;
        status)
            if [ -z "${SSTATE_DIR}" ] || [ -z "${DL_DIR}" ]; then
                echo "Select a release first: lms 5|6"; return 1
            fi
            du -sh "${DL_DIR}" "${SSTATE_DIR}"
            df -h "${SSTATE_DIR}" | tail -1
            ;;
        prune)
            shift
            if [ -z "${SSTATE_DIR}" ]; then
                echo "Select a release first: lms 5|6"; return 1
            fi
            local stamps=() s
            if [ -n "${LMS_STAMPS}" ]; then
                IFS=: read -ra _lms_arr <<< "${LMS_STAMPS}"
                for s in "${_lms_arr[@]}"; do stamps+=(--stamps-dir "$s"); done
            else
                for s in ${LMS_STAMPS_GLOB}; do
                    [ -d "$s" ] && stamps+=(--stamps-dir "$s")
                done
            fi
            python3 "${LMS_HOME}/tools/sstate-prune.py" --cache-dir "${SSTATE_DIR}" \
                --list "${LMS_HOME}/sstate-prune.list" "${stamps[@]}" "$@"
            ;;
        *)
            echo "Usage: lms 5|6 | status | prune [--apply] [--days N] [--keep-newest N] [--min-free GiB]"
            echo "       5=scarthgap, 6=wrynose"
            return 1
            ;;
    esac
}

# git2/ is shared between releases: <rel>/downloads/git2 is a relative symlink to
# ../git2, which inside kas-container (DL_DIR mounted as /downloads) is /git2.
function kas-container(){
    if [ -d "${LMS_HOME}/git2" ]; then
        command kas-container --runtime-args "-v ${LMS_HOME}/git2:/git2:rw" "$@"
    else
        command kas-container "$@"
    fi
}
