@echo off
REM ==========================================================================
REM  Update Sangala Blocks on a Windows machine that runs it from a git clone.
REM  Double-click this file. It pulls whatever branch the clone has checked
REM  out - orthographic while that work is being tested, main after it lands -
REM  and lists what came in.
REM
REM  It never leaves you half-updated: if the pull cannot go through cleanly -
REM  no git, no connection, a file edited in this folder, a branch that has
REM  moved under you - it says which and changes nothing.
REM
REM  The download updater main carries, "Update SangalaBlocks.cmd", is not on this branch:
REM  it fetches main's page and program over whatever is here, which undid a test
REM  once (Jo Watts, 2026-09-14). A clone of this branch updates with this one.
REM
REM  It only updates. Sangala Blocks is closed first if it is running, because
REM  Windows will not replace a program file that is in use; start it again
REM  afterwards as usual, by double-clicking SangalaBlockDesigner.exe, and
REM  reload the page if one is open. The LEGO parts travel in the clone, so
REM  nothing else needs fetching.  (Jo Watts, 2026-09-14)
REM ==========================================================================
setlocal
cd /d "%~dp0"

echo Checking for a newer Sangala Blocks...
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo Update FAILED - git is not installed. Install Git for Windows from git-scm.com and run this again.
  goto :fail
)
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo Update FAILED - this folder is not a git clone. Clone the repository with git and run this file from the clone.
  goto :fail
)
set "BRANCH="
for /f "delims=" %%B in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%B"
git rev-parse --abbrev-ref @{upstream} >nul 2>&1
if errorlevel 1 (
  echo Update FAILED - the branch '%BRANCH%' has no GitHub branch to pull from.
  goto :fail
)

REM A file edited in this folder would be overwritten or tangled by the pull, so it stops here.
set "DIRTY="
for /f "delims=" %%L in ('git status --porcelain --untracked-files=no') do set "DIRTY=1"
if defined DIRTY (
  echo These files have been changed in this folder:
  git status --short --untracked-files=no
  echo.
  echo Update FAILED - pulling over changed files could lose them. Put them back with
  echo     git checkout -- .
  echo or keep them elsewhere, then run this again.
  goto :fail
)

git fetch --quiet origin
if errorlevel 1 (
  echo Update FAILED - could not reach GitHub. Check the internet connection and run this again.
  goto :fail
)
set "BEFORE="
set "AFTER="
for /f "delims=" %%H in ('git rev-parse HEAD') do set "BEFORE=%%H"
for /f "delims=" %%H in ('git rev-parse @{upstream}') do set "AFTER=%%H"
if "%BEFORE%"=="%AFTER%" (
  echo Already up to date on the '%BRANCH%' branch - nothing changed.
  goto :done
)

REM The program may be running, which locks its file, so close it first; nothing is lost.
taskkill /im "SangalaBlockDesigner.exe" /f >nul 2>&1

REM Fast-forward only: the clone takes what GitHub has and never invents a merge of its own.
git merge --ff-only @{upstream}
if errorlevel 1 (
  echo.
  echo Update FAILED - the '%BRANCH%' branch could not simply move forward. Read what git said
  echo above: either this clone has commits GitHub does not, or a file was still in use.
  goto :fail
)
echo.
echo Updated the '%BRANCH%' branch. What came in:
git --no-pager log --oneline %BEFORE%..%AFTER%
echo.
echo Done - Sangala Blocks is up to date.
echo.
echo   Start it as usual: double-click SangalaBlockDesigner.exe. If a page was open, reload it.
if not exist "%~dp0LDraw\ldraw\parts" (
  echo.
  echo   NOTE: the LEGO parts folder is missing, so parts will be drawn as stand-in shapes.
)
:done
echo.
pause
exit /b 0

:fail
echo Your current Sangala Blocks was NOT changed, so it still works.
echo.
pause
exit /b 1
