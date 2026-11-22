@echo off
call venv\Scripts\activate
python manage.py test tests
python manage.py evaluate_nlp
pause
