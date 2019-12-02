sftbackup
=========

Simple wrapper for [borg backup](https://github.com/borgbackup/borg) and [snapper](https://github.com/openSUSE/snapper)

* [Config file](etc/sftbackup.cfg) example.


Remote backup setup
-------------------

You can store the backup over SSH on a remote server.

This even works for multiple clients to one server as borg can jail clients by ssh forced commands.


### Client setup

Backup targets:
* Remote server via SSH (you have a borg remote url)
* Local storage (secondary harddrive, a `nfs`/`samba` mount, ...)


#### Remote backup client preparation

If you do your backup remotely via SSH, you need a SSH key first.

* Generate ssh-key for user `root`
  * Of course you may reuse an existing ssh key, but root has to be configured to use it.

```
HOME=/root sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519_backup
```

* Provide your ssh public key in `/root/.ssh/id_ed25519_backup.pub` to the server operator
* Configure SSH to use the right *user* and *ssh key* in `/root/.ssh/config`:

```
# example config if your borg backup remote url is "borg@borgbackup.somewhere.net:reponame"
Host borgbackup.somewhere.net
    User borg
    IdentityFile ~/.ssh/id_ed25519_backup
```

#### Client configuration

* Configure `sftbackup` in `/etc/sftbackup.cfg`
* Set `password = ...` to encrypt the backup
  * To generate a password, you can use `pwgen 30 1`
  * **Note down the password** somewhere (to be able to restore the backup!)
* Use `repo = ...` to specify where to store the backup
  * Remote backup via SSH: `repo = borg@borgbackup.somewhere.net:reponame`
  * Local storage, e.g. external HDD: `repo = /mnt/backupdrive`
* Adjust other things like paths, excludepaths, ...


#### Repo creation

* Create the repo: `sudo sftbackup init`
* This will initialize the borg repo in `repokey` mode.


#### Test backup

* Test the creation of the first backup by running `sudo sftbackup backup`


#### Automated runs

This is only suitable for devices that are permanently running (e.g. servers)

* Install the `sftbackup.timer` and `sftbackup.service` systemd units
* Enable and start the `sftbackup.timer`

Enjoy your backups!


### Server setup

Repo storage:
* Create a `borg` user on your host: `sudo useradd -m borg`
* Create the storage directory: `sudo mkdir /home/borg/repos`.
* Create the `authorized_keys` file in `/home/borg/.ssh/authorized_keys`
  * Ensure the `.ssh` and `authorized_keys` file belong to user `borg`

Client access:
* Create a directory `/home/borg/repos/clientname` (owned by user `borg`)
* Grant access in `authorized_keys`:

```
command="cd /home/borg/repos/clientname; borg serve --restrict-to-repository /home/borg/repos/clientname/reponame --storage-quota 1.5T",restrict ssh-ed25519 client's_ssh_public_key_... root@clientname
```

* Add `--append-only` to disallow this client to remove data in its repos (very handy so a server can't delete its own backup when hacked).
* See `man borg-serve` for further information on how to restrict client access


Restore
-------

* Retrieve and store file(s) from repo
  * use [`borg extract`](https://borgbackup.readthedocs.io/en/stable/usage/extract.html)
* Mount repo as [FUSE](https://en.wikipedia.org/wiki/Filesystem_in_Userspace)
  * use [`borg mount`](https://borgbackup.readthedocs.io/en/stable/usage/mount.html)


Contributing
------------

As you might have guessed, you can report issues and submit patches through pull requests easily.


License
-------

**GNU GPLv3** or later; see [copying.md](copying.md) and [legal/GPLv3](/legal/GPLv3).
