import os
import time
import shutil
from django.conf import settings
from django.core.management.base import (BaseCommand, CommandError)
from subprocess import Popen, PIPE, list2cmdline


def gen_name(ext):
    return 'db.%s.%s' % (time.strftime('%Y-%m-%d'), ext)


def sqlite_db_backup(db_name, out_path):
    if os.path.isfile(db_name):
        # backup the latest database, eg to: `db.2017-02-29.sqlite3`
        shutil.copyfile(db_name, out_path)
        return True
    return False


def mysql_db_backup(db_settings, out_path):
    username = db_settings['USER']
    password = db_settings['PASSWORD']
    database = db_settings['NAME']
    host = db_settings['HOST']
    port = db_settings['PORT']

    cmd = ['mysqldump',
           '-h', host, '-P', port,
           '-u', username, '-p%s' % password,
           '--no-create-info', '--skip-add-drop-table',
           database]

    p = Popen(list2cmdline(cmd),
              stdout=PIPE, stderr=PIPE,
              universal_newlines=True,
              shell=True)
    stdout, stderr = p.communicate()

    if stderr:
        return False

    with open(out_path, 'w', encoding='utf-8') as output_file:
        output_file.write(stdout.strip())

    return True


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
        elif not os.path.isdir(dir_path):
            return self.error_info("The backup directory doesn't exist!")

        DB_SETTINGS = settings.DATABASES[database]

        if settings.DATABASES[database]['ENGINE'] == 'django.db.backends.sqlite3':
            backup_database_path = os.path.join(dir_path, gen_name('sqlite3'))
            sqlite_db_backup(DB_SETTINGS['NAME'], backup_database_path)
        elif settings.DATABASES[database]['ENGINE'] == 'django.db.backends.mysql':
            backup_database_path = os.path.join(dir_path, gen_name('sql'))
            mysql_db_backup(DB_SETTINGS, backup_database_path)
        else:
            return self.error_info("This script backs up sqlite/mysql databases only!")

        if backup_database_path:
            self.success_info("[+] Backup the database `%s` to %s" % (DB_SETTINGS['NAME'], backup_database_path))
        else:
            self.error_info("Database %s not found" % DB_SETTINGS['NAME'])
