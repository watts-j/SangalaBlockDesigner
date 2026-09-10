@echo off
REM ==========================================================================
REM  Update Sangala Blocks to the latest version from GitHub.
REM  Double-click this file. No admin, no install, no git, no compiler needed.
REM
REM  This updates BOTH parts of the program in one step:
REM     SangalaBlockDesigner.html   (the page: tools, panels, fixes)
REM     SangalaBlockDesigner.exe    (the program that serves the page and
REM                                  renders snapshots)
REM  so an ordinary update and a program update both arrive the same way --
REM  you never have to rebuild anything by hand.
REM
REM  It only downloads when there is actually a newer version, and it never
REM  leaves you half-updated: if either file fails to download, nothing on your
REM  computer is changed.
REM
REM  WHAT IT DOES NOT UPDATE, and why. Sangala Blocks carries its own renderer
REM  (the LDView folder) and its own LEGO parts (the LDraw folder) -- about
REM  three thousand files. Those are fetched once, with the folder itself, and
REM  they change rarely; an updater that pulled them one at a time would take
REM  an hour. This checks that they are present and says so if they are not.
REM
REM  It also puts a "Sangala Blocks" icon on your Desktop -- and refreshes it if
REM  you have moved this folder -- so you can start the program without hunting
REM  for it. That happens whether or not there was anything new to download.
REM ==========================================================================
setlocal
cd /d "%~dp0"

set "BASE=https://raw.githubusercontent.com/watts-j/SangalaBlockDesigner/main"
set "HTML=SangalaBlockDesigner.html"
set "EXE=SangalaBlockDesigner.exe"
set "TMPHTML=SangalaBlockDesigner.html.new"
set "TMPEXE=SangalaBlockDesigner.exe.new"

echo Checking for a newer Sangala Blocks...
echo.

if exist "%TMPHTML%" del "%TMPHTML%" >nul 2>&1
if exist "%TMPEXE%"  del "%TMPEXE%"  >nul 2>&1

REM ---- 1. Download the page. curl is built into Windows 10/11; PowerShell is the fallback.
call :download "%BASE%/%HTML%" "%TMPHTML%"
if not exist "%TMPHTML%" goto :failed

REM A good page ends with the closing </html> tag; a truncated download will not.
find "</html>" "%TMPHTML%" >nul 2>&1
if errorlevel 1 goto :badfile

REM ---- 2. Compare release versions. Same version -> nothing to do, download nothing else.
set "REMOTEVER="
set "LOCALVER="
for /f "delims=" %%V in ('findstr /c:"SANGALA_VERSION" "%TMPHTML%"') do if not defined REMOTEVER set "REMOTEVER=%%V"
if exist "%HTML%" for /f "delims=" %%V in ('findstr /c:"SANGALA_VERSION" "%HTML%"') do if not defined LOCALVER set "LOCALVER=%%V"

if defined LOCALVER if "%LOCALVER%"=="%REMOTEVER%" (
  del "%TMPHTML%" >nul 2>&1
  echo Already up to date - nothing downloaded.
  call :checkparts
  call :shortcut
  echo.
  pause
  exit /b 0
)

REM ---- 3. There is a newer version. Download the program too, BEFORE we touch anything.
echo A newer version is available. Downloading...
call :download "%BASE%/%EXE%" "%TMPEXE%"

REM Sanity-check the download: it must exist and be a real program (tens of KB, not an error page).
set "EXEOK="
for %%F in ("%TMPEXE%") do if %%~zF GTR 20000 set "EXEOK=1"
if not defined EXEOK goto :badfile

REM ---- 4. Both files are downloaded and look complete. Now swap them in.
REM     The program may be running (its crane icon sits in the notification area),
REM     which locks the file, so close it first. Nothing is lost -- you just
REM     reopen it when we are done.
taskkill /im "%EXE%" /f >nul 2>&1
REM Give Windows a moment to release the file after closing the program.
timeout /t 1 /nobreak >nul 2>&1

REM Keep the current copies as backups, then move the new ones into place.
if exist "%HTML%" copy /y "%HTML%" "%HTML%.bak" >nul
if exist "%EXE%"  copy /y "%EXE%"  "%EXE%.bak"  >nul

move /y "%TMPHTML%" "%HTML%" >nul
move /y "%TMPEXE%"  "%EXE%"  >nul 2>&1
if exist "%TMPEXE%" (
  REM The program was still locked; wait a bit longer and try once more.
  timeout /t 2 /nobreak >nul 2>&1
  move /y "%TMPEXE%" "%EXE%" >nul 2>&1
)
if exist "%TMPEXE%" goto :exelocked

echo.
echo Done - Sangala Blocks is up to date.
echo.
echo   Now reopen SangalaBlockDesigner.exe (double-click it). Your browser will
echo   open the design page. If a page was already open, press F5 to refresh it.
call :checkparts
call :shortcut
echo.
echo   (Your previous version was saved as %HTML%.bak and %EXE%.bak, just in case.)
echo.
pause
exit /b 0

REM ==========================================================================
:download
REM  %1 = URL, %2 = output file. curl if present, else PowerShell.
where curl >nul 2>&1
if %errorlevel%==0 (
  curl -L -f -s -o "%~2" "%~1"
) else (
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%~1' -OutFile '%~2' -UseBasicParsing } catch { exit 1 }"
)
goto :eof

REM ==========================================================================
:checkparts
REM  The renderer and the parts travel with the folder rather than with an
REM  update. A folder copied before they shipped will update its page and its
REM  program quite happily and then take no snapshots, with nothing to say why --
REM  so it is said here.
if not exist "%~dp0LDView\LDView64.exe" goto :missingparts
if not exist "%~dp0LDraw\ldraw\parts" goto :missingparts
goto :eof
:missingparts
echo.
echo   NOTE: the renderer or the LEGO parts are missing from this folder, so
echo   the Snapshot button will not be offered. They are not downloaded by this
echo   update - they come with the folder. Ask for a fresh copy of the whole
echo   Sangala Blocks folder, and your designs will be unaffected.
goto :eof

REM ==========================================================================
:shortcut
REM  Put (or refresh) a "Sangala Blocks" icon on the Desktop, pointing at the
REM  program in THIS folder -- so the icon keeps working even after an update,
REM  and gets corrected if the folder has been moved.
REM  Pure convenience: it writes only to the user's own Desktop (no admin), and
REM  if anything goes wrong the update itself is still good, so this never
REM  changes the exit code. The paths travel as environment variables so folder
REM  names with spaces or apostrophes cannot break the quoting, and
REM  SpecialFolders finds the real Desktop even when OneDrive has redirected it.
if not exist "%~dp0%EXE%" goto :eof
set "SANGALA_HOME=%~dp0"
set "SANGALA_TARGET=%~dp0%EXE%"
powershell -NoProfile -Command "try { $ws = New-Object -ComObject WScript.Shell; $p = Join-Path $ws.SpecialFolders('Desktop') 'Sangala Blocks.lnk'; $l = $ws.CreateShortcut($p); $l.TargetPath = $env:SANGALA_TARGET; $l.WorkingDirectory = $env:SANGALA_HOME.TrimEnd('\'); $l.Description = 'Sangala Blocks - Block Design Tool'; $l.Save(); exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto :eof
echo.
echo   A "Sangala Blocks" icon is on your Desktop, ready to use.
goto :eof

REM ==========================================================================
:exelocked
echo.
echo Update ALMOST done - the page was updated, but the program file was still
echo in use and could not be replaced.
echo   1. Close Sangala Blocks completely (right-click its crane icon in the
echo      notification area, then Quit Sangala Blocks).
echo   2. Run this update again.
echo Your program still works in the meantime.
echo.
pause
exit /b 1

:badfile
del "%TMPHTML%" >nul 2>&1
del "%TMPEXE%"  >nul 2>&1
:failed
echo.
echo Update FAILED - could not download a complete copy.
echo Your current Sangala Blocks was NOT changed, so it still works.
echo Check the internet connection and run this again.
echo.
pause
exit /b 1
