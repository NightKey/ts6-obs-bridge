IF NOT EXIST venv\ (
    ECHO Venv doesn't exist, creating venv.
    python -m venv venv
)

IF "%VIRTUAL_ENV%"=="" (
    call venv\Scripts\activate.bat
)

echo "Upgrading dependencies"
call python -m pip install -r dependencies.txt --upgrade
call python -m test.main