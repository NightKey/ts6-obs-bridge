pip install -r dependencies.txt --upgrade > pip.txt
pip install pyinstaller

echo "Upgrading dependencies"
python -m pip install -r dependencies.txt --upgrade

python test/main.py
pytest test/