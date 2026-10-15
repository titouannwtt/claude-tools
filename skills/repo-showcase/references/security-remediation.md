# Security remediation

How to handle what `security` and `attribution` report. `S=~/.claude/skills/repo-showcase/scripts/showcase.py`,
`R=<repo>`. Both commands print a summary and findings sorted by severity (at most 5 occurrences per value, the
full redacted report is in `<git dir>/repo-showcase/security-report.json`), and exit 4 on any high or medium finding.
A finding has a `fingerprint` (stable id of the value), a `preview` (never the value), a `where`
(`working-tree`, `history`, `commit-message`, `identity`, `pull-request`, `release`) and a list of `remedy` ids.
Ask the user per category, never per finding. Fix the working tree first, then the history.

## Remedy ids

- `rotate`: revoke the credential at its provider and issue a new one. Mandatory for anything ever pushed.
- `redact-head`: edit the current files (placeholder, environment variable, generic text) and commit normally.
- `move-to-env`: read the value from the environment; commit an `.env.example` with placeholders only.
- `untrack`: `git rm --cached <file>` (folder: `git rm -r --cached <dir>`), add it to `.gitignore`, commit.
- `rewrite-history`: remove the data from every commit (`fix-plan` then `fix-apply`, see below).
- `mailmap`: replace an author or committer identity in history (`--map-email`, `--map-name`, `--map-mine`).
  A `.mailmap` file only changes how `git log` displays names, it does not rewrite anything.
- `strip-messages`: remove AI co-authorship lines from commit messages (`fix-plan --strip-ai`).
- `edit-pr`: edit pull request and release texts on GitHub (`fix-prs`).
- `allow`: accept a false positive: `python3 $S allow $R <fingerprint>...` (undo with `--remove`). A single line can
  also carry the comment `showcase: ignore`.
- `review`: ask the user what the file is; keep it only if it is public by intent.
- `lfs-or-release`: keep large binaries out of git (Git LFS or release assets).
- `keep`: nothing to fix, informational.

## Categories

**secret** (high): API keys, tokens, private keys, seed phrases, hard-coded passwords. Anyone who cloned has it.
Options: `rotate` first (GitHub: Settings > Developer settings; AWS: `aws iam create-access-key` then
`aws iam delete-access-key --access-key-id <old>`; Stripe, Slack, Anthropic, OpenAI, Google: the provider console;
SSH or TLS key: new key pair, replace the public half; JWT: new signing secret). Then `redact-head` and
`move-to-env`. Then rewrite the history only if the repository will be public: `fix-plan $R --replace-category secret`
(or `--replace <fingerprint>` for chosen values). Default: rotate, then redact-head, then rewrite.

**credentials-url** (high): a URL with a user and password before the host. Same as secret: rotate the password, use a URL without
credentials plus an environment variable, rewrite with `--replace-category credentials-url`.

**env-file** (high): a tracked `.env`-style file. `untrack`, add to `.gitignore`, keep `.env.example`, rotate every
value it held, then `fix-plan $R --remove-path .env` (removes the path from all commits). Default: untrack, rotate,
remove the path.

**credential-file** (high; low for a certificate or public key alone): `*.pem`, `*.key`, `.npmrc` with a token,
`.pypirc`, `.netrc`, keystores, `credentials.json`, kubeconfig. `untrack`, rotate, then
`fix-plan $R --remove-path <path>`. Default: same as env-file.

**email** (high): a real address in files, messages or git identities. Files: `redact-head` (use a noreply or
example.com address). Identities: `git config user.email <id>+<login>@users.noreply.github.com` for the future, and
for history `fix-plan $R --map-mine` or `--map-email OLD=NEW`. Other people's identities are never changed
implicitly: they appear under `third_party_identities`. Default: noreply address, `--map-mine` if the user agrees.

**ip** (medium public, low private) and **port** (low): infrastructure details. `redact-head` with a placeholder or
a documentation address (192.0.2.x). Private ranges and ports are usually acceptable: ask, then `allow` or fix.
History: `--replace-category ip`. Default: redact-head for public IPs, allow for the rest.

**username** (medium): a user folder path of macOS, Linux or Windows. `redact-head` with a relative path or a variable.
History: `--replace-category username`.

**personal-name** (high): configured personal terms (`--terms`, `FORBIDDEN_TERMS`), the OS login and full name, in
files, file names, messages or identities. `redact-head`, rename files with `git mv`, then `--replace-category
personal-name` for contents and `--map-name OLD=NEW` for author names. The public GitHub handle belongs in
`ALLOWED_TERMS`.

**phone**, **postal-address** (medium), **iban**, **card-number** (high): personal or financial data. `redact-head`,
then `--replace-category phone,postal-address,iban,card-number` for history. A card or IBAN that was real: tell the
user to contact the bank.

**personal-file** (medium; high when its text holds personal data or contract wording): contracts, invoices, CV,
identity documents, statements. `review` with the user. If private: `untrack`, `--remove-path <path>`. Office
documents are read (docx, odt, xlsx, pptx); PDFs and images are judged on the name only.

**photo** (medium; low when no EXIF), **photo-location** (high, GPS in EXIF), **photo-person** (high, faces):
`review`. Remove metadata with `exiftool -all= <file>` if installed, or re-export the image; remove the file from
git with `untrack` and `--remove-path`. Face detection needs `cv2` (or macOS Vision); `doctor` says if it is
available, otherwise the detail says "face detection unavailable" and the user must look at the images.

**large-blob** (low): a blob above 5 MB somewhere in history. `lfs-or-release`: ship the binary as a release asset
(`gh release upload <tag> <file>`) or with Git LFS. To shrink history: `fix-plan $R --strip-blobs-bigger-than 10M`.

**ai-coauthor** (high) and **ai-author** (medium): AI trailers and "generated with" lines in commit messages, files,
pull requests and releases; commits authored by an AI bot identity. Messages: `fix-plan $R --strip-ai`
(optionally with `--map-email BOT=NEW` for bot authors). Files: `redact-head`. Pull requests and releases:
`python3 $S fix-prs $R` (dry run), then `--confirm`. Product mentions in a README are not flagged.

**ai-config-file** (info): `CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.claude/`... Ask whether the user wants them
public; `keep` or `untrack`. Reported by `attribution` only.

## What rewriting history can and cannot fix

Can: remove data from every commit, tag and message of the local repository (and of the remote after a force-push).
Cannot (GitHub guidance): forks and clones made earlier keep the old commits; cached views and old commit URLs stay
reachable by SHA until GitHub garbage-collects them; `refs/pull/*` are read-only and only GitHub Support can purge
them; other people's clones cannot be cleaned. So: rotate secrets first, always. Rewriting protects the future, not
the past.

## fix-plan then fix-apply

1. `python3 $S fix-plan $R [options] [--remote origin]` first runs `git fetch --prune <remote>` and compares it with
   the local refs. It refuses (exit 6) when the remote is unreachable, when a local branch is behind or diverged
   from its remote counterpart (integrate first), or when the remote has a branch or tag absent locally (create
   it: `git branch --track X origin/X`, `git fetch origin tag T`): a force push would destroy that work or leave it
   unrewritten. A branch only ahead is fine. It writes `<git dir>/repo-showcase/plan/` (`mailmap.txt`,
   `replacements.txt`: the exact matched texts as bounded `regex:` lines, mode 600, `message-callback.py`,
   `paths.txt`, `terms.txt`, `plan.json` with the remote ref shas) and runs the exact rewrite on a temporary mirror
   clone. Values found inside zipped documents (docx, xlsx...) or non-UTF-8 files cannot be edited as text:
   fix-plan refuses (exit 6) and names the files; ask the user, then rerun with `--remove-path <file>` for each
   file to drop from every commit, or `allow` the fingerprints. Show:
   commits rewritten, first rewritten date, refs affected, size, `remote.not_pushed`, and
   `dry_run.remaining.total`, which must be 0 (exit 4 otherwise). Remaining values are found by rescanning the
   clone with the scanner. `--no-dry-run` only writes the plan.
2. `python3 $S fix-apply $R --confirm [--backup-dir DIR] [--push] [--remote origin]`. Refuses (exit 6) without
   `--confirm`, with changes to tracked files, if local refs or HEAD moved since the plan, if the remote moved
   since the plan (`git ls-remote`) or cannot be reached, without a plan, without git-filter-repo or with git older
   than 2.36 (run it on another machine). In `~/repo-showcase-backups` (created mode 700; an existing folder keeps
   its mode) it writes a verified `git bundle --all` and a `.git.tar.gz` archive of the whole git directory
   (reflogs and unreachable commits, which the rewrite expires), both mode 600. It rewrites, restores the remotes
   and upstream config (also on failure or interrupt, with the remote-tracking refs), rescans, and prints
   `next_steps`: one `git push --atomic --force-with-lease=<ref>:<recorded sha>... <remote> <ref>:<ref>...` for
   the branches and tags that already exist on the remote. Local-only refs are listed in `not_pushed`, never
   published. `--push` runs it; a rejected push (exit 7) is a stale lease (someone pushed: fetch and check) or a
   protected branch (lift the protection temporarily).
3. Show `remote_cleanup` to the user (rotate, forks, cached SHAs, `refs/pull/*`, re-clone, delete the backups).
4. `ready` blocks while the remote still points to pre-rewrite commits (`plan.applied.json`): run the push.

## Force-push consequences

Every commit hash changes from the first rewritten commit on. Collaborators must re-clone (or `git fetch` then
`git reset --hard origin/<branch>`); their old history merged back would reintroduce the data. Open pull requests may
break or show odd diffs. Commit and tag signatures are lost (re-sign if needed). Tags already on the remote are rewritten and pushed
with the branches. Releases pointing at old tags must be checked. Say all this before asking for the final yes.

## Restore and clean up

Restore: `git clone <backup>.bundle <new-folder>` gives the repository as it was before the rewrite (branches under
`origin/*`); for reflogs and unreachable commits too: `mkdir <new-folder> && tar -xzf <backup>.git.tar.gz -C
<new-folder> && git -C <new-folder> reset --hard`. Keep both until the user has checked the rewritten repository and
the remote, then delete them: `rm <backup>.bundle <backup>.git.tar.gz`. They still contain every removed secret, so
never commit or upload them. After a successful `fix-apply`, `replacements.txt`, `mailmap.txt`, `paths.txt`,
`terms.txt` and the message callback are deleted; only `plan.applied.json` (shas and fingerprints, no values)
stays. After a failure they are kept to retry: delete `<git dir>/repo-showcase/plan/` when done.
