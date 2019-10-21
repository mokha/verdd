from django.core.management.base import BaseCommand, CommandError
import os
import time
import shutil
from django.conf import settings
from django.core.management.base import (BaseCommand, CommandError)


class Command(BaseCommand):
    '''
    Example: python manage.py database_backup -d default -p ../backup
    Note: Using sqlite .backup API would be better to prevent an injury (e.g. https://www.zzzzzzzzz.net/daily-backup-sqlite3-database-shell-script/).
    However, this is a simpler method.
    '''

    help = 'Command to deploy and backup the latest database.'

    def add_arguments(self, parser):
        parser.add_argument('-d', '--database', type=str, help='The name of the database to backup.')
        parser.add_argument('-p', '--path', type=str, help='The directory to store the backed up database in.', )

    def success_info(self, info):
        return self.stdout.write(self.style.SUCCESS(info))

    def error_info(self, info):
        return self.stdout.write(self.style.ERROR(info))

    def handle(self, *args, **options):
        database = options['database']
        dir_path = options['path']

        if not database or not dir_path:
            return self.print_help()
        elif database not in settings.DATABASES:
            return self.error_info('Database %s not found in the configuration!' % database)
        elif settings.DATABASES[database]['ENGINE'] != 'django.db.backends.sqlite3':
            return self.error_info("This script backs up sqlite databases only!")
        elif not os.path.isdir(dir_path):
            return self.error_info("The backup directory doesn't exist!")

        DATABASE_NAME = settings.DATABASES[database]['NAME']

        if os.path.isfile(DATABASE_NAME):
            # backup the latest database, eg to: `db.2017-02-29.sqlite3`
            backup_database = 'db.%s.sqlite3' % time.strftime('%Y-%m-%d')
            backup_database_path = os.path.join(dir_path, backup_database)
            shutil.copyfile(DATABASE_NAME, backup_database_path)
            self.success_info("[+] Backup the database `%s` to %s" % (DATABASE_NAME, backup_database_path))
        else:
            self.error_info("Database %s not found" % DATABASE_NAME)
