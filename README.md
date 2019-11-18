sftbackup
=========

Simple wrapper for [borg backup](https://github.com/borgbackup/borg) and [snapper](https://github.com/openSUSE/snapper)

* [Config file](etc/sftbackup.cfg) example.


Remote backup setup
-------------------

You can store the backup over SSH on a remote server.

This even works for multiple clients to one server as borg can jail clients by ssh forced commands.

* Server setup:
  * Create a `backup` user on your host: `sudo useradd -m backup`
  * Create the storage directory: `sudo mkdir /home/backup/repos`.
  * Create the `authorized_keys` file in `/home/backup/.ssh/authorized_keys`
    * Ensure the `.ssh` and `authorized_keys` file belong to user `backup`
  * For each client:
    * Create a directory `/home/backup/repos/clientname` (owned by user `backup`)
    * Add line in `authorized_keys`:
```
command="cd /home/backup/repos/clientname; borg serve --restrict-to-path /home/backup/repos/clientname",restrict ssh-ed25519 client's_ssh_public_key_... root@clientname
```
    * add `--restrict-to-repository somename` to force access to only this repo name
    * add `--append-only` to disallow this client to remove data in its repos
    * add `--storage-quota 1.5T` to enforce a quota
    * see `man borg-serve` for further information of those options

* Client setup:
  * On each client, generate a ssh-key for the `root` user with `HOME=/root sudo ssh-keygen -t ed25519`
  * Add the content of `/root/.ssh/id_ed25519.pub` file to the `authorized_keys` file as explained above
  * Initialize the borg repo:
    * run `sudo borg init -e repokey backup@your.server:root`
    * enter a password, e.g. generated with `pwgen 30 1`
    * **note down the password** somewhere (to be able to restore the backup!)
  * edit `/etc/sftbackup.cfg` and set at least:
    * `repo = backup@your.server:root`
    * `password = your_generated_repo_password`
    * adjust other things like paths, excludepaths, ...
  * do the first backup by running `sudo ./sftbackup.py`
  * Install the `sftbackup.timer` and `sftbackup.service` systemd units
  * Enable and start the `sftbackup.timer`
* Enjoy your backups!


Contributing
------------

As you might have guessed, you can report issues and submit patches through pull requests easily.


License
-------

**GNU GPLv3** or later; see [copying.md](copying.md) and [legal/GPLv3](/legal/GPLv3).
