@echo off
python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m spacy download en_core_web_sm
if not exist .env copy .env.example .env
python manage.py migrate
python manage.py load_cases
python manage.py build_index
echo.
echo Setup complete. Run run.bat to start MYSTIQ.
pause
