@echo off
rem Instala o SIM neste computador (uma vez). Requer Python 3.14 e internet.
cd /d "%~dp0"
echo === Instalacao do SIM ===
rem Pastas muito longas estouram o limite de caminho do Windows ao instalar as bibliotecas.
set "PASTA=%~dp0"
if not "%PASTA:~60,1%"=="" goto pasta_longa
set "PY="
py -3.14 --version >nul 2>&1 && set "PY=py -3.14"
if not defined PY python --version 2>nul | findstr /b /c:"Python 3.14" >nul && set "PY=python"
if not defined PY goto sem_python
if not exist ".venv\Scripts\python.exe" (
  echo Criando o ambiente .venv...
  %PY% -m venv .venv || goto erro
)
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto erro
echo Instalando as bibliotecas nas mesmas versoes do computador original...
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt || goto erro
echo Conferindo o banco de dados...
".venv\Scripts\python.exe" -m alembic upgrade head || goto erro
echo.
echo Instalacao concluida. Para abrir o SIM, de dois cliques em INICIAR_SIM.bat
pause
exit /b 0

:sem_python
echo Python 3.14 nao encontrado.
echo Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH" e rode este arquivo de novo.
pause
exit /b 1

:pasta_longa
echo Esta pasta tem um caminho longo demais para o Windows:
echo %PASTA%
echo Mova a pasta do SIM para um caminho curto, por exemplo C:\SIM, e rode este arquivo de novo.
pause
exit /b 1

:erro
echo.
echo A instalacao falhou. Veja a mensagem acima.
pause
exit /b 1
