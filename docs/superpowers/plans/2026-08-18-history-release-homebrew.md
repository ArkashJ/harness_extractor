# Harness Extractor History, Release, and Homebrew Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove private artifacts from every public Git ref, merge the reviewed release candidate, publish `v1.0.0` with verified artifacts, and publish a tested `ArkashJ/homebrew-tap` formula.

**Architecture:** Treat GitHub as authoritative before and after every external mutation. Keep the repository private while all advertised refs are rewritten with `git filter-repo --sensitive-data-removal`, GitHub Support removes cached views and internal pull-request references, stale clones are coordinated, and the reviewed candidate is merged. Verify the reporting links on merged `main`, restore public visibility, enable private vulnerability reporting, and only then release. Derive Homebrew's checksum from the downloaded release sdist rather than a local build.

**Tech Stack:** Git 2.x, `git-filter-repo` `a40bce548d2c`, GitHub CLI, GitHub Actions, Python 3.10–3.14, `uv`, Twine, Homebrew 6.0.17, Homebrew `python@3.14`.

**Spec:** `docs/superpowers/specs/2026-08-18-public-release-design.md`

## Authoritative state at plan creation

- Repository: `https://github.com/ArkashJ/harness_extractor`
- Draft PR: `https://github.com/ArkashJ/harness_extractor/pull/1`
- Audited implementation commit: `8cbd38b2a47066339231c58510cf61a6acc31c04`
- Green CI: `https://github.com/ArkashJ/harness_extractor/actions/runs/32105011071`
- Local artifacts: `harness_extractor-1.0.0-py3-none-any.whl` and `harness_extractor-1.0.0.tar.gz`
- Local audit hashes, retained only as provenance because GitHub Actions rebuilds the release:
  - wheel: `71d996e9a72d543bb02de34161452466589f94bdbcd80841e3d6f7e94fe8f697`
  - sdist: `80562d4d6d8e22adffda8eb4f68f8fbbc03517a512cd063871500814ba7c7b39`
- Remote branches:
  - `main` -> `e9f7bee57590f25a7b4b71e0340901a495fa3aa8`
  - `codex/release-readiness` -> `21fe9b3c15812d8209575cef72957073c85d167d`
  - `codex/library-cli-implementation` -> `8cbd38b2a47066339231c58510cf61a6acc31c04`
- GitHub also advertises `refs/pull/1/head` and `refs/pull/1/merge`; post-rewrite verification must include them even though GitHub owns them.
- The repository is temporarily `PRIVATE` after retained confidential content was confirmed. Before that change, the reachable graph exposed 97 distinct forbidden paths. There are currently zero forks, stars, and watchers; inventory collaborators, observable clone traffic, and stale local clones again at execution time.
- There are no tags, no `v1.0.0` release, no branch protection/rulesets, and no `ArkashJ/homebrew-tap` repository.
- Release URLs:
  - `https://github.com/ArkashJ/harness_extractor/releases/tag/v1.0.0`
  - `https://github.com/ArkashJ/harness_extractor/releases/download/v1.0.0/harness_extractor-1.0.0-py3-none-any.whl`
  - `https://github.com/ArkashJ/harness_extractor/releases/download/v1.0.0/harness_extractor-1.0.0.tar.gz`
  - `https://github.com/ArkashJ/homebrew-tap`

## Global Constraints

- Distribution and CLI name: `harness-extractor`; import name: `harness_extractor`.
- Version: `1.0.0`; release tag: `v1.0.0`.
- Python: `>=3.10`; CI: 3.10, 3.11, 3.12, 3.13, 3.14.
- Runtime dependencies: none.
- Remove `findings/**`, `synthesis/**`, `out/**`, `.claude/**`, `.superpowers/**`, `prompts/ORIGIN-*.md`, `prompts/PR-REVIEW-PROMPT.md`, and `prompts/repo-steward-SEED.md` from every Git ref.
- Keep the private backup outside the repository with mode `0600`; never upload it.
- Keep `ArkashJ/harness_extractor` private until the force-push, GitHub Support purge, cached-view/internal-PR-ref cleanup, stale-clone coordination, and authoritative readbacks are complete.
- Do not merge until the Support and clone-cleanup gates pass. Do not tag or release until merged `main` has consistent private-reporting links, the repository is explicitly restored to `PUBLIC`, that visibility is read back, and private vulnerability reporting is enabled and read back.
- Obtain fresh confirmation immediately before the history force-push and again immediately before merging PR #1. A previous approval does not satisfy either gate.
- Use the release workflow's downloaded sdist checksum in the Homebrew formula. Never reuse the local audit checksum.
- Do not publish to PyPI and do not add bottles, telemetry, release bots, or auto-update tooling for `1.0.0`.

```text
reviewed candidate + green CI
             |
             v
 private Git bundle backup
             |
             v
 disposable mirror -> filter -> local graph/content checks
             |
             v
 FRESH FORCE-PUSH CONFIRMATION
             |
             v
 force-with-lease three rewritten branches
             |
             v
 fresh GitHub all-ref clone -> zero forbidden paths -> CI green
             |
             v
 GitHub Support cache/internal-PR cleanup -> stale clones coordinated
             |
             v
 FRESH MERGE CONFIRMATION -> merge reviewed PR -> read back main
             |
             v
 verify reporting links -> restore PUBLIC -> enable private reporting
             |
             v
 tag v1.0.0 -> Release workflow -> wheel + sdist readback
             |
             v
 observed release sdist SHA-256 -> formula -> audit/install/test
             |
             v
 create ArkashJ/homebrew-tap -> public install smoke
```

---

### Task 1: Freeze the reviewed release candidate

**Files:**
- No repository file changes.

**Interfaces:**
- Consumes: reviewed PR #1, the branch containing `8cbd38b2a47066339231c58510cf61a6acc31c04`, and successful GitHub Actions.
- Produces: an exact PR-head SHA in `/private/tmp/harness-extractor-release-candidate.sha` and an immutable remote-ref snapshot.

- [ ] **Step 1: Confirm local and GitHub identity**

Run outside the sandbox:

```bash
git fetch --all --prune
gh repo view ArkashJ/harness_extractor --json nameWithOwner,url
git status --short
git branch --show-current
git rev-parse HEAD
git merge-base --is-ancestor 8cbd38b2a47066339231c58510cf61a6acc31c04 HEAD
git filter-repo --version
git filter-repo -h | grep -F -- '--sensitive-data-removal'
```

Expected: repository `ArkashJ/harness_extractor`, empty status, the release-candidate branch, a zero exit from `merge-base`, and a `git-filter-repo` version exposing the sensitive-data-removal flag (version 2.47 or newer).

- [ ] **Step 2: Put the reviewed candidate on PR #1's head branch**

```bash
gh pr view 1 --repo ArkashJ/harness_extractor --json url,isDraft,headRefName,headRefOid,baseRefName,mergeable,mergeStateStatus
git push origin HEAD:refs/heads/codex/release-readiness
gh pr view 1 --repo ArkashJ/harness_extractor --json headRefName,headRefOid,mergeable,mergeStateStatus
```

Expected: PR #1 remains based on `main`, its head is `codex/release-readiness`, and `headRefOid` equals local `HEAD`. Abort if the push is not a fast-forward.

- [ ] **Step 3: Require CI success for the exact PR-head SHA**

Run outside the sandbox as one shell block:

```bash
candidate_sha=$(gh pr view 1 --repo ArkashJ/harness_extractor --json headRefOid --jq .headRefOid)
printf '%s\n' "$candidate_sha" > /private/tmp/harness-extractor-release-candidate.sha
ci_run_id=""
for attempt in {1..30}; do
  ci_run_id=$(gh run list --repo ArkashJ/harness_extractor --workflow CI --commit "$candidate_sha" --json databaseId,headSha --jq ".[] | select(.headSha == \"$candidate_sha\") | .databaseId" | head -n 1)
  test -z "$ci_run_id" || break
  sleep 10
done
test -n "$ci_run_id"
gh run watch "$ci_run_id" --repo ArkashJ/harness_extractor --exit-status
test "$(gh run view "$ci_run_id" --repo ArkashJ/harness_extractor --json headSha --jq .headSha)" = "$candidate_sha"
test "$(gh run view "$ci_run_id" --repo ArkashJ/harness_extractor --json conclusion --jq .conclusion)" = success
if gh pr view 1 --repo ArkashJ/harness_extractor --json isDraft --jq .isDraft | grep -qx true; then gh pr ready 1 --repo ArkashJ/harness_extractor; fi
gh pr checks 1 --repo ArkashJ/harness_extractor
gh pr view 1 --repo ArkashJ/harness_extractor --json isDraft,headRefOid,mergeable,mergeStateStatus
```

Expected: a run appears within five minutes, completes successfully with `headSha` exactly equal to `candidate_sha`, all PR checks pass, and `isDraft` is false. This fresh result supersedes run `32105011071` if the audit-plan commit changed the head.

- [ ] **Step 4: Inventory forks, collaborators, clone traffic, and local clones**

Run outside the sandbox and keep identity/path inventories private:

```bash
gh api repos/ArkashJ/harness_extractor --jq '{visibility,forks_count,stargazers_count,subscribers_count}' > /private/tmp/harness-extractor-repository-exposure.json
gh api --paginate repos/ArkashJ/harness_extractor/forks --jq '.[].full_name' > /private/tmp/harness-extractor-forks.txt
test ! -s /private/tmp/harness-extractor-forks.txt
if gh api --paginate repos/ArkashJ/harness_extractor/collaborators --jq '.[].login' > /private/tmp/harness-extractor-collaborators.txt; then
  test -f /private/tmp/harness-extractor-collaborators.txt
else
  printf '%s\n' 'collaborator inventory unavailable to current token' > /private/tmp/harness-extractor-collaborators.unavailable
fi
if gh api repos/ArkashJ/harness_extractor/traffic/clones > /private/tmp/harness-extractor-clone-traffic.json; then
  test -s /private/tmp/harness-extractor-clone-traffic.json
else
  printf '%s\n' 'clone telemetry unavailable to current token' > /private/tmp/harness-extractor-clone-traffic.unavailable
fi
: > /private/tmp/harness-extractor-local-clones.txt
find "$HOME/Developer" -name .git -prune -print0 |
  while IFS= read -r -d '' git_entry; do
    clone=${git_entry%/.git}
    if git -C "$clone" remote get-url --all origin 2>/dev/null | grep -Eq 'github\.com[:/]ArkashJ/harness_extractor(\.git)?$'; then
      printf '%s\n' "$clone"
    fi
  done > /private/tmp/harness-extractor-local-clones.txt
```

Expected: the repository remains private and the fork inventory is empty. Preserve collaborator, clone-traffic, and local-clone inventories privately; every listed clone must be replaced or cleaned after the rewrite, never merged from stale history.

- [ ] **Step 5: Freeze advertised refs and assert the known ref shape**

```bash
git ls-remote origin > /private/tmp/harness-extractor-before-rewrite.refs
git ls-remote --heads origin | awk '{print $2}' | sort > /private/tmp/harness-extractor-before-rewrite.heads
printf '%s\n' refs/heads/codex/library-cli-implementation refs/heads/codex/release-readiness refs/heads/main | sort > /private/tmp/harness-extractor-expected.heads
diff -u /private/tmp/harness-extractor-expected.heads /private/tmp/harness-extractor-before-rewrite.heads
test -z "$(git ls-remote --tags origin)"
```

Expected: exactly the three known branch names and no tags. Stop if any other branch or tag exists; it must be included deliberately rather than deleted by omission.

- [ ] **Step 6: Commit**

No commit: this task records authoritative external state only.

---

### Task 2: Back up and rewrite the public history locally

**Files:**
- Create outside the repository: one unique private directory below `$HOME/Developer/personal/extractor-private-backups/`, containing `repository.bundle` and retained `filter-repo` evidence.
- Create temporarily: `/private/tmp/harness-extractor-history-source.git`
- Create temporarily: `/private/tmp/harness-extractor-history-rewrite.git`

**Interfaces:**
- Consumes: the frozen remote refs and exact PR-head SHA from Task 1.
- Produces: a verified rewritten mirror containing the same three branch names and no forbidden reachable path.

- [ ] **Step 1: Create and verify the private recovery bundle**

Run outside the sandbox:

```bash
umask 077
backup_parent="$HOME/Developer/personal/extractor-private-backups"
install -d -m 700 "$backup_parent"
backup_dir=$(mktemp -d "$backup_parent/harness-extractor-before-public-rewrite.XXXXXX")
backup="$backup_dir/repository.bundle"
test ! -e "$backup"
git bundle create "$backup" --all
chmod 600 "$backup"
git bundle verify "$backup"
shasum -a 256 "$backup"
stat -f '%Sp %N' "$backup"
printf '%s\n' "$backup" > /private/tmp/harness-extractor-private-backup.path
```

Expected: the `umask` is set before creation, the bundle target did not previously exist, bundle verification succeeds, and `stat` begins with `-rw-------`. Record its unique path and checksum privately; never put the bundle or hash in the public repository.

- [ ] **Step 2: Clone two disposable mirrors from GitHub**

```bash
git clone --mirror git@github.com:ArkashJ/harness_extractor.git /private/tmp/harness-extractor-history-source.git
git clone --mirror git@github.com:ArkashJ/harness_extractor.git /private/tmp/harness-extractor-history-rewrite.git
git -C /private/tmp/harness-extractor-history-source.git fetch origin '+refs/pull/*:refs/pull/*'
git -C /private/tmp/harness-extractor-history-rewrite.git fetch origin '+refs/pull/*:refs/pull/*'
git -C /private/tmp/harness-extractor-history-source.git fsck --full --strict
git -C /private/tmp/harness-extractor-history-rewrite.git fsck --full --strict
```

- [ ] **Step 3: Record source tips and non-private tree content**

```bash
source_mirror=/private/tmp/harness-extractor-history-source.git
for branch in main codex/release-readiness codex/library-cli-implementation; do
  git -C "$source_mirror" rev-parse "refs/heads/$branch" > "/private/tmp/harness-extractor-old-${branch//\//-}.sha"
  git -C "$source_mirror" ls-tree -r "refs/heads/$branch" |
    awk '$4 !~ /^(findings|synthesis|out|\.claude|\.superpowers)(\/|$)/ && $4 !~ /^prompts\/ORIGIN-/ && $4 != "prompts/PR-REVIEW-PROMPT.md" && $4 != "prompts/repo-steward-SEED.md" {print}' |
    sort > "/private/tmp/harness-extractor-old-${branch//\//-}.tree"
done
```

- [ ] **Step 4: Remove every forbidden path from every mirrored ref**

```bash
git -C /private/tmp/harness-extractor-history-rewrite.git filter-repo \
  --sensitive-data-removal \
  --path findings \
  --path synthesis \
  --path out \
  --path .claude \
  --path .superpowers \
  --path-glob 'prompts/ORIGIN-*' \
  --path prompts/PR-REVIEW-PROMPT.md \
  --path prompts/repo-steward-SEED.md \
  --invert-paths \
  --force
```

- [ ] **Step 5: Retain sensitive-removal evidence for GitHub Support**

```bash
rewrite_mirror=/private/tmp/harness-extractor-history-rewrite.git
filter_metadata="$rewrite_mirror/filter-repo"
test -s "$filter_metadata/changed-refs"
test -s "$filter_metadata/first-changed-commits"
backup=$(cat /private/tmp/harness-extractor-private-backup.path)
evidence_dir="$(dirname "$backup")/filter-repo"
install -d -m 700 "$evidence_dir"
install -m 600 "$filter_metadata/changed-refs" "$evidence_dir/changed-refs"
install -m 600 "$filter_metadata/first-changed-commits" "$evidence_dir/first-changed-commits"
install -m 600 "$filter_metadata/commit-map" "$evidence_dir/commit-map"
awk '/^refs\/pull\/.*\/head$/ {count++} END {print count + 0}' "$evidence_dir/changed-refs" > "$evidence_dir/affected-pull-request-count"
shasum -a 256 "$evidence_dir/changed-refs" "$evidence_dir/first-changed-commits" "$evidence_dir/commit-map"
```

Expected: `changed-refs`, `first-changed-commits`, `commit-map`, and the affected-PR count are retained beside the private bundle with private permissions. Report their counts and hashes, not sensitive payloads; provide the exact first-changed commits and affected PR count privately to GitHub Support.

- [ ] **Step 6: Prove ref shape, path removal, retained public content, and graph health**

```bash
rewrite_mirror=/private/tmp/harness-extractor-history-rewrite.git
git -C "$rewrite_mirror" for-each-ref --format='%(refname)' refs/heads | sort > /private/tmp/harness-extractor-after-rewrite.heads
diff -u /private/tmp/harness-extractor-expected.heads /private/tmp/harness-extractor-after-rewrite.heads
test -z "$(git -C "$rewrite_mirror" rev-list --objects --all | awk 'NF > 1 {sub(/^[^ ]+ /, ""); if ($0 ~ /^(findings|synthesis|out|\.claude|\.superpowers)(\/|$)/ || $0 ~ /^prompts\/ORIGIN-/ || $0 == "prompts/PR-REVIEW-PROMPT.md" || $0 == "prompts/repo-steward-SEED.md") print}')"
for branch in main codex/release-readiness codex/library-cli-implementation; do
  git -C "$rewrite_mirror" ls-tree -r "refs/heads/$branch" |
    awk '$4 !~ /^(findings|synthesis|out|\.claude|\.superpowers)(\/|$)/ && $4 !~ /^prompts\/ORIGIN-/ && $4 != "prompts/PR-REVIEW-PROMPT.md" && $4 != "prompts/repo-steward-SEED.md" {print}' |
    sort > "/private/tmp/harness-extractor-new-${branch//\//-}.tree"
  diff -u "/private/tmp/harness-extractor-old-${branch//\//-}.tree" "/private/tmp/harness-extractor-new-${branch//\//-}.tree"
done
git -C "$rewrite_mirror" fsck --full --strict
```

Expected: ref and public-tree diffs are empty, the forbidden-path assertion is empty, and `git fsck` succeeds.

- [ ] **Step 7: Run the complete gate from the rewritten PR head**

```bash
git clone --branch codex/release-readiness /private/tmp/harness-extractor-history-rewrite.git /private/tmp/harness-extractor-rewritten-checkout
cd /private/tmp/harness-extractor-rewritten-checkout
python3 -m unittest discover -s tests -v
python3 -m py_compile harness_extractor.py harvest.py
uv build
uvx twine check dist/*
git diff --check
git status --short
```

Expected: the complete suite passes (repository-only tests run here), compile succeeds, wheel and sdist pass Twine, diff check is clean, and status is empty.

- [ ] **Step 8: Commit**

No commit: the rewrite remains isolated until the explicit confirmation gate.

---

### Task 3: Force-push rewritten refs and verify GitHub readback

**Files:**
- No repository file changes.

**Interfaces:**
- Consumes: the verified rewrite mirror and frozen pre-rewrite remote tips.
- Produces: rewritten GitHub branches, regenerated PR refs, a fresh all-ref clone with zero forbidden paths, and green CI for the rewritten candidate.

- [ ] **Step 1: Stop for a fresh force-push confirmation**

Ask exactly:

```text
The disposable mirror has passed graph, content, privacy, build, and test checks. May I now force-push the rewritten main, codex/release-readiness, and codex/library-cli-implementation refs to ArkashJ/harness_extractor using force-with-lease? This rewrites public Git history and invalidates old commit IDs.
```

Do not continue until the user confirms this force-push in the current interaction. Earlier implementation or planning approval does not count.

- [ ] **Step 2: Recheck identity and leases immediately before mutation**

Run outside the sandbox as one shell block:

```bash
gh repo view ArkashJ/harness_extractor --json nameWithOwner,url
git ls-remote origin > /private/tmp/harness-extractor-immediate-pre-push.refs
diff -u /private/tmp/harness-extractor-before-rewrite.refs /private/tmp/harness-extractor-immediate-pre-push.refs
old_main=$(cat /private/tmp/harness-extractor-old-main.sha)
old_pr=$(cat /private/tmp/harness-extractor-old-codex-release-readiness.sha)
old_impl=$(cat /private/tmp/harness-extractor-old-codex-library-cli-implementation.sha)
test "$(git ls-remote origin refs/heads/main | awk '{print $1}')" = "$old_main"
test "$(git ls-remote origin refs/heads/codex/release-readiness | awk '{print $1}')" = "$old_pr"
test "$(git ls-remote origin refs/heads/codex/library-cli-implementation | awk '{print $1}')" = "$old_impl"
```

Expected: exact repository identity, no ref drift, and all three leases pass. Abort if any assertion fails.

- [ ] **Step 3: Force-push only the known branches with leases**

```bash
rewrite_mirror=/private/tmp/harness-extractor-history-rewrite.git
old_main=$(cat /private/tmp/harness-extractor-old-main.sha)
old_pr=$(cat /private/tmp/harness-extractor-old-codex-release-readiness.sha)
old_impl=$(cat /private/tmp/harness-extractor-old-codex-library-cli-implementation.sha)
git -C "$rewrite_mirror" remote add origin git@github.com:ArkashJ/harness_extractor.git
git -C "$rewrite_mirror" push origin \
  --atomic \
  --force-with-lease="refs/heads/main:$old_main" \
  --force-with-lease="refs/heads/codex/release-readiness:$old_pr" \
  --force-with-lease="refs/heads/codex/library-cli-implementation:$old_impl" \
  refs/heads/main:refs/heads/main \
  refs/heads/codex/release-readiness:refs/heads/codex/release-readiness \
  refs/heads/codex/library-cli-implementation:refs/heads/codex/library-cli-implementation
```

Expected: exactly three forced updates. Do not use `--mirror`; GitHub-owned `refs/pull/**` are not push targets.

- [ ] **Step 4: Read back every GitHub-advertised ref into a fresh bare clone**

Run outside the sandbox after GitHub regenerates the pull refs:

```bash
rewritten_sha=$(git -C /private/tmp/harness-extractor-history-rewrite.git rev-parse refs/heads/codex/release-readiness)
rewritten_base=$(git -C /private/tmp/harness-extractor-history-rewrite.git rev-parse refs/heads/main)
pr_head=""
pr_merge=""
for attempt in {1..30}; do
  pr_head=$(git ls-remote origin refs/pull/1/head | awk '{print $1}')
  pr_merge=$(git ls-remote origin refs/pull/1/merge | awk '{print $1}')
  if test "$pr_head" = "$rewritten_sha" && test -n "$pr_merge"; then break; fi
  sleep 10
done
test "$pr_head" = "$rewritten_sha"
test -n "$pr_merge"
git clone --bare git@github.com:ArkashJ/harness_extractor.git /private/tmp/harness-extractor-github-readback.git
git -C /private/tmp/harness-extractor-github-readback.git fetch origin '+refs/pull/*:refs/pull/*'
git ls-remote origin > /private/tmp/harness-extractor-after-rewrite.refs
git -C /private/tmp/harness-extractor-github-readback.git for-each-ref --format='%(refname) %(objectname)' | sort
read -r merge_commit merge_base merge_head extra <<< "$(git -C /private/tmp/harness-extractor-github-readback.git rev-list --parents -n 1 refs/pull/1/merge)"
test "$merge_base" = "$rewritten_base"
test "$merge_head" = "$rewritten_sha"
test -z "$extra"
test -z "$(git -C /private/tmp/harness-extractor-github-readback.git rev-list --objects --all | awk 'NF > 1 {sub(/^[^ ]+ /, ""); if ($0 ~ /^(findings|synthesis|out|\.claude|\.superpowers)(\/|$)/ || $0 ~ /^prompts\/ORIGIN-/ || $0 == "prompts/PR-REVIEW-PROMPT.md" || $0 == "prompts/repo-steward-SEED.md") print}')"
git -C /private/tmp/harness-extractor-github-readback.git fsck --full --strict
```

Expected: the exact `refs/pull/1/head` appears within five minutes, its regenerated merge ref has the rewritten `main` and PR head as parents, branch and pull refs contain zero forbidden paths, and `git fsck` succeeds.

- [ ] **Step 5: Require rewritten-head CI**

```bash
gh pr view 1 --repo ArkashJ/harness_extractor --json url,isDraft,headRefName,headRefOid,baseRefName,mergeable,mergeStateStatus
rewritten_sha=$(gh pr view 1 --repo ArkashJ/harness_extractor --json headRefOid --jq .headRefOid)
ci_run_id=""
for attempt in {1..30}; do
  ci_run_id=$(gh run list --repo ArkashJ/harness_extractor --workflow CI --commit "$rewritten_sha" --json databaseId,headSha --jq ".[] | select(.headSha == \"$rewritten_sha\") | .databaseId" | head -n 1)
  test -z "$ci_run_id" || break
  sleep 10
done
test -n "$ci_run_id"
gh run watch "$ci_run_id" --repo ArkashJ/harness_extractor --exit-status
test "$(gh run view "$ci_run_id" --repo ArkashJ/harness_extractor --json headSha --jq .headSha)" = "$rewritten_sha"
test "$(gh run view "$ci_run_id" --repo ArkashJ/harness_extractor --json conclusion --jq .conclusion)" = success
gh pr checks 1 --repo ArkashJ/harness_extractor
printf '%s\n' "$rewritten_sha" > /private/tmp/harness-extractor-expected-merge-head.sha
git ls-remote origin refs/heads/main | awk '{print $1}' > /private/tmp/harness-extractor-expected-merge-base.sha
test -s /private/tmp/harness-extractor-expected-merge-head.sha
test -s /private/tmp/harness-extractor-expected-merge-base.sha
```

Expected: PR #1 remains open and mergeable, CI succeeds for its rewritten `headRefOid`, and the exact reviewed head/base SHAs are persisted for the merge guard.

- [ ] **Step 6: Complete GitHub Support cleanup and stale-copy coordination while private**

Keep the repository `PRIVATE`. Open a GitHub Support sensitive-data-removal case following GitHub's [authoritative cleanup procedure](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository). Provide privately:

- owner/repository identity;
- the affected pull-request count from `changed-refs`;
- every entry from `first-changed-commits`;
- any LFS orphan evidence reported by `git filter-repo`;
- a request to remove cached views and pre-rewrite internal pull-request refs, dereference affected PR history, run server garbage collection, and confirm completion.

Do not include confidential file contents in the case. Wait for Support's affirmative completion response, retain the case identifier privately, and follow any stricter instruction they provide. Collaborators must rebase or reclone rather than merge stale history. Every local clone inventoried in Task 1 must be replaced, cleaned per the `git-filter-repo` manual, or explicitly quarantined from all future pushes.

After Support closes the cleanup, run the authoritative follow-up:

```bash
test "$(gh repo view ArkashJ/harness_extractor --json visibility --jq .visibility)" = PRIVATE
test "$(gh api repos/ArkashJ/harness_extractor --jq .visibility)" = private
gh api --paginate repos/ArkashJ/harness_extractor/forks --jq '.[].full_name' > /private/tmp/harness-extractor-post-support-forks.txt
test ! -s /private/tmp/harness-extractor-post-support-forks.txt
git clone --bare git@github.com:ArkashJ/harness_extractor.git /private/tmp/harness-extractor-post-support-readback.git
git -C /private/tmp/harness-extractor-post-support-readback.git fetch origin '+refs/pull/*:refs/pull/*'
test -z "$(git -C /private/tmp/harness-extractor-post-support-readback.git rev-list --objects --all | awk 'NF > 1 {sub(/^[^ ]+ /, ""); if ($0 ~ /^(findings|synthesis|out|\.claude|\.superpowers)(\/|$)/ || $0 ~ /^prompts\/ORIGIN-/ || $0 == "prompts/PR-REVIEW-PROMPT.md" || $0 == "prompts/repo-steward-SEED.md") print}')"
first_changed=$(dirname "$(cat /private/tmp/harness-extractor-private-backup.path)")/filter-repo/first-changed-commits
while read -r old_commit remainder; do
  test -n "$old_commit" || continue
  if gh api "repos/ArkashJ/harness_extractor/commits/$old_commit" >/dev/null 2>&1; then
    printf '%s\n' 'a pre-rewrite first-changed commit remains accessible' >&2
    exit 1
  fi
done < "$first_changed"
git -C /private/tmp/harness-extractor-post-support-readback.git fsck --full --strict
```

If Support had to remove PR #1, obtain confirmation and create a replacement PR from the already-rewritten branch; otherwise retain PR #1. Store the authoritative PR number and re-run review/check gates:

```bash
release_pr=1
pr_state=$(gh pr view 1 --repo ArkashJ/harness_extractor --json state --jq .state 2>/dev/null || true)
if test "$pr_state" != OPEN; then
  release_url=$(gh pr create --repo ArkashJ/harness_extractor --base main --head codex/release-readiness --title 'Release harness-extractor 1.0.0' --body 'Replacement review after sensitive-data cleanup; review the full rewritten diff and privacy gates.')
  release_pr=${release_url##*/}
fi
printf '%s\n' "$release_pr" > /private/tmp/harness-extractor-release-pr.number
expected_head=$(git -C /private/tmp/harness-extractor-history-rewrite.git rev-parse refs/heads/codex/release-readiness)
expected_base=$(git -C /private/tmp/harness-extractor-history-rewrite.git rev-parse refs/heads/main)
clean_pr_head=""
for attempt in {1..30}; do
  clean_pr_head=$(git ls-remote origin "refs/pull/$release_pr/head" | awk '{print $1}')
  if test "$clean_pr_head" = "$expected_head"; then break; fi
  sleep 10
done
test "$clean_pr_head" = "$expected_head"
test "$(gh pr view "$release_pr" --repo ArkashJ/harness_extractor --json headRefOid --jq .headRefOid)" = "$expected_head"
ci_run_id=""
for attempt in {1..30}; do
  ci_run_id=$(gh run list --repo ArkashJ/harness_extractor --workflow CI --commit "$expected_head" --json databaseId,headSha --jq ".[] | select(.headSha == \"$expected_head\") | .databaseId" | head -n 1)
  test -z "$ci_run_id" || break
  sleep 10
done
test -n "$ci_run_id"
gh run watch "$ci_run_id" --repo ArkashJ/harness_extractor --exit-status
test "$(gh run view "$ci_run_id" --repo ArkashJ/harness_extractor --json headSha --jq .headSha)" = "$expected_head"
gh pr checks "$release_pr" --repo ArkashJ/harness_extractor
gh pr view "$release_pr" --repo ArkashJ/harness_extractor --json url,isDraft,state,headRefOid,baseRefName,mergeable,mergeStateStatus
printf '%s\n' "$expected_head" > /private/tmp/harness-extractor-expected-merge-head.sha
printf '%s\n' "$expected_base" > /private/tmp/harness-extractor-expected-merge-base.sha
```

Expected: Support confirms cached-view/internal-PR-ref cleanup and garbage collection, old first-changed commits are inaccessible, a fresh all-ref clone and fork inventory are clean, stale clones are accounted for, and the reviewed release PR points exactly at the rewritten head/base. Any replacement PR receives fresh human review before merge.

- [ ] **Step 7: Commit**

No commit: authoritative state changed on GitHub and was read back from GitHub.

---

### Task 4: Merge the reviewed PR, restore public visibility, and publish `v1.0.0`

**Files:**
- No repository file changes.

**Interfaces:**
- Consumes: the reviewed PR number stored after Support cleanup, successful exact-head CI, and zero forbidden paths in GitHub readback.
- Produces: merged `main`, annotated tag `v1.0.0`, GitHub release, and two verified release assets.

- [ ] **Step 1: Stop for a fresh merge confirmation**

Ask exactly:

```text
The post-cleanup release PR is reviewed, mergeable, green at its rewritten head, and the fresh GitHub all-ref clone contains zero forbidden paths. May I merge it into main now? This is a separate confirmation from the history force-push.
```

Do not continue until the user confirms this merge in the current interaction.

- [ ] **Step 2: Recheck the merge target and merge without deleting branches**

```bash
release_pr=$(cat /private/tmp/harness-extractor-release-pr.number)
gh repo view ArkashJ/harness_extractor --json nameWithOwner,url
gh pr checks "$release_pr" --repo ArkashJ/harness_extractor
gh pr view "$release_pr" --repo ArkashJ/harness_extractor --json isDraft,mergeable,mergeStateStatus,headRefOid,baseRefName
expected_head=$(cat /private/tmp/harness-extractor-expected-merge-head.sha)
expected_base=$(cat /private/tmp/harness-extractor-expected-merge-base.sha)
actual_head=$(gh pr view "$release_pr" --repo ArkashJ/harness_extractor --json headRefOid --jq .headRefOid)
actual_base=$(git ls-remote origin refs/heads/main | awk '{print $1}')
test "$actual_head" = "$expected_head"
test "$actual_base" = "$expected_base"
gh pr merge "$release_pr" --repo ArkashJ/harness_extractor --merge --match-head-commit "$expected_head"
gh pr view "$release_pr" --repo ArkashJ/harness_extractor --json state,mergedAt,mergeCommit,url
```

Expected: checks pass, the reviewed rewritten head/base match immediately before the write, and `--match-head-commit` prevents a moved head from merging. Afterward PR state is `MERGED` and `mergeCommit.oid` is present.

- [ ] **Step 3: Read back `main` and run the release gate**

```bash
git clone --branch main git@github.com:ArkashJ/harness_extractor.git /private/tmp/harness-extractor-main-readback
cd /private/tmp/harness-extractor-main-readback
release_pr=$(cat /private/tmp/harness-extractor-release-pr.number)
release_commit=$(git rev-parse HEAD)
test "$release_commit" = "$(gh pr view "$release_pr" --repo ArkashJ/harness_extractor --json mergeCommit --jq .mergeCommit.oid)"
python3 -m unittest discover -s tests -v
python3 -m py_compile harness_extractor.py harvest.py
uv build
uvx twine check dist/*
git diff --check
git status --short
```

Expected: `main` equals the reviewed PR's merge commit, the complete suite passes, both artifacts pass Twine, and status is empty. This `release_commit` is the authoritative tag target; pre-rewrite `8cbd38b…` is provenance only.

- [ ] **Step 4: Verify reporting links, restore `PUBLIC`, and enable private reporting**

Before changing visibility, prove merged `main` points both policies to the same intended private channel and the Support gate left the repository private:

```bash
cd /private/tmp/harness-extractor-main-readback
reporting_url='https://github.com/ArkashJ/harness_extractor/security/advisories/new'
test "$(grep -F -l "$reporting_url" SECURITY.md CODE_OF_CONDUCT.md | wc -l | tr -d ' ')" = 2
test "$(gh repo view ArkashJ/harness_extractor --json visibility --jq .visibility)" = PRIVATE
test "$(gh api repos/ArkashJ/harness_extractor --jq .visibility)" = private
```

Ask for fresh confirmation to restore `ArkashJ/harness_extractor` to public visibility. Then mutate and read back both visibility and the enabled reporting channel:

```bash
gh repo edit ArkashJ/harness_extractor --visibility public --accept-visibility-change-consequences
test "$(gh repo view ArkashJ/harness_extractor --json visibility --jq .visibility)" = PUBLIC
test "$(gh api repos/ArkashJ/harness_extractor --jq .visibility)" = public
gh api --method PUT repos/ArkashJ/harness_extractor/private-vulnerability-reporting
test "$(gh api repos/ArkashJ/harness_extractor/private-vulnerability-reporting --jq .enabled)" = true
```

Expected: the merged docs share the exact private-reporting URL before exposure; GitHub reads back `PUBLIC`/`public`; the private-vulnerability-reporting endpoint reads back `enabled: true`. Stop and return the repository to private if any post-change readback fails.

- [ ] **Step 5: Require successful CI for the exact merge/release commit**

Run outside the sandbox as one shell block:

```bash
release_commit=$(git -C /private/tmp/harness-extractor-main-readback rev-parse HEAD)
ci_run_id=""
for attempt in {1..30}; do
  ci_run_id=$(gh run list --repo ArkashJ/harness_extractor --workflow CI --commit "$release_commit" --json databaseId,headSha --jq ".[] | select(.headSha == \"$release_commit\") | .databaseId" | head -n 1)
  test -z "$ci_run_id" || break
  sleep 10
done
test -n "$ci_run_id"
gh run watch "$ci_run_id" --repo ArkashJ/harness_extractor --exit-status
test "$(gh run view "$ci_run_id" --repo ArkashJ/harness_extractor --json headSha --jq .headSha)" = "$release_commit"
test "$(gh run view "$ci_run_id" --repo ArkashJ/harness_extractor --json conclusion --jq .conclusion)" = success
gh run view "$ci_run_id" --repo ArkashJ/harness_extractor --json url,status,conclusion,headSha,jobs
```

Expected: the authoritative CI workflow completes successfully with `headSha` equal to the merge commit. Do not create the tag from local-only gate evidence.

- [ ] **Step 6: Confirm publication, then push the annotated tag**

Ask for confirmation to publish `v1.0.0`, then run:

```bash
cd /private/tmp/harness-extractor-main-readback
gh repo view ArkashJ/harness_extractor --json nameWithOwner,url
test -z "$(git ls-remote --tags origin refs/tags/v1.0.0 refs/tags/v1.0.0^{})"
git tag -a v1.0.0 -m 'harness-extractor 1.0.0' "$(git rev-parse HEAD)"
git push origin refs/tags/v1.0.0
git ls-remote --tags origin refs/tags/v1.0.0 refs/tags/v1.0.0^{}
```

- [ ] **Step 7: Wait for the tag workflow and read back the release**

```bash
release_commit=$(git -C /private/tmp/harness-extractor-main-readback rev-parse HEAD)
release_run_id=""
for attempt in {1..30}; do
  release_run_id=$(gh run list --repo ArkashJ/harness_extractor --workflow Release --event push --json databaseId,headBranch,headSha --jq ".[] | select(.headBranch == \"v1.0.0\" and .headSha == \"$release_commit\") | .databaseId" | head -n 1)
  test -z "$release_run_id" || break
  sleep 10
done
test -n "$release_run_id"
gh run watch "$release_run_id" --repo ArkashJ/harness_extractor --exit-status
test "$(gh run view "$release_run_id" --repo ArkashJ/harness_extractor --json headSha --jq .headSha)" = "$release_commit"
gh run view "$release_run_id" --repo ArkashJ/harness_extractor --json url,status,conclusion,headSha,jobs
gh release view v1.0.0 --repo ArkashJ/harness_extractor --json tagName,url,isDraft,isPrerelease,publishedAt,assets
```

Expected: the exact tag/ref run appears within five minutes and succeeds at `release_commit`; the release is published, not draft/prerelease, and exposes exactly the named wheel and sdist.

- [ ] **Step 8: Download, hash, inspect, and clean-install release assets**

Run outside the sandbox as one shell block:

```bash
release_dir=$(mktemp -d /private/tmp/harness-extractor-v1.0.0-assets.XXXXXX)
gh release download v1.0.0 --repo ArkashJ/harness_extractor --dir "$release_dir" --pattern 'harness_extractor-1.0.0*'
test "$(find "$release_dir" -type f | wc -l | tr -d ' ')" = 2
shasum -a 256 "$release_dir"/*
release_sdist_sha256=$(shasum -a 256 "$release_dir/harness_extractor-1.0.0.tar.gz" | awk '{print $1}')
[[ "$release_sdist_sha256" =~ ^[0-9a-f]{64}$ ]]
api_sdist_digest=$(gh api repos/ArkashJ/harness_extractor/releases/tags/v1.0.0 --jq '.assets[] | select(.name == "harness_extractor-1.0.0.tar.gz") | .digest')
test "$api_sdist_digest" = "sha256:$release_sdist_sha256"
unzip -Z1 "$release_dir/harness_extractor-1.0.0-py3-none-any.whl"
tar -tzf "$release_dir/harness_extractor-1.0.0.tar.gz"
test -z "$({ unzip -Z1 "$release_dir/harness_extractor-1.0.0-py3-none-any.whl"; tar -tzf "$release_dir/harness_extractor-1.0.0.tar.gz" | sed 's#^[^/]*/##'; } | awk '/^(findings|synthesis|out|\.claude|\.superpowers)(\/|$)/ || /^prompts\/ORIGIN-/ || /^prompts\/PR-REVIEW-PROMPT\.md$/ || /^prompts\/repo-steward-SEED\.md$/ {print}')"
uvx twine check "$release_dir"/*
fixture=/private/tmp/harness-extractor-post-release-smoke.jsonl
printf '%s\n' '{"timestamp":"2026-08-18T00:00:00Z","sessionId":"post-release-smoke","cwd":"/tmp/example","message":{"role":"user","content":"No, use the shared helper."}}' > "$fixture"
uv venv --clear /private/tmp/harness-extractor-release-wheel
uv pip install --python /private/tmp/harness-extractor-release-wheel/bin/python "$release_dir/harness_extractor-1.0.0-py3-none-any.whl"
test "$(/private/tmp/harness-extractor-release-wheel/bin/harness-extractor --version)" = 'harness-extractor 1.0.0'
/private/tmp/harness-extractor-release-wheel/bin/harness-extractor --help | grep -F -- '--list'
/private/tmp/harness-extractor-release-wheel/bin/harness-extractor "$fixture" | grep -F '# Session post-release-smoke'
uv venv --clear /private/tmp/harness-extractor-release-sdist
uv pip install --python /private/tmp/harness-extractor-release-sdist/bin/python "$release_dir/harness_extractor-1.0.0.tar.gz"
test "$(/private/tmp/harness-extractor-release-sdist/bin/harness-extractor --version)" = 'harness-extractor 1.0.0'
/private/tmp/harness-extractor-release-sdist/bin/harness-extractor --help | grep -F -- '--list'
/private/tmp/harness-extractor-release-sdist/bin/harness-extractor "$fixture" | grep -F '# Session post-release-smoke'
printf '%s\n' "$release_sdist_sha256" > /private/tmp/harness-extractor-v1.0.0-sdist.sha256
```

Expected: GitHub's digest equals the computed digest, no forbidden members exist, Twine passes, and both downloaded assets pass version, help, and synthetic-fixture smokes. The checksum file is Task 5's only checksum input.

- [ ] **Step 9: Commit**

No commit: tag and release are authoritative GitHub state.

---

### Task 5: Build, test, and publish the Homebrew tap

**Files:**
- Create in the tap repository: `Formula/harness-extractor.rb`
- Retain the `README.md` generated by `brew tap-new`.
- Delete generated `.github/` automation because it builds/publishes bottles, opens automated bump PRs, and configures Dependabot, all excluded from `1.0.0`.

**Interfaces:**
- Consumes: the published release sdist URL and validated SHA-256 in `/private/tmp/harness-extractor-v1.0.0-sdist.sha256`.
- Produces: public `ArkashJ/homebrew-tap`, a source formula for `harness-extractor 1.0.0`, and a successful documented install command.

```text
GitHub release sdist
        |
        +--> download --> SHA-256 --> compare GitHub asset digest
                                      |
                                      v
                         Formula/harness-extractor.rb
                                      |
                     +----------------+----------------+
                     |                |                |
                     v                v                v
               brew audit      source install      brew test
                     |                |                |
                     +----------------+----------------+
                                      |
                                      v
                    publish ArkashJ/homebrew-tap
                                      |
                                      v
                 brew install ArkashJ/tap/harness-extractor
```

- [ ] **Step 1: Reconfirm the release checksum and Homebrew Python**

```bash
release_sdist_sha256=$(cat /private/tmp/harness-extractor-v1.0.0-sdist.sha256)
[[ "$release_sdist_sha256" =~ ^[0-9a-f]{64}$ ]]
asset_digest=$(gh api repos/ArkashJ/harness_extractor/releases/tags/v1.0.0 --jq '.assets[] | select(.name == "harness_extractor-1.0.0.tar.gz") | .digest')
test "$asset_digest" = "sha256:$release_sdist_sha256"
brew info python@3.14 --json=v2
```

Expected: digest equality and an available stable `python@3.14`. At plan creation Homebrew reports stable `3.14.7`.

- [ ] **Step 2: Create the local tap and checksum-bearing Python scaffold**

```bash
brew tap-new --branch main ArkashJ/homebrew-tap
tap_dir=$(brew --repository ArkashJ/homebrew-tap)
git -C "$tap_dir" rm -r .github
test ! -e "$tap_dir/.github"
HOMEBREW_EDITOR=true brew create --python \
  --set-name harness-extractor \
  --set-version 1.0.0 \
  --set-license MIT \
  --tap ArkashJ/homebrew-tap \
  https://github.com/ArkashJ/harness_extractor/releases/download/v1.0.0/harness_extractor-1.0.0.tar.gz
formula="$tap_dir/Formula/harness-extractor.rb"
formula_sha256=$(ruby -ne 'puts $1 if /sha256 "([0-9a-f]{64})"/' "$formula")
test "$formula_sha256" = "$(cat /private/tmp/harness-extractor-v1.0.0-sdist.sha256)"
```

Expected: all generated bottle/autobump/Dependabot automation is staged for deletion; Homebrew downloads the release asset and writes the independently verified checksum into the formula.

- [ ] **Step 3: Reduce the scaffold to the exact formula contract**

Use `apply_patch` on the generated formula. Preserve `brew create`'s exact `url` and 64-character `sha256` lines; make every other line match:

```ruby
class HarnessExtractor < Formula
  include Language::Python::Virtualenv

  desc "Reduce Claude Code session transcripts to the turns worth reviewing"
  homepage "https://github.com/ArkashJ/harness_extractor"
  url "https://github.com/ArkashJ/harness_extractor/releases/download/v1.0.0/harness_extractor-1.0.0.tar.gz"
  # Keep the verified sha256 line produced by brew create.
  license "MIT"

  depends_on "python@3.14"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "harness-extractor 1.0.0", shell_output("#{bin}/harness-extractor --version")

    (testpath/"session.jsonl").write <<~JSONL
      {"timestamp":"2026-08-18T00:00:00Z","sessionId":"brew-smoke","cwd":"/tmp/example","message":{"role":"user","content":"No, use the shared helper."}}
    JSONL
    output = shell_output("#{bin}/harness-extractor #{testpath}/session.jsonl")
    assert_match "# Session brew-smoke", output
    assert_match "No, use the shared helper.", output
  end
end
```

This follows Homebrew's current Python application guidance: immutable checksummed source, declared current Python, `virtualenv_install_with_resources`, and a functional installed-behavior test. There are no resource blocks because the package has no runtime dependencies.

- [ ] **Step 4: Revalidate URL and checksum after editing**

```bash
tap_dir=$(brew --repository ArkashJ/homebrew-tap)
formula="$tap_dir/Formula/harness-extractor.rb"
grep -F 'url "https://github.com/ArkashJ/harness_extractor/releases/download/v1.0.0/harness_extractor-1.0.0.tar.gz"' "$formula"
formula_sha256=$(ruby -ne 'puts $1 if /sha256 "([0-9a-f]{64})"/' "$formula")
test "$formula_sha256" = "$(cat /private/tmp/harness-extractor-v1.0.0-sdist.sha256)"
test "$(grep -c '^  sha256 "[0-9a-f]\{64\}"$' "$formula")" = 1
test ! -e "$tap_dir/.github"
```

- [ ] **Step 5: Run Homebrew's complete local gate**

```bash
brew audit --new --formula ArkashJ/tap/harness-extractor
brew install --build-from-source ArkashJ/tap/harness-extractor
brew test ArkashJ/tap/harness-extractor
harness-extractor --version
git -C "$(brew --repository ArkashJ/homebrew-tap)" diff --check
git -C "$(brew --repository ArkashJ/homebrew-tap)" status --short
```

Expected: audit, source installation, and functional test pass; the CLI prints `harness-extractor 1.0.0`; only generated tap/formula files are uncommitted.

- [ ] **Step 6: Commit the tap locally**

```bash
tap_dir=$(brew --repository ArkashJ/homebrew-tap)
git -C "$tap_dir" add README.md Formula
git -C "$tap_dir" diff --cached --check
git -C "$tap_dir" commit -m 'Add harness-extractor 1.0.0 formula'
git -C "$tap_dir" rev-parse HEAD > /private/tmp/harness-extractor-tap-commit.sha
git -C "$tap_dir" status --short
```

Expected: one local commit and empty status; `git ls-files .github` returns no paths.

- [ ] **Step 7: Confirm creation/publication, then create and push the tap**

Ask for confirmation to create public `ArkashJ/homebrew-tap` and publish the tested formula. Then run outside the sandbox:

```bash
gh api user --jq .login | grep -Fx ArkashJ
gh repo view ArkashJ/homebrew-tap --json nameWithOwner >/dev/null 2>&1 && exit 1 || test $? = 1
gh repo create ArkashJ/homebrew-tap --public --source "$(brew --repository ArkashJ/homebrew-tap)" --push --description 'Homebrew formulae maintained by ArkashJ'
gh repo view ArkashJ/homebrew-tap --json nameWithOwner,url,visibility,defaultBranchRef
tap_dir=$(brew --repository ArkashJ/homebrew-tap)
formula="$tap_dir/Formula/harness-extractor.rb"
expected_commit=$(cat /private/tmp/harness-extractor-tap-commit.sha)
remote_commit=$(gh api repos/ArkashJ/homebrew-tap/commits/main --jq .sha)
test "$remote_commit" = "$expected_commit"
remote_formula=$(mktemp /private/tmp/harness-extractor-remote-formula.XXXXXX)
gh api "repos/ArkashJ/homebrew-tap/contents/Formula/harness-extractor.rb?ref=$remote_commit" --jq .content | tr -d '\n' | base64 --decode > "$remote_formula"
cmp "$formula" "$remote_formula"
test "$(shasum -a 256 "$formula" | awk '{print $1}')" = "$(shasum -a 256 "$remote_formula" | awk '{print $1}')"
shasum -a 256 "$formula" "$remote_formula"
```

Expected: `ArkashJ/homebrew-tap`, public visibility, default branch `main`, remote commit exactly equal to the locally tested tap commit, and decoded remote formula bytes/hash exactly equal to the tested local formula.

- [ ] **Step 8: Verify the documented public install path from a fresh tap state**

```bash
brew uninstall harness-extractor
brew untap ArkashJ/tap
brew install ArkashJ/tap/harness-extractor
harness-extractor --version
brew test ArkashJ/tap/harness-extractor
```

Expected: the README command installs from the public tap, version is `1.0.0`, and the functional test passes.

- [ ] **Step 9: Final authoritative readback**

```bash
gh release view v1.0.0 --repo ArkashJ/harness_extractor --json url,tagName,isDraft,isPrerelease,assets
gh repo view ArkashJ/harness_extractor --json nameWithOwner,url,visibility,defaultBranchRef
test "$(gh api repos/ArkashJ/harness_extractor/private-vulnerability-reporting --jq .enabled)" = true
gh repo view ArkashJ/homebrew-tap --json nameWithOwner,url,visibility,defaultBranchRef
git ls-remote --heads --tags git@github.com:ArkashJ/harness_extractor.git
git ls-remote --heads git@github.com:ArkashJ/homebrew-tap.git
harness-extractor --version
```

Expected: the source repository is public with private vulnerability reporting enabled, release and tap URLs resolve, `v1.0.0` and both assets exist, both repositories advertise `main`, and the installed command reports `1.0.0`.

---

## Completion evidence

The final report must record:

1. private bundle path and mode, with its checksum kept only in private notes;
2. `changed-refs` count/hash, affected-PR count, `first-changed-commits` count/hash, and old-to-new mappings from `commit-map`;
3. fork count, observable collaborator/clone inventory counts, and disposition of every stale local clone;
4. fresh force-push confirmation and three successful leased updates;
5. regenerated exact PR refs, zero forbidden paths across fresh GitHub branch/pull refs, and rewritten exact-head CI URL;
6. GitHub Support case completion for internal PR refs, garbage collection, and cached views, plus inaccessible first-changed commits;
7. fresh merge confirmation, authoritative merge commit, consistent reporting links, `PUBLIC` visibility readback, and enabled private-vulnerability-reporting readback;
8. tag, Release workflow URL, release URL, artifact names, GitHub-validated digests, and both downloaded-artifact smokes;
9. Homebrew formula checksum, audit/install/test output, exact remote tap commit, byte/hash-equal formula readback, tap URL, and public install smoke.

If authoritative readback differs from the expected identity, ref, SHA, digest, or visibility, stop before the next external mutation and investigate.
