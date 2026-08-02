set -e
echo "Cleaning previous build"
rm -f "dist/TeamSpeak-OBS-Bridge-App-Linux.tar.gz"
rm -rf "dist/TeamSpeak-OBS-Bridge-App"

RE="v([0-9]+\.[0-9]+\.[0-9]+)(-|)([a-zA-Z]+|)"
VERSION=""
BRANCH=""
if [[ $1 =~ $RE ]]; then
  VERSION=${BASH_REMATCH[1]}
  BRANCH=${BASH_REMATCH[3]}
fi
echo "Target version: $VERSION-$BRANCH"

echo "Upgrading dependencies"
pip install -r dependencies.txt --upgrade
pip install pyinstaller

echo "Building executable"
pyinstaller -n "TeamSpeak-OBS-Bridge-App" -D src/bridge.py --paths=./modules
pyinstaller -n -w "TeamSpeak-OBS-Bridge-App-Headless" -D src/bridge.py --paths=./modules

echo "Creating levels file"
mkdir "dist/TeamSpeak-OBS-Bridge-App/data"
mkdir "dist/TeamSpeak-OBS-Bridge-App-Headless/data"
echo "{
    \"database\": {
        \"level\": \"INFO\",
        \"create_file\": false
    },
    \"webui\": {
        \"level\": \"WARNING\",
        \"create_file\": false
    },
    \"teamspeak\": {
        \"level\": \"INFO\",
        \"create_file\": false
    },
    \"obs\": {
        \"level\": \"INFO\",
        \"create_file\": false
    },
    \"bridge\": {
        \"level\": \"INFO\",
        \"create_file\": false
    }
}" > dist/TeamSpeak-OBS-Bridge-App/data/log_settings
cp "dist/TeamSpeak-OBS-Bridge-App/data/log_settings" "dis/TeamSpeak-OBS-Bridge-App-Headless/data/log_settings"
echo "$VERSION
$BRANCH" > "dist/TeamSpeak-OBS-Bridge-App/data/version"
cp "dist/TeamSpeak-OBS-Bridge-App/data/version" "dis/TeamSpeak-OBS-Bridge-App-Headless/data/version"

echo "Creating WebUI folders"
mkdir -p "./dist/TeamSpeak-OBS-Bridge-App/_internal/modules/WebUI"
mkdir -p "./dist/TeamSpeak-OBS-Bridge-App-Headless/_internal/modules/WebUI"

echo "Copying WebUI assets"
cp -r "src/modules/WebUI/static" "dist/TeamSpeak-OBS-Bridge-App/_internal/modules/WebUI/static"
cp -r "src/modules/WebUI/static" "dist/TeamSpeak-OBS-Bridge-App-Headless/_internal/modules/WebUI/static"
cp -r "src/modules/WebUI/templates" "dist/TeamSpeak-OBS-Bridge-App/_internal/modules/WebUI/templates"
cp -r "src/modules/WebUI/templates" "dist/TeamSpeak-OBS-Bridge-App-Headless/_internal/modules/WebUI/templates"

echo "Converting to pdf"
pandoc README.md -o dist/readme.pdf --pdf-engine=weasyprint --metadata title="TeamSpeak6-OBS Bridge"

echo "Copying pdf"
cp "dist/readme.pdf" "dist/TeamSpeak-OBS-Bridge-App/readme.pdf"
cp "dist/readme.pdf" "dist/TeamSpeak-OBS-Bridge-App-Headless/readme.pdf"

echo "Creating tar.gz file"
tar -czvf "dist/TeamSpeak-OBS-Bridge-App-Linux.tar.gz" "dist/TeamSpeak-OBS-Bridge-App"
tar -czvf "dist/TeamSpeak-OBS-Bridge-App-Headless-Linux.tar.gz" "dist/TeamSpeak-OBS-Bridge-App-Headless"
echo "Done"
