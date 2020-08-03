
### Setup commands
````sh
python manage.py makemigrations
python manage.py migrate
python manage.py makemessages -l 'fi'
python manage.py compilemessages # add -f to ignore ",fuzzy" cases in .PO file
python manage.py createsuperuser
python manage.py collectstatic
python manage.py runserver
````

````python
from uralicNLP import uralicApi
uralicApi.download("sms")
uralicApi.download("fin")
````
#### To load language fixtures:
````sh
python manage.py loaddata languages_data
````

#### For development
````
cp dev.env .env
````

When running the above commands in development, pass the following parameters to the `manage.py`:
` `


sudo ln -s FULLPATH/verdd/verdd.service /etc/systemd/system/
sudo ln -s FULLPATH/verdd/verdd.ini /etc/uwsgi/apps-available/

#### For daily backups
``
crontab -e

# Run verdd backup every day at 2:00 am
0 2 * * * /www/verdd/venv/bin/python3.5 /www/verdd/manage.py database_backup -d default -p /www/verdd_db_bk/ --settings verdd.settings.development