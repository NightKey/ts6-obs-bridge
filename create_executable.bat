@ECHO off
echo "Cleaning previous build"
if exist "dist\TeamSpeak-OBS-Bridge-App" rmdir /s /q "dist\TeamSpeak-OBS-Bridge-App"
if exist "dist\TeamSpeak-OBS-Bridge-App-Windows.zip" del "dist\TeamSpeak-OBS-Bridge-App-Windows.zip"

SET "INPUT_TAG=%~1"
SET "VERSION=0.0.0"
SET "BRANCH=unknown"

if "%INPUT_TAG%"=="" goto :skip_parsing

SET "TMP_TAG=%INPUT_TAG:v=%"

for /f "tokens=1,2 delims=-" %%A in ("%TMP_TAG%") do (
    SET "VERSION=%%A"
    SET "BRANCH=%%B"
)

:skip_parsing
echo Target version: %VERSION%-%BRANCH%

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
pyinstaller -y -n "TeamSpeak-OBS-Bridge-App" -D src\bridge.py --paths=.\modules || exit /b 1
pyinstaller -y -w -n "TeamSpeak-OBS-Bridge-App-Headless" -D src\bridge.py --paths=.\modules || exit /b 1

echo "Creating levels file"
mkdir "dist\TeamSpeak-OBS-Bridge-App\data" || exit /b 1
echo { > dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     "database": { >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "level": "INFO", >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "create_file": false >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     }, >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     "webui": { >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "level": "WARNING", >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "create_file": false >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     }, >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     "teamspeak": { >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "level": "INFO", >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "create_file": false >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     }, >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     "obs": { >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "level": "INFO", >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "create_file": false >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     }, >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     "bridge": { >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "level": "INFO", >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo         "create_file": false >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo     } >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo } >> dist\TeamSpeak-OBS-Bridge-App\data\log_settings || exit /b 1
echo %VERSION% > "dist\TeamSpeak-OBS-Bridge-App\data\version" || exit /b 1
echo %BRANCH%>> "dist\TeamSpeak-OBS-Bridge-App\data\version" || exit /b 1
copy "dist\TeamSpeak-OBS-Bridge-App\data\log_settings" "dist\TeamSpeak-OBS-Bridge-App-Headless\data\log_settings"
copy "dist\TeamSpeak-OBS-Bridge-App\data\version" "dist\TeamSpeak-OBS-Bridge-App-Headless\data\version"

echo "Creating WebUI folders"
mkdir "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\static" || exit /b 1
mkdir "dist\TeamSpeak-OBS-Bridge-App-Headless\_internal\modules\WebUI\static" || exit /b 1
mkdir "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\templates" || exit /b 1
mkdir "dist\TeamSpeak-OBS-Bridge-App-Headless\_internal\modules\WebUI\templates" || exit /b 1

echo "Copying WebUI assets"
robocopy "src\modules\WebUI\static" "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\static" /e /copy:DAT /r:0
robocopy "src\modules\WebUI\static" "dist\TeamSpeak-OBS-Bridge-App-Headless\_internal\modules\WebUI\static" /e /copy:DAT /r:0
robocopy "src\modules\WebUI\templates" "dist\TeamSpeak-OBS-Bridge-App\_internal\modules\WebUI\templates" /e /copy:DAT /r:0
robocopy "src\modules\WebUI\templates" "dist\TeamSpeak-OBS-Bridge-App-Headless\_internal\modules\WebUI\templates" /e /copy:DAT /r:0

echo "Copying readme pdf"
copy "dist\readme.pdf" "dist\TeamSpeak-OBS-Bridge-App\readme.pdf"
copy "dist\readme.pdf" "dist\TeamSpeak-OBS-Bridge-App-Headless\readme.pdf"

echo "Creating zip file"
cd dist
tar -a -cvf "TeamSpeak-OBS-Bridge-App-Windows.zip" "TeamSpeak-OBS-Bridge-App" || exit /b 1
tar -a -cvf "TeamSpeak-OBS-Bridge-App-Headless-Windows.zip" "TeamSpeak-OBS-Bridge-App" || exit /b 1
echo "Done"