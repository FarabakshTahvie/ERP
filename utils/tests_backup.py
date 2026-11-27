import io
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from botocore.exceptions import ClientError
from boto3.exceptions import S3UploadFailedError
from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings

from utils import db_backup


class FakeS3:
    """S3 درون‌حافظه‌ای فقط برای تست؛ شبکه ندارد."""
    def __init__(self, objects=None, extra_size=0, upload_error=None):
        self.objects = dict(objects or {})
        self.extra_size = extra_size          # شبیه‌سازی ناهمخوانی حجم
        self.upload_error = upload_error
        self.deleted, self.calls = [], []

    def upload_file(self, filename, bucket, key, ExtraArgs=None, Config=None):
        self.calls.append(("upload", key))
        if self.upload_error:
            raise self.upload_error
        self.objects[key] = Path(filename).read_bytes()

    def head_object(self, Bucket, Key):
        return {"ContentLength": len(self.objects[Key]) + self.extra_size}

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)
        self.objects.pop(Key, None)

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}

    def download_file(self, Bucket, Key, Filename):
        Path(Filename).write_bytes(self.objects[Key])

    def get_paginator(self, name):
        outer = self

        class _Pages:
            def paginate(self, Bucket, Prefix=""):
                return [{"Contents": [{"Key": k, "Size": len(v)} for k, v in sorted(outer.objects.items())
                                      if k.startswith(Prefix)]}]
        return _Pages()


def fake_run_factory(record, dump_rc=0, restore_rc=0, dump_bytes=b"PGDMP-test"):
    def fake_run(cmd, **kw):
        record.append((cmd, kw))
        if cmd[0] == "pg_dump":
            if dump_rc == 0:
                Path(cmd[cmd.index("--file") + 1]).write_bytes(dump_bytes)
            return SimpleNamespace(returncode=dump_rc, stderr="boom" if dump_rc else "")
        return SimpleNamespace(returncode=restore_rc, stderr="bad toc" if restore_rc else "")
    return fake_run


CLOUD_SETTINGS = {
    "BACKUP_CLOUD_ACCESS_KEY": "k",
    "BACKUP_CLOUD_SECRET_KEY": "s",
    "BACKUP_CLOUD_BUCKET": "bk",
    "BACKUP_CLOUD_ENDPOINT": "https://x.test",
}


class DbBackupPlanTests(SimpleTestCase):
    def test_local_window_counts_back_from_newest_backup(self):
        names = [f"db-202011{day:02d}-0230.dump" for day in range(10, 29)]
        doomed = db_backup.plan_local_prune(names, 14)
        self.assertEqual(doomed, [f"db-202011{day:02d}-0230.dump" for day in range(10, 15)])
        self.assertNotIn("db-20201115-0230.dump", doomed)

    def test_local_newest_is_never_planned_even_when_backups_stopped_long_ago(self):
        names = [f"db-202001{day:02d}-0230.dump" for day in range(1, 6)]
        for keep_days in range(1, 31):
            doomed = db_backup.plan_local_prune(names, keep_days)
            self.assertNotIn("db-20200105-0230.dump", doomed)

    def test_local_ignores_foreign_and_invalid_names(self):
        names = [
            "notes.txt",
            "db-bad.dump",
            "db-20201340-0101.dump",
            "db-20200101-0000.dump.part",
            "db-20200120-0230.dump",
        ]
        doomed = db_backup.plan_local_prune(names, 1)
        self.assertEqual(doomed, [])

    def test_cloud_keeps_newest_file_of_each_of_the_two_newest_days(self):
        keys = [
            "database/db-20200125-0230.dump",
            "database/db-20200126-0230.dump",
            "database/db-20200127-0230.dump",
            "database/db-20200127-0900.dump",
            "database/db-20200128-0230.dump",
            "database/db-20200128-0900.dump",
        ]
        doomed = db_backup.plan_cloud_prune(keys, 2)
        self.assertEqual(
            doomed,
            [
                "database/db-20200125-0230.dump",
                "database/db-20200126-0230.dump",
                "database/db-20200127-0230.dump",
                "database/db-20200128-0230.dump",
            ],
        )

    def test_cloud_ignores_foreign_keys(self):
        keys = [
            "database/_check/x.txt",
            "database/old/db-20200101-0000.dump",
            "other/db-20200101-0000.dump",
            "database/readme.txt",
            "database/db-20200120-0230.dump",
        ]
        doomed = db_backup.plan_cloud_prune(keys, 1)
        self.assertEqual(doomed, [])

    def test_keep_days_below_one_is_refused(self):
        with self.assertRaises(ValueError):
            db_backup.plan_local_prune(["db-20200101-0230.dump"], 0)
        with self.assertRaises(ValueError):
            db_backup.plan_cloud_prune(["database/db-20200101-0230.dump"], 0)


class DbBackupDumpTests(SimpleTestCase):
    PG_DB = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "n",
        "USER": "u",
        "PASSWORD": "secret",
        "HOST": "h",
        "PORT": 5432,
    }
    FIXED_NOW = datetime(2020, 1, 2, 2, 30)

    def test_dump_command_hides_password_and_publishes_final_file(self):
        rec = []
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("utils.db_backup.subprocess.run", side_effect=fake_run_factory(rec)):
                out = db_backup.dump_database(tmp, db=self.PG_DB, now=self.FIXED_NOW)
            self.assertEqual(out.name, "db-20200102-0230.dump")
            self.assertTrue(out.is_file())
            self.assertFalse(out.with_name(out.name + ".part").exists())
            dump_cmd, dump_kw = rec[0]
            self.assertEqual(dump_cmd[0], "pg_dump")
            self.assertIn("--format=custom", dump_cmd)
            self.assertIn("--compress=6", dump_cmd)
            self.assertTrue(all("secret" not in arg for arg in dump_cmd))
            self.assertEqual(dump_kw["env"]["PGPASSWORD"], "secret")
            restore_cmd, _ = rec[1]
            self.assertEqual(restore_cmd[:2], ["pg_restore", "--list"])

    def test_pg_dump_failure_leaves_no_file_and_keeps_old_backups(self):
        rec = []
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "db-20200101-0230.dump"
            old.write_bytes(b"old")
            part = Path(tmp) / "db-20200102-0230.dump.part"
            part.write_bytes(b"partial")
            with mock.patch("utils.db_backup.subprocess.run", side_effect=fake_run_factory(rec, dump_rc=1)):
                with self.assertRaises(db_backup.BackupError):
                    db_backup.dump_database(tmp, db=self.PG_DB, now=self.FIXED_NOW)
            self.assertFalse((Path(tmp) / "db-20200102-0230.dump").exists())
            self.assertFalse(part.exists())
            self.assertTrue(old.is_file())

    def test_unreadable_dump_is_refused(self):
        rec = []
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("utils.db_backup.subprocess.run", side_effect=fake_run_factory(rec, restore_rc=1)):
                with self.assertRaises(db_backup.BackupError):
                    db_backup.dump_database(tmp, db=self.PG_DB, now=self.FIXED_NOW)
            self.assertFalse((Path(tmp) / "db-20200102-0230.dump").exists())
            self.assertFalse((Path(tmp) / "db-20200102-0230.dump.part").exists())

    def test_empty_dump_is_refused(self):
        rec = []
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("utils.db_backup.subprocess.run", side_effect=fake_run_factory(rec, dump_bytes=b"")):
                with self.assertRaises(db_backup.BackupError):
                    db_backup.dump_database(tmp, db=self.PG_DB, now=self.FIXED_NOW)
            self.assertFalse((Path(tmp) / "db-20200102-0230.dump").exists())
            self.assertFalse((Path(tmp) / "db-20200102-0230.dump.part").exists())

    def test_non_postgres_database_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(db_backup.BackupError):
                db_backup.dump_database(
                    tmp,
                    db={"ENGINE": "django.db.backends.sqlite3", "NAME": "db.sqlite3"},
                    now=self.FIXED_NOW,
                )

    def test_existing_file_with_same_name_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "db-20200102-0230.dump"
            target.write_bytes(b"keep-me")
            with self.assertRaises(db_backup.BackupError):
                db_backup.dump_database(tmp, db=self.PG_DB, now=self.FIXED_NOW)
            self.assertEqual(target.read_bytes(), b"keep-me")

    def test_prune_local_removes_only_old_matching_files_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("db-20200101-0230.dump", "db-20200102-0230.dump", "db-20200103-0230.dump", "notes.txt"):
                (root / name).write_bytes(b"x")
            deleted = db_backup.prune_local(root, 2)
            self.assertEqual(deleted, ["db-20200101-0230.dump"])
            self.assertFalse((root / "db-20200101-0230.dump").exists())
            self.assertTrue((root / "db-20200102-0230.dump").exists())
            self.assertTrue((root / "db-20200103-0230.dump").exists())
            self.assertTrue((root / "notes.txt").exists())


@override_settings(**CLOUD_SETTINGS)
class DbBackupCloudTests(SimpleTestCase):
    def test_upload_verifies_size_then_keeps_two_newest_days(self):
        fake = FakeS3({
            "database/db-20200125-0230.dump": b"1",
            "database/db-20200126-0230.dump": b"2",
            "database/db-20200127-0230.dump": b"3",
        })
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "db-20200128-0230.dump"
            p.write_bytes(b"4444")
            with mock.patch("utils.db_backup.build_client", return_value=fake):
                res = db_backup.cloud_upload(p, keep_days=2)
        self.assertEqual(
            res["deleted"],
            ["database/db-20200125-0230.dump", "database/db-20200126-0230.dump"],
        )
        self.assertEqual(
            sorted(fake.objects),
            ["database/db-20200127-0230.dump", "database/db-20200128-0230.dump"],
        )

    def test_size_mismatch_removes_partial_and_prunes_nothing(self):
        fake = FakeS3({
            "database/db-20200125-0230.dump": b"1",
            "database/db-20200126-0230.dump": b"2",
        }, extra_size=1)
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "db-20200128-0230.dump"
            p.write_bytes(b"4444")
            with mock.patch("utils.db_backup.build_client", return_value=fake):
                with self.assertRaises(db_backup.BackupError):
                    db_backup.cloud_upload(p, keep_days=1)
        self.assertEqual(fake.deleted, ["database/db-20200128-0230.dump"])
        self.assertIn("database/db-20200125-0230.dump", fake.objects)
        self.assertIn("database/db-20200126-0230.dump", fake.objects)

    def test_upload_error_prunes_nothing(self):
        err_client = ClientError(
            {"Error": {"Code": "AccessDenied"}, "ResponseMetadata": {"HTTPStatusCode": 403}},
            "PutObject",
        )
        for err in (err_client, S3UploadFailedError("fail")):
            fake = FakeS3({
                "database/db-20200125-0230.dump": b"1",
                "database/db-20200126-0230.dump": b"2",
            }, upload_error=err)
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "db-20200128-0230.dump"
                p.write_bytes(b"4444")
                with mock.patch("utils.db_backup.build_client", return_value=fake):
                    with self.assertRaises(db_backup.BackupError):
                        db_backup.cloud_upload(p, keep_days=1)
            self.assertEqual(fake.deleted, [])
            self.assertIn("database/db-20200125-0230.dump", fake.objects)
            self.assertIn("database/db-20200126-0230.dump", fake.objects)

    def test_uploaded_key_is_never_pruned_even_if_older_than_kept_days(self):
        fake = FakeS3({
            "database/db-20200127-0230.dump": b"3",
            "database/db-20200128-0230.dump": b"4",
        })
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "db-20200101-0230.dump"
            p.write_bytes(b"old-but-freshly-uploaded")
            with mock.patch("utils.db_backup.build_client", return_value=fake):
                res = db_backup.cloud_upload(p, keep_days=2)
        self.assertNotIn("database/db-20200101-0230.dump", res["deleted"])
        self.assertIn("database/db-20200101-0230.dump", fake.objects)

    @override_settings(BACKUP_CLOUD_BUCKET="same", ARVAN_FILES_BUCKET="same")
    def test_same_bucket_as_file_manager_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "db-20200128-0230.dump"
            p.write_bytes(b"4")
            with mock.patch("utils.db_backup.build_client") as build:
                with self.assertRaises(db_backup.BackupError):
                    db_backup.cloud_upload(p)
                build.assert_not_called()

    @override_settings(BACKUP_CLOUD_ACCESS_KEY="", BACKUP_CLOUD_SECRET_KEY="", BACKUP_CLOUD_BUCKET="")
    def test_unconfigured_cloud_is_refused_with_env_names(self):
        with self.assertRaises(db_backup.BackupError) as ctx:
            db_backup.assert_cloud_ready()
        msg = str(ctx.exception)
        self.assertIn("BACKUP_CLOUD_ACCESS_KEY_ID", msg)
        self.assertIn("BACKUP_CLOUD_SECRET_ACCESS_KEY", msg)
        self.assertIn("BACKUP_CLOUD_BUCKET_NAME", msg)

    def test_bad_name_missing_or_empty_file_is_refused(self):
        fake = FakeS3()
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.dump"
            bad.write_bytes(b"x")
            empty = Path(tmp) / "db-20200128-0230.dump"
            empty.write_bytes(b"")
            missing = Path(tmp) / "db-20200127-0230.dump"
            with mock.patch("utils.db_backup.build_client", return_value=fake):
                for target in (bad, empty, missing):
                    with self.assertRaises(db_backup.BackupError):
                        db_backup.cloud_upload(target)
        self.assertEqual(fake.calls, [])

    def test_check_probe_cleans_up_after_itself(self):
        fake = FakeS3()
        with mock.patch("utils.db_backup.build_client", return_value=fake):
            db_backup.cloud_check()
        self.assertFalse(any(k.startswith("database/_check/") for k in fake.objects))

    def test_download_latest_and_named_and_refuses_overwrite(self):
        fake = FakeS3({
            "database/db-20200127-0230.dump": b"older",
            "database/db-20200128-0230.dump": b"newest",
        })
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch("utils.db_backup.build_client", return_value=fake):
                dest1 = Path(tmp) / "out1.dump"
                db_backup.cloud_download("latest", dest1)
                self.assertEqual(dest1.read_bytes(), b"newest")
                self.assertFalse((Path(tmp) / "out1.dump.part").exists())

                dest2 = Path(tmp) / "out2.dump"
                db_backup.cloud_download("db-20200127-0230.dump", dest2)
                self.assertEqual(dest2.read_bytes(), b"older")

                with self.assertRaises(db_backup.BackupError):
                    db_backup.cloud_download("db-20200199-0230.dump", Path(tmp) / "missing.dump")
                with self.assertRaises(db_backup.BackupError):
                    db_backup.cloud_download("latest", dest1)


class DbBackupRunTests(SimpleTestCase):
    def test_full_run_order_is_dump_then_local_prune_then_cloud(self):
        order = []
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "db-20200128-0230.dump"
            p.write_bytes(b"ok")

            def fake_dump(dest):
                order.append("dump")
                return p

            def fake_prune(dest, days):
                order.append("prune_local")
                return []

            def fake_cloud(path):
                order.append("cloud_upload")
                return {"key": f"database/{path.name}", "size": 2, "deleted": []}

            with mock.patch("utils.db_backup.dump_database", side_effect=fake_dump), \
                 mock.patch("utils.db_backup.prune_local", side_effect=fake_prune), \
                 mock.patch("utils.db_backup.cloud_upload", side_effect=fake_cloud):
                db_backup.run_backup(dest=tmp, say=lambda _m: None)
        self.assertEqual(order, ["dump", "prune_local", "cloud_upload"])

    def test_local_only_never_touches_cloud(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "db-20200128-0230.dump"
            p.write_bytes(b"ok")
            with mock.patch("utils.db_backup.dump_database", return_value=p), \
                 mock.patch("utils.db_backup.prune_local", return_value=[]), \
                 mock.patch("utils.db_backup.cloud_upload") as upload:
                res = db_backup.run_backup(local_only=True, dest=tmp, say=lambda _m: None)
                upload.assert_not_called()
            self.assertIsNone(res["cloud"])

    def test_cloud_failure_keeps_local_backup_and_raises_with_file_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "db-20200128-0230.dump"
            p.write_bytes(b"ok")
            with mock.patch("utils.db_backup.dump_database", return_value=p), \
                 mock.patch("utils.db_backup.prune_local", return_value=[]), \
                 mock.patch("utils.db_backup.cloud_upload", side_effect=db_backup.BackupError("آپلود شکست خورد")):
                with self.assertRaises(db_backup.BackupError) as ctx:
                    db_backup.run_backup(dest=tmp, say=lambda _m: None)
            self.assertTrue(p.is_file())
            self.assertIn("db-20200128-0230.dump", str(ctx.exception))

    @unittest.skipUnless(db_backup.fcntl, "fcntl only on POSIX")
    def test_concurrent_run_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            fh = open(Path(tmp) / ".lock", "w")
            try:
                db_backup.fcntl.flock(fh, db_backup.fcntl.LOCK_EX | db_backup.fcntl.LOCK_NB)
                with self.assertRaises(db_backup.BackupError):
                    db_backup.run_backup(dest=tmp, say=lambda _m: None)
            finally:
                fh.close()

    def test_command_maps_backup_error_to_command_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(BACKUP_DIR=Path(tmp)):
                with mock.patch("utils.db_backup.dump_database", side_effect=db_backup.BackupError("خراب")):
                    with self.assertRaises(CommandError):
                        call_command("db_backup", "--local-only")


class DbBackupFilesGuardTests(SimpleTestCase):
    BASE = Path(settings.BASE_DIR)

    def test_old_backup_script_and_cron_entry_are_gone(self):
        self.assertFalse((self.BASE / "deploy" / "backup.sh").exists())
        self.assertNotIn("backup.sh", (self.BASE / "deploy" / "cron").read_text(encoding="utf-8"))

    def test_update_sh_installs_backup_units_but_never_enables_the_timer(self):
        text = (self.BASE / "deploy" / "update.sh").read_text(encoding="utf-8")
        self.assertIn("farabakhsh-backup.service", text)
        self.assertIn("farabakhsh-backup.timer", text)
        self.assertNotIn("enable farabakhsh-backup", text)

    def test_service_runs_the_command_as_www_data_without_media(self):
        text = (self.BASE / "deploy" / "farabakhsh-backup.service").read_text(encoding="utf-8")
        self.assertIn("db_backup", text)
        self.assertIn("User=www-data", text)
        self.assertNotIn("media", text)

    def test_env_example_lists_backup_variables(self):
        text = (self.BASE / ".env.example").read_text(encoding="utf-8")
        for var in (
            "BACKUP_CLOUD_ACCESS_KEY_ID",
            "BACKUP_CLOUD_SECRET_ACCESS_KEY",
            "BACKUP_CLOUD_BUCKET_NAME",
            "BACKUP_CLOUD_ENDPOINT_URL",
        ):
            self.assertIn(var, text)

    def test_no_real_backup_credentials_during_tests(self):
        self.assertEqual(settings.BACKUP_CLOUD_ACCESS_KEY, "")
        self.assertEqual(settings.BACKUP_CLOUD_SECRET_KEY, "")
        self.assertEqual(settings.BACKUP_CLOUD_BUCKET, "")
