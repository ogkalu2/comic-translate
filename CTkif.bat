@echo off
:: Cambia directory al percorso del file se necessario
cd /d "%~dp0"

:: Avvia il file Python comic.py
python comic.py

:: Mantieni la finestra aperta in caso di errore
pause