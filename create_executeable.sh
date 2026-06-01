if ! [ -d venv ]
then
  echo "venv doesn't exist, creating venv."
    python3 -m virtualenv venv
fi

#If not in venv, activate venv.
if [[ "$VIRTUAL_ENV" = "" ]]
then
    source venv/bin/activate
fi

pip install -r dependencies.txt --upgrade
pip install pyinstaller
rm -rf "dist/TeamSpeak-OBS-Bridge-App"
pyinstaller -n "TeamSpeak-OBS-Bridge-App" -D src/main.py --paths=./modules
mkdir "dist/TeamSpeak-OBS-Bridge-App/data"
cp "src/data/levels" "dist/TeamSpeak-OBS-Bridge-App/data/levels"
mkdir -p "./dist/TeamSpeak-OBS-Bridge-App/_internal/modules/WebUI"
cp -r "src/modules/WebUI/static" "dist/TeamSpeak-OBS-Bridge-App/_internal/modules/WebUI/static"
cp -r "src/modules/WebUI/templates" "dist/TeamSpeak-OBS-Bridge-App/_internal/modules/WebUI/templates"
rm "dist/TeamSpeak-OBS-Bridge-App-Linux.tar.gz"
tar -czvf "dist/TeamSpeak-OBS-Bridge-App-Linux.tar.gz" "dist/TeamSpeak-OBS-Bridge-App"