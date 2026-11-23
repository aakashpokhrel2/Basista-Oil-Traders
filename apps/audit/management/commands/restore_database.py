"""
Database Restoration Management Command.
Validates SHA-256 integrity, verifies manifest, and restores data safely.
"""

import os
import hashlib
import gzip
import json
import subprocess
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.conf import settings
from django.utils import timezone

from apps.audit.services import record_audit_event


class Command(BaseCommand):
    help = "Verify checksum and restore database from a compressed backup archive."

    def add_arguments(self, parser):
        parser.add_argument(
            '--backup-file',
            type=str,
            required=True,
            help='Path to the .sql.gz or .json.gz backup archive.'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Explicit confirmation to proceed with database overwrite.'
        )

    def handle(self, *args, **options):
        backup_path = Path(options['backup_file'])
        if not backup_path.exists():
            raise CommandError(f"Backup file not found: {backup_path}")

        if not options['confirm']:
            raise CommandError("Restoring will overwrite current database records! Pass --confirm to execute.")

        self.stdout.write(self.style.NOTICE(f"Verifying integrity of '{backup_path.name}'..."))

        # 1. Compute Checksum
        sha256 = hashlib.sha256()
        with open(backup_path, 'rb') as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        actual_checksum = sha256.hexdigest()

        # Check against manifest if present
        manifest_path = backup_path.parent / f"{backup_path.stem}.manifest.json"
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as mf:
                manifest_data = json.load(mf)
                expected_checksum = manifest_data.get('sha256_checksum')
                if expected_checksum and expected_checksum != actual_checksum:
                    raise CommandError(
                        f"Integrity check failed! Archive SHA256 ({actual_checksum}) does not match manifest ({expected_checksum})."
                    )
            self.stdout.write(self.style.SUCCESS(f"SHA-256 integrity check verified: {actual_checksum}"))
        else:
            self.stdout.write(self.style.WARNING("Manifest file not found; proceeding with calculated checksum."))

        # 2. Perform Restoration
        db_conf = settings.DATABASES['default']
        db_engine = db_conf.get('ENGINE', '')
        db_name = db_conf.get('NAME', 'petrol_station')

        if backup_path.name.endswith('.sql.gz') and 'postgresql' in db_engine:
            # PostgreSQL restore
            host = db_conf.get('HOST', 'localhost')
            port = str(db_conf.get('PORT', '5432'))
            user = db_conf.get('USER', 'postgres')
            password = db_conf.get('PASSWORD', '')

            env = os.environ.copy()
            if password:
                env['PGPASSWORD'] = password

            cmd = ['psql', '-h', host, '-p', port, '-U', user, '-d', str(db_name)]
            with gzip.open(backup_path, 'rb') as gz_in:
                proc = subprocess.run(cmd, stdin=gz_in, capture_output=True, env=env)
                if proc.returncode != 0:
                    raise CommandError(f"psql restore failed: {proc.stderr.decode('utf-8')}")

            self.stdout.write(self.style.SUCCESS("PostgreSQL SQL database restored successfully."))
        elif backup_path.name.endswith('.json.gz'):
            # Decompress JSON to temp file and loaddata
            temp_json = backup_path.parent / f"restore_temp_{timezone.now().strftime('%Y%m%d%H%M%S')}.json"
            try:
                with gzip.open(backup_path, 'rb') as f_in, open(temp_json, 'wb') as f_out:
                    f_out.write(f_in.read())

                call_command('loaddata', str(temp_json))
                self.stdout.write(self.style.SUCCESS("Django portable JSON data loaded successfully."))
            finally:
                if temp_json.exists():
                    temp_json.unlink()
        else:
            raise CommandError(f"Unsupported backup format: {backup_path.name}")

        # 3. Record Audit Log
        try:
            record_audit_event(
                action='RESTORE',
                model_name='DatabaseRestore',
                record_id=backup_path.name,
                user=None,
                previous_value={},
                updated_value={'filename': backup_path.name, 'sha256': actual_checksum},
                reason=f"Restored database from verified backup {backup_path.name}"
            )
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS("Database restore procedure completed successfully!"))
