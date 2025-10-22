@echo off
REM Vai para a pasta do bot
cd "C:\Users\Ana\Desktop\Compiuter\Discord Bots\pin_controller\Pin Controller"

REM Ativa a venv
call .venv\Scripts\activate.bat

REM Roda o bot em segundo plano sem abrir o terminal
"C:\Users\Ana\Desktop\Compiuter\Discord Bots\pin_controller\Pin Controller\.venv\Scripts\pythonw.exe" pincontroller.py
