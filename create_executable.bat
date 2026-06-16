@ECHO off
echo "Cleaning previous build"
if exist "dist\TeamSpeak-OBS-Bridge-App" rmdir /s /q "dist\TeamSpeak-OBS-Bridge-App"
if exist "dist\TeamSpeak-OBS-Bridge-App-Windows.zip" del "dist\TeamSpeak-OBS-Bridge-App-Windows.zip"

echo "Moving to newest state"
git stash
git fetch --all
git reset --hard

SET INPUT_TAG=%1
SET VERSION=0.0.0-unknown

:: Rough Batch parsing logic for vX.Y.Z-Stable -> X.Y.Z
IF NOT "%INPUT_TAG%"=="" (
    SET tmp1=%INPUT_TAG:v=%
    CALL SET VERSION=%%tmp1:-Stable=%%
)
echo Target version: %VERSION%

IF NOT EXIST venv\ (
    ECHO Venv doesn't exist, creating venv.
    python -m venv venv
)

IF "%VIRTUAL_ENV%"=="" (
    call venv\Scripts\activate.bat
)

echo "Upgrading dependencies"
call python -m pip install -r dependencies.txt --upgrade
call python -m pip install pyinstaller

echo "Building executable"
pyinstaller -n "TeamSpeak-OBS-Bridge-App" -D src\main.py --paths=.\modules

echo "Creating levels file"
mkdir "dist\TeamSpeak-OBS-Bridge-App\data"
echo {> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "database":"INFO",>> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "webui":"WARNING",>> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "teamspeak":"INFO",>> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "obs":"INFO",>> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo     "main":"INFO">> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo }>> dist\TeamSpeak-OBS-Bridge-App\data\levels
echo %VERSION% > "dist/TeamSpeak-OBS-Bridge-App/data/version"

echo "Creating WebUI folders"
mkdir "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\static"
mkdir "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\templates"

echo "Copying WebUI assets"
robocopy "src\modules\WebUI\static" "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\static" /e /copy:DAT /r:0
robocopy "src\modules\WebUI\templates" "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\templates" /e /copy:DAT /r:0

echo "Creating zip file"
cd dist
tar -a -cvf "TeamSpeak-OBS-Bridge-App-Windows.zip" "TeamSpeak-OBS-Bridge-App"

git stash pop
git stash clear
echo "Done"