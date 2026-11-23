"""
Automated Database Backup Management Command.
Supports PostgreSQL (pg_dump) & portable compressed JSON dumps with SHA-256 checksums,
off-site replication, retention policy pruning, and security audit trail logging.
"""

import os
import shutil
import hashlib
import gzip
import json
import datetime
import subprocess
from pathlib import Path
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
from django.utils import timezone

from apps.audit.services import record_audit_event


class Command(BaseCommand):
    help = "Generate a verified, compressed database backup with retention rotation."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default=str(settings.BASE_DIR / 'backups' / 'local'),
            help='Local directory path to store database backups.'
        )
        parser.add_argument(
            '--offsite-dir',
            type=str,
            default=str(settings.BASE_DIR / 'backups' / 'offsite'),
            help='Secondary off-site / external mount directory for replicated backups.'
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=7,
            help='Number of daily backups to retain before pruning (default: 7).'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json_gz', 'sql_gz', 'auto'],
            default='auto',
            help='Backup archive format (default: auto).'
        )

    def handle(self, *args, **options):
        output_dir = Path(options['output_dir'])
        offsite_dir = Path(options['offsite_dir']) if options['offsite_dir'] else None
        keep_days = options['keep_days']
        fmt = options['format']

        output_dir.mkdir(parents=True, exist_ok=True)
        if offsite_dir:
            offsite_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = timezone.now().strftime('%Y%m%d_%H%M%S')
        db_conf = settings.DATABASES['default']
        db_engine = db_conf.get('ENGINE', '')
        db_name = db_conf.get('NAME', 'petrol_station')

        self.stdout.write(self.style.NOTICE(f"Initiating backup for database '{db_name}' ({db_engine})..."))

        # Determine backup strategy
        is_postgres = 'postgresql' in db_engine
        use_sql = (fmt == 'sql_gz') or (fmt == 'auto' and is_postgres)

        backup_file = None

        if use_sql and is_postgres:
            # PostgreSQL pg_dump
            sql_file = output_dir / f"db_backup_{timestamp_str}.sql.gz"
            host = db_conf.get('HOST', 'localhost')
            port = str(db_conf.get('PORT', '5432'))
            user = db_conf.get('USER', 'postgres')
            password = db_conf.get('PASSWORD', '')

            env = os.environ.copy()
            if password:
                env['PGPASSWORD'] = password

            cmd = [
                'pg_dump',
                '-h', host,
                '-p', port,
                '-U', user,
                '-d', db_name,
                '--clean',
                '--if-exists'
            ]
            try:
                with gzip.open(sql_file, 'wb') as gz_out:
                    proc = subprocess.run(cmd, stdout=gz_out, stderr=subprocess.PIPE, env=env, check=True)
                backup_file = sql_file
                self.stdout.write(self.style.SUCCESS(f"PostgreSQL pg_dump completed: {backup_file.name}"))
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                self.stdout.write(self.style.WARNING(f"pg_dump failed or not found ({e}). Falling back to portable JSON dump."))
                if sql_file.exists():
                    sql_file.unlink()
                use_sql = False

        if not backup_file:
            # Portable Django JSON dump (Works for both PostgreSQL and SQLite, platform-independent)
            json_gz_file = output_dir / f"db_backup_{timestamp_str}.json.gz"
            temp_json = output_dir / f"temp_{timestamp_str}.json"
            with open(temp_json, 'w', encoding='utf-8') as f:
                call_command(
                    'dumpdata',
                    exclude=['contenttypes', 'auth.permission', 'sessions', 'audit.auditlog'],
                    natural_foreign=True,
                    natural_primary=True,
                    indent=2,
                    stdout=f
                )

            with open(temp_json, 'rb') as f_in, gzip.open(json_gz_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

            if temp_json.exists():
                temp_json.unlink()

            backup_file = json_gz_file
            self.stdout.write(self.style.SUCCESS(f"Compressed portable JSON dump created: {backup_file.name}"))

        # Calculate SHA-256 Checksum
        sha256 = hashlib.sha256()
        with open(backup_file, 'rb') as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        checksum = sha256.hexdigest()
        file_size_bytes = backup_file.stat().st_size

        # Write manifest file
        manifest_data = {
            'timestamp': timezone.now().isoformat(),
            'filename': backup_file.name,
            'size_bytes': file_size_bytes,
            'sha256_checksum': checksum,
            'database_engine': db_engine,
            'database_name': str(db_name),
            'station': getattr(settings, 'STATION_NAME_EN', 'Basista Oil Traders'),
        }
        manifest_file = output_dir / f"{backup_file.stem}.manifest.json"
        with open(manifest_file, 'w', encoding='utf-8') as mf:
            json.dump(manifest_data, mf, indent=2)

        # Off-site replication if configured
        if offsite_dir:
            offsite_backup = offsite_dir / backup_file.name
            offsite_manifest = offsite_dir / manifest_file.name
            shutil.copy2(backup_file, offsite_backup)
            shutil.copy2(manifest_file, offsite_manifest)
            self.stdout.write(self.style.SUCCESS(f"Replicated to off-site location: {offsite_dir}"))

        # Retention Policy Pruning
        self.prune_old_backups(output_dir, keep_days)
        if offsite_dir:
            self.prune_old_backups(offsite_dir, keep_days)

        # Log security audit event
        try:
            record_audit_event(
                action='BACKUP',
                model_name='DatabaseBackup',
                record_id=backup_file.name,
                user=None,
                previous_value={},
                updated_value={
                    'filename': backup_file.name,
                    'size_bytes': file_size_bytes,
                    'sha256': checksum
                },
                reason=f"Automated verified database backup ({file_size_bytes} bytes)"
            )
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS(
            f"Backup complete!\n"
            f"File: {backup_file}\n"
            f"Size: {file_size_bytes:,} bytes\n"
            f"SHA256: {checksum}"
        ))

    def prune_old_backups(self, directory: Path, keep_days: int):
        """Remove backup archives older than keep_days."""
        cutoff = timezone.now() - datetime.timedelta(days=keep_days)
        for item in directory.glob('db_backup_*'):
            if item.is_file():
                mtime = datetime.datetime.fromtimestamp(item.stat().st_mtime, tz=datetime.timezone.utc)
                if mtime < cutoff:
                    item.unlink()
                    self.stdout.write(self.style.NOTICE(f"Pruned expired backup: {item.name}"))
