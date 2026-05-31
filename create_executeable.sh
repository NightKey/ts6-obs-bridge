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
rm -rf "./dist/TeamSpeak-OBS-Bridge"
pyinstaller -w -n "TeamSpeak-OBS-Bridge-App" -F ./src/main.py --paths=./modules
mkdir "./dist/TeamSpeak-OBS-Bridge"
mv "./dist/TeamSpeak-OBS-Bridge-App" "./dist/TeamSpeak-OBS-Bridge/TeamSpeak-OBS-Bridge-App"
mkdir "./dist/TeamSpeak-OBS-Bridge/data"
cp "./src/data/levels" "./dist/TeamSpeak-OBS-Bridge/data/levels"