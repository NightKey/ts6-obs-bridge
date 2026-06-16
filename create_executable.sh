echo "Cleaning previous build"
rm -f "dist/TeamSpeak-OBS-Bridge-App-Linux.tar.gz"
rm -rf "dist/TeamSpeak-OBS-Bridge-App"

echo "Moving to newest state"
git stash
git fetch --all
git reset --hard

RE="v([0-9]+\.[0-9]+\.[0-9]+)(-|)([a-zA-Z]+|)"
VERSION=""
BRANCH=""
if [[ $1 =~ $RE ]]; then
  VERSION=${BASH_REMATCH[1]}
  BRANCH=${BASH_REMATCH[3]}
fi
echo "Target version: $VERSION-$BRANCH"

if ! [ -d venv ]
then
  echo "venv doesn't exist, creating venv."
    python3 -m virtualenv venv
fi

if [[ "$VIRTUAL_ENV" = "" ]]
then
    source venv/bin/activate
fi

echo "Upgrading dependencies"
pip install -r dependencies.txt --upgrade
pip install pyinstaller

echo "Building executable"
pyinstaller -n "TeamSpeak-OBS-Bridge-App" -D src/main.py --paths=./modules

echo "Creating levels file"
mkdir "dist/TeamSpeak-OBS-Bridge-App/data"
cat << 'EOF' > dist/TeamSpeak-OBS-Bridge-App/data/levels
{
    "database":"INFO",
    "webui":"WARNING",
    "teamspeak":"INFO",
    "obs":"INFO",
    "main":"INFO"
}
EOF
echo "$VERSION
$BRANCH" > "dist/TeamSpeak-OBS-Bridge-App/data/version"

echo "Creating WebUI folders"
mkdir -p "./dist/TeamSpeak-OBS-Bridge-App/_internal/modules/WebUI"

echo "Copying WebUI assets"
cp -r "src/modules/WebUI/static" "dist/TeamSpeak-OBS-Bridge-App/_internal/modules/WebUI/static"
cp -r "src/modules/WebUI/templates" "dist/TeamSpeak-OBS-Bridge-App/_internal/modules/WebUI/templates"

echo "Creating tar.gz file"
tar -czvf "dist/TeamSpeak-OBS-Bridge-App-Linux.tar.gz" "dist/TeamSpeak-OBS-Bridge-App"
git stash pop
git stash clear
echo "Done"