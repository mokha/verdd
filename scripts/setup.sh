#!/bin/bash
echo -n MySQL Username:
read mysql_user
echo -n MySQL Password:
read -s mysql_password
echo -n MySQL DB:
read database_name
echo

### Setup MySQL DB
# drop existing DB
mysql --user="$mysql_user" --password="$mysql_password" --database="$database_name" --execute="DROP DATABASE IF EXISTS $database_name;"
# create new DB
mysql --user="$mysql_user" --password="$mysql_password" --database="$database_name" --execute="CREATE DATABASE $database_name DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_bin;"
# drop existing DB
mysql --user="$mysql_user" --password="$mysql_password" --database="$database_name" --execute="GRANT ALL PRIVILEGES ON $database_name.* TO '$mysql_user'@'localhost';"

### Setup Ve'rdd
python manage.py migrate         # install migrations
python manage.py compilemessages # compile localization messages
python manage.py collectstatic   # collect static files
python manage.py createsuperuser # create admin account
