@echo off
setlocal enabledelayedexpansion

REM add + commit + push helper for Git CMD on Windows.

git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  echo Error: no estas dentro de un repositorio Git.
  exit /b 2
)

set "MSG=%*"
if "%MSG%"=="" (
  echo Uso: acp "mensaje del commit"
  exit /b 2
)

git add -A
if errorlevel 1 exit /b %errorlevel%

git diff --cached --quiet
if not errorlevel 1 (
  echo No hay cambios para commitear.
  exit /b 0
)

git commit -m "%MSG%"
if errorlevel 1 exit /b %errorlevel%

git push
exit /b %errorlevel%

