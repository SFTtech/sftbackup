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
    """
    argparsing and entry point for sftbackup
    """

    cli = argparse.ArgumentParser()
    cli.add_argument("--cfg", default="/etc/sftbackup.cfg")
    cli.add_argument("--dryrun", action="store_true")
    subp = cli.add_subparsers(dest="mode", required=True)

    subp.add_parser("prune")
    backupcli = subp.add_parser("backup")
    backupcli.add_argument('--override', help='enter snapshot name e.g. to resume backup')

    subp.add_parser("init")

    args = cli.parse_args()

    cfg = configparser.ConfigParser()
    with open(args.cfg) as cfgfd:
        cfg.read_file(cfgfd)

    if args.mode == "init":
        init(cfg, args.dryrun)

    elif args.mode == "prune":
        prune(cfg, args.dryrun)

    elif args.mode == "backup":
        backup(cfg, args.dryrun, args.override)

    else:
        raise Exception("unknown program mode")


def backup(cfg, dryrun, backupname_override):
    """
    create a backup with borg
    """
    if not cfg.has_section('archive'):
        raise Exception("config file needs [archive] section with repo and password at least")

    # general borg archive properties
    borgrepo = cfg['archive']['repo']
    password_cfg = cfg['archive']['password']

    # settings for the backup
    compress = cfg['backup'].get('compress', 'auto,zstd,4')
    rootdir = cfg['backup'].get('rootdir', '/')
    exclude_cfg = cfg['backup'].get('exclude')
    paths_cfg = cfg['backup'].get('paths', '/')
    prune_run_cfg = cfg['backup'].get('prune_old')

    prune_run = False
    if prune_run_cfg:
        prune_run = prune_run_cfg.lower() == 'true'

    password = get_password(password_cfg)

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

    use_snapper = False
    if cfg.has_section('snapper'):
        use_snapper_cfg = cfg['snapper'].get('active')
        if use_snapper_cfg:
            use_snapper = use_snapper_cfg.lower() == 'true'

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

    borg_create = ["create",
                   "--one-file-system",
                   "--stats",
                   "--exclude-caches",
                   "--show-rc",
                   "--checkpoint-interval", "600",
                   "--compression", compress]

    if os.isatty(sys.stdout.fileno()):
        borg_create.append("--progress")

    for exclude in excludedirs:
        borg_create.extend(["--exclude", exclude])

    repospec = f"{borgrepo}::{backupname}"
    borg_invocation = borg_create + [repospec] + backuppaths

    launch_borg(
        borg_invocation,
        password,
        workdir=backupdir,
        dryrun=dryrun,
    )

    if prune_run:
        prune(cfg, dryrun)


def prune(cfg, dryrun):
    """
    remove old archives from a borg repo
    """
    if not cfg.has_section('archive'):
        raise Exception("config file needs [archive] section with repo and password at least")

    borgrepo = cfg['archive']['repo']
    password_cfg = cfg['archive']['password']

    if not cfg.has_section('prune'):
        raise Exception("config file needs a [prune] configuration section")

    prune_keep_daily = int(cfg['prune'].get('keep_daily', 7))
    prune_keep_weekly = int(cfg['prune'].get('keep_weekly', 4))
    prune_keep_monthly = int(cfg['prune'].get('keep_monthly', 3))

    password = get_password(password_cfg)

    borg_prune_invocation = ["prune",
                             "--list",
                             "--show-rc",
                             "--keep-daily", str(prune_keep_daily),
                             "--keep-weekly", str(prune_keep_weekly),
                             "--keep-monthly", str(prune_keep_monthly),
                             borgrepo]

    launch_borg(borg_prune_invocation, password, dryrun=dryrun)


def init(cfg, dryrun):
    """
    create a new borg archive in repokey mode

    TODO: also add support for keyfile mode
    """
    if not cfg.has_section('archive'):
        raise Exception("config file needs [archive] section with repo and password at least")

    borgrepo = cfg['archive']['repo']
    password_cfg = cfg['archive']['password']

    password = get_password(password_cfg)

    borg_init_invocation = ["init",
                            "--encryption", "repokey",
                            borgrepo]

    launch_borg(borg_init_invocation, password, dryrun=dryrun)


def get_password(password):
    """
    try to read the password from a file, if it looks like a filename.
    """
    if any(password.startswith(char) for char in ('~', '/', '.')):
        try:
            password = os.path.expanduser(password)
            with open(password) as pwfile:
                password = pwfile.read().strip()
        except FileNotFoundError:
            print("tried to use password as file, but could not find it")

    return password


def launch_borg(args, password, workdir=None, dryrun=False):
    """
    launch borg and supply the password by environment

    raises a CalledProcessError when borg doesn't return with 0
    """
    with tempfile.NamedTemporaryFile() as pwfile:
        pwfile.write(password.encode())
        pwfile.flush()

        pwfilepath = os.path.abspath(pwfile.name)
        env = {
            'BORG_PASSCOMMAND': f'cat {pwfilepath}',
        }

        if workdir:
            # change to / or the snapper snapshot
            print(f"$ cd {workdir}")
            os.chdir(workdir)

        cmd = ["borg"] + args

        print(f"$ {' '.join(cmd)}")

        if not dryrun:
            subprocess.run(cmd, env=env, check=True)


if __name__ == "__main__":
    try:
        main()
    except PermissionError as exc:
        raise Exception("my permissions (uid=%s, name=%s) couldn't do it :(" % (os.geteuid(), getpass.getuser())) from exc
