#!/bin/bash
# ==========================================================================
#  Update Sangala Blocks on a Mac to the latest version from GitHub.
#  Double-click this file. Terminal opens, the update runs, and the window
#  stays so you can read what happened.
#
#  A Mac runs Sangala Blocks from a git clone of the repository, started with
#      node tools/bridge_stub.js
#  so an update is a pull of whatever branch the clone has checked out - the
#  orthographic branch while that work is being tested, main after it lands.
#  A Windows clone updates the same way with "Update SangalaBlocks (git).cmd".
#  Main's download updater, which fetches main's two files by hand for a school
#  machine without git, is not on this branch: it undid a test once.
#
#  It never leaves you half-updated: if the pull cannot go through cleanly -
#  no connection, a file you have edited in the folder, a branch that has
#  moved under you - it says which and changes nothing. It only updates:
#  starting the application is a separate step (Jo Watts, 2026-09-14).
#
#  The LEGO parts travel in the clone, so nothing else needs fetching.
# ==========================================================================
cd "$(dirname "$0")" || exit 1
export PATH="$PATH:/usr/local/bin:/opt/homebrew/bin"   # where an installer or Homebrew puts node

pause(){ echo; read -r -s -n 1 -p "Press any key to close this window."; echo; }
fail(){ echo; echo "Update FAILED - $1"; echo "Your current Sangala Blocks was NOT changed, so it still works."; pause; exit 1; }

echo "Checking for a newer Sangala Blocks..."
echo

command -v git >/dev/null 2>&1 || fail "git is not installed. Run 'git --version' in Terminal and accept Apple's offer to install it."
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "this folder is not a git clone. Clone the repository with git and run this file from the clone."

branch="$(git rev-parse --abbrev-ref HEAD)"
git rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1 || fail "the branch '$branch' has no GitHub branch to pull from."

# A file edited in the folder would be overwritten or tangled by the pull, so it stops here.
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "These files have been changed in this folder:"
  git status --short --untracked-files=no
  fail "pulling over changed files could lose them. Put them back with 'git checkout -- .' or keep them elsewhere, then run this again."
fi

git fetch --quiet origin || fail "could not reach GitHub. Check the internet connection and run this again."

before="$(git rev-parse HEAD)"
after="$(git rev-parse '@{upstream}')"
if [ "$before" = "$after" ]; then
  echo "Already up to date on the '$branch' branch - nothing changed."
  pause
  exit 0
fi

# Fast-forward only: the clone takes what GitHub has and never invents a merge of its own.
if ! git merge --ff-only --quiet '@{upstream}'; then
  fail "the '$branch' branch here has commits GitHub does not, so it cannot simply move forward. This needs a hand: run 'git status' and read what it says."
fi

echo "Updated the '$branch' branch. What came in:"
git --no-pager log --oneline "$before..$after"
echo
echo "Done - Sangala Blocks is up to date."
echo
echo "  Start it as before: in Terminal, in this folder,"
echo "      node tools/bridge_stub.js"
echo "  then open the address it prints. If a page was already open, reload it."
command -v node >/dev/null 2>&1 || { echo; echo "  NOTE: node is not installed, so it cannot be started. Install Node.js from nodejs.org."; }
[ -d "LDraw/ldraw/parts" ] || { echo; echo "  NOTE: the LEGO parts folder is missing, so parts will be drawn as stand-in shapes."; }
pause
exit 0
