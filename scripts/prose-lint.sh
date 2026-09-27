#!/usr/bin/env bash
# Fails on em dashes and a short list of stock words in reader-facing docs.
set -u
files=(README.md CONTEXT.md CLAUDE.md)
status=0
for f in "${files[@]}"; do
  [ -f "$f" ] || continue
  if grep -n -- '—' "$f"; then echo "$f: em dash"; status=1; fi
  if grep -n -i -E '\b(seamless(ly)?|robust(ly|ness)?|leverag(e|es|ed|ing)|passionate(ly)?|blazing(ly)?)\b' "$f"; then
    echo "$f: stock word"; status=1
  fi
done
exit $status
