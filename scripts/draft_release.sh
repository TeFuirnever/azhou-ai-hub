#!/usr/bin/env bash
set -euo pipefail

tag="$1"
shift
ref="refs/tags/$tag"
if [[ -z "$tag" || "$tag" == -* || ! "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]] || ! git check-ref-format "$ref"; then
  echo "invalid release tag or verified commit SHA" >&2
  exit 2
fi

# Git advertises both the tag object and the peeled target of annotated tags.
# Only exit 2 from ls-remote with no output means the exact ref is absent.
tag_commit() {
  local refs status sha name direct="" peeled=""
  if refs="$(git ls-remote --exit-code "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY.git" "$ref" "$ref^{}")"; then
    while read -r sha name; do
      [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || return 1
      case "$name" in
        "$ref") [[ -z "$direct" ]] || return 1; direct="$sha" ;;
        "$ref^{}") [[ -z "$peeled" ]] || return 1; peeled="$sha" ;;
        *) return 1 ;;
      esac
    done <<< "$refs"
    if [[ -n "$direct" ]]; then
      printf '%s\n' "${peeled:-$direct}"
      return
    fi
  else
    status=$?
    if [[ "$status" == 2 && -z "$refs" ]]; then
      return 0
    fi
  fi
  printf 'unable to resolve exact remote tag %s\n' "$tag" >&2
  return 1
}

verify_commit() {
  if [[ -n "$1" && "$1" != "$GITHUB_SHA" ]]; then
    printf 'tag %s points to %s, not verified commit %s\n' "$tag" "$1" "$GITHUB_SHA" >&2
    return 1
  fi
}

before="$(tag_commit)"
verify_commit "$before"
if [[ -n "$before" ]]; then
  set -- --verify-tag "$@"
fi
gh release create "$tag" --repo "$GITHUB_REPOSITORY" --draft --target "$GITHUB_SHA" "$@"

# GitHub does not atomically bind creating a draft to a tag's current target.
# Catch a concurrent change before reporting success; never move or delete it.
if ! after="$(tag_commit)" || ! verify_commit "$after" || [[ -n "$before" && -z "$after" ]]; then
  echo "draft may remain unpublished; do not publish it until the tag is verified" >&2
  exit 1
fi
