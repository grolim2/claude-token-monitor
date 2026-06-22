@echo off
echo Instalando dependencias...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Compilando executavel...
pyinstaller --onefile --windowed --name "ClaudeTokenMonitor" --icon=NONE main.py

echo.
echo Pronto! O executavel esta em: dist\ClaudeTokenMonitor.exe
pause
