@echo off
rem Abre o SIM neste computador em http://127.0.0.1:8501 (so este computador acessa).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo O SIM ainda nao foi instalado neste computador. Rode primeiro INSTALAR.bat
  pause
  exit /b 1
)
echo Abrindo o SIM. Mantenha esta janela aberta enquanto usar o sistema.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless false
pause
