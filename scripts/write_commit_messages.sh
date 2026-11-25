#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MESSAGE_MAP_FILE="${ROOT_DIR}/scripts/commit_messages.tsv"

usage() {
  cat <<EOF
Usage: $(basename "$0") [print|stage]

print  Show grouped commit-message preview for current git changes.
stage  Commit each changed file using exact messages from scripts/commit_messages.tsv.

Default: print
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "${1:-}" == "help" ]]; then
  usage
  exit 0
fi

mode="${1:-print}"
if [[ "${mode}" != "print" && "${mode}" != "stage" ]]; then
  usage >&2
  exit 2
fi

cd "${ROOT_DIR}"

declare -A COMMIT_MESSAGES=()
if [[ -f "${MESSAGE_MAP_FILE}" ]]; then
  while IFS=$'\t' read -r mapped_path mapped_message; do
    [[ -z "${mapped_path}" || "${mapped_path}" == \#* ]] && continue
    [[ -z "${mapped_message:-}" ]] && continue
    COMMIT_MESSAGES["${mapped_path}"]="${mapped_message}"
  done < "${MESSAGE_MAP_FILE}"
fi

status_output="$(git status --porcelain --untracked-files=all)"
if [[ -z "${status_output}" ]]; then
  echo "No changes detected."
  exit 0
fi

declare -a paths=()
declare -a messages=()
declare -a missing=()
declare -a statuses=()

while IFS= read -r line; do
  [[ -z "${line}" ]] && continue

  status="${line:0:2}"
  path="${line:3}"

  # For renames, keep the destination path readable.
  if [[ "${path}" == *" -> "* ]]; then
    path="${path##* -> }"
  fi

  # Prefer index status, fallback to worktree status.
  short_status="${status:0:1}"
  if [[ "${short_status}" == " " ]]; then
    short_status="${status:1:1}"
  fi
  if [[ "${status}" == "??" ]]; then
    short_status="??"
  fi

  if [[ -z "${COMMIT_MESSAGES[${path}]:-}" ]]; then
    missing+=("${path}")
    continue
  fi

  paths+=("${path}")
  messages+=("${COMMIT_MESSAGES[${path}]}")
  statuses+=("${short_status}")
done <<< "${status_output}"

if (( ${#missing[@]} )); then
  echo "Missing commit messages for changed files:" >&2
  printf -- "- %s\n" "${missing[@]}" >&2
  exit 1
fi

if [[ "${mode}" == "print" ]]; then
  declare -a added=()
  declare -a modified=()
  declare -a removed=()
  declare -a other=()

  for index in "${!paths[@]}"; do
    message="${messages[$index]}"

    case "${statuses[$index]}" in
      A|??)
        added+=("${message}")
        ;;
      M)
        modified+=("${message}")
        ;;
      D)
        removed+=("${message}")
        ;;
      *)
        other+=("${message}")
        ;;
    esac
  done

  echo "chore: update project files"
  echo

  if (( ${#added[@]} )); then
    echo "Added:"
    printf -- "- %s\n" "${added[@]}"
    echo
  fi

  if (( ${#modified[@]} )); then
    echo "Modified:"
    printf -- "- %s\n" "${modified[@]}"
    echo
  fi

  if (( ${#removed[@]} )); then
    echo "Removed:"
    printf -- "- %s\n" "${removed[@]}"
    echo
  fi

  if (( ${#other[@]} )); then
    echo "Other:"
    printf -- "- %s\n" "${other[@]}"
    echo
  fi

  exit 0
fi

for index in "${!paths[@]}"; do
  path="${paths[$index]}"
  message="${messages[$index]}"

  git add -- "${path}"
  git commit -m "${message}" -- "${path}"
done
