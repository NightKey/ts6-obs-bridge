@ECHO off
git stash
git reset --hard

IF NOT EXIST venv\ (
    ECHO Venv doesn't exist, creating venv.
    python -m venv venv
)

IF "%VIRTUAL_ENV%"=="" (
    call venv\Scripts\activate.bat
)

call python -m pip install -r dependencies.txt --upgrade
call python -m pip install pyinstaller
if exist "dist\TeamSpeak-OBS-Bridge-App" rmdir /s /q "dist\TeamSpeak-OBS-Bridge-App"
pyinstaller -n "TeamSpeak-OBS-Bridge-App" -D src\main.py --paths=.\modules
mkdir "dist\TeamSpeak-OBS-Bridge-App\data"
echo {> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "database":"INFO",>> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "webui":"WARNING",>> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "teamspeak":"INFO",>> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "obs":"INFO",>> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "main":"INFO">> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo }>> dist\TeamSpeak-OBS-Bridge-App\data\levels
mkdir "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\static"
mkdir "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\templates"
robocopy "src\modules\WebUI\static" "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\static" /e /copyall /r:0
robocopy "src\modules\WebUI\templates" "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\templates" /e /copyall /r:0
del "dist\TeamSpeak-OBS-Bridge-App-Windows.zip"
cd dist
tar -a -cvf "TeamSpeak-OBS-Bridge-App-Windows.zip" "TeamSpeak-OBS-Bridge-App"
git stash pop
git stash clear