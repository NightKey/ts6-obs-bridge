@ECHO off
SET main_dir=%~dp0
cd %main_dir%

IF NOT EXIST venv\ (
    ECHO Venv doesn't exist, creating venv.
    python -m venv venv
)

IF "%VIRTUAL_ENV%"=="" (
    call venv\Scripts\activate.bat
)

call python -m pip install -r dependencies.txt --upgrade
call python -m pip install pyinstaller
if exist ".\dist\TeamSpeak-OBS-Bridge" rmdir /s /q ".\dist\TeamSpeak-OBS-Bridge"
pyinstaller -w -n "TeamSpeak-OBS-Bridge-App" -F ./src/main.py --paths=./modules
mkdir ".\dist\TeamSpeak-OBS-Bridge"
move ".\dist\TeamSpeak-OBS-Bridge-App.exe" ".\dist\TeamSpeak-OBS-Bridge\TeamSpeak-OBS-Bridge-App.exe"
mkdir ".\dist\TeamSpeak-OBS-Bridge\data"
copy ".\src\data\levels" ".\dist\TeamSpeak-OBS-Bridge\data\levels"