#!/usr/bin/env python3

"""
create a backup with borg

also supports backing up with the latest snapper snapshot

released under the GNU GPLv3 or any later version.
(c) 2019 Jonas Jelten <jj@sft.mx>


config usually in /etc/sftbackup.cfg
"""


import argparse
import configparser
import datetime
import getpass
import os
import subprocess
import sys
import tempfile


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--cfg", default="/etc/sftbackup.cfg")
    cli.add_argument("--dryrun", action="store_true")
    cli.add_argument('--override', help='enter snapshot name e.g. to resume backup')
    args = cli.parse_args()

    cfg = configparser.ConfigParser()
    with open(args.cfg) as cfgfd:
        cfg.read_file(cfgfd)

    backup(cfg, args.dryrun, args.override)


def backup(cfg, dryrun, backupname_override):
    if not cfg.has_section('backup'):
        raise Exception("config file needs [backup] section with repo and password at least")

    borgrepo = cfg['backup']['repo']
    password = cfg['backup']['password']
    compress = cfg['backup'].get('compress', 'auto,zstd,4')
    rootdir = cfg['backup'].get('rootdir', '/')
    exclude_cfg = cfg['backup'].get('exclude')
    paths_cfg = cfg['backup'].get('paths', '/')

    if any(password.startswith(char) for char in ('~', '/', '.')):
        try:
            password = os.path.expanduser(password)
            with open(password) as pwfile:
                password = pwfile.read().strip()
        except FileNotFoundError:
            print("tried to use password as file, but could not find it")

    excludedirs = ["home/*/.cache/*", "var/tmp/*", "tmp/*", "var/cache/*",
                   "proc/*", "sys/*", "dev/*"]

    if exclude_cfg:
        for path in exclude_cfg.split(","):
            path = path.strip()
            if path:
                excludedirs.append(os.path.relpath(path, "/"))

    backuppaths = []
    for path in paths_cfg.split(","):
        path = path.strip()
        if path:
            backuppaths.append(os.path.relpath(path, "/"))

    if cfg.has_section('prune'):
        prune_active_cfg = cfg['prune'].get('active')
        prune_active = False
        if prune_active_cfg:
            prune_active = True if prune_active_cfg.lower() == 'true' else False

        prune_keep_daily = int(cfg['prune'].get('keep_daily', 7))
        prune_keep_weekly = int(cfg['prune'].get('keep_weekly', 4))
        prune_keep_monthly = int(cfg['prune'].get('keep_monthly', 3))

    use_snapper = False
    if cfg.has_section('snapper'):
        use_snapper_cfg = cfg['snapper'].get('active')
        if use_snapper_cfg:
            use_snapper = True if use_snapper_cfg.lower() == 'true' else False

        snapperdir = cfg['snapper'].get('snapdir', '.snapshots')

    if use_snapper:
        print("figuring out latest snapper snapshot...")
        snapper_list = subprocess.check_output(["snapper", "list"]).decode()

        # list of existing snapper snapshots
        # [(id, type, pre_id, date, user, cleanup, description, userdata), ...]
        snapshots = []
        for snap_entry in snapper_list.split("\n"):
            entry = tuple(ent.strip() for ent in snap_entry.split("|"))
            if len(entry) >= 5 and entry[4] == "root":
                snapshots.append((int(entry[0]),) + entry[1:])

        snapshots = sorted(snapshots, key=lambda x: x[0])
        latest_snap = snapshots[-1]

        snap_id = latest_snap[0]
        snap_date = datetime.datetime.strptime(latest_snap[3], "%Y-%m-%dT%H:%M:%S %Z")
        backupname = f"snapshot-{snap_id}-{snap_date.isoformat()}"

        print(f"found latest snapper snapshot: {backupname}")

        # what to actually backup:
        backupdir = os.path.join(rootdir, snapperdir, str(snap_id), "snapshot")

    else:
        now = datetime.datetime.now().isoformat()
        backupname = f"snapshot-{now}"
        backupdir = rootdir

    if backupname_override:
        backupname = backupname_override

    borg_flags = ["--one-file-system",
                  "--stats",
                  "--exclude-caches",
                  "--show-rc",
                  "--checkpoint-interval", "600",
                  "--compression", compress]  # borg help compression

    if os.isatty(sys.stdout.fileno()):
        borg_flags.append("--progress")

    for exclude in excludedirs:
        borg_flags.extend(["--exclude", exclude])

    with tempfile.NamedTemporaryFile() as pwfile:
        pwfile.write(password.encode())
        pwfile.flush()

        pwfilepath = os.path.abspath(pwfile.name)
        env = {
            'BORG_PASSCOMMAND': f'cat {pwfilepath}',
        }

        # usually, change to / or the snapper snapshot
        print(f"$ cd {backupdir}")
        os.chdir(backupdir)

        repospec = f"{borgrepo}::{backupname}"

        borg_invocation = ["borg", "create"] + borg_flags + [repospec] + backuppaths
        print(f"$ {' '.join(borg_invocation)}")

        if not dryrun:
            subprocess.run(borg_invocation, env=env, check=True)

        if prune_active:
            borg_prune_invocation = ["borg", "prune", "--list", "--show-rc",
                                     "--keep-daily", str(prune_keep_daily),
                                     "--keep-weekly", str(prune_keep_weekly),
                                     "--keep-monthly", str(prune_keep_monthly),
                                     borgrepo]

            print(f"$ {' '.join(borg_prune_invocation)}")
            if not dryrun:
                subprocess.run(borg_prune_invocation, env=env, check=True)


if __name__ == "__main__":
    try:
        main()
    except PermissionError as exc:
        raise Exception("my permissions (uid=%s, name=%s) couldn't do it :(" % (os.geteuid(), getpass.getuser())) from exc
