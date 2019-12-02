#!/usr/bin/env python3

from distutils.core import setup
import os
import glob


setup(
    name="sftbackup",
    version="0.1",
    description="Simple backup client based on Borg Backup and Snapper",
    long_description=(
        "Backup your machine with Borg. Optionally, use Snapper to "
        "snapshot your filesystem to back up.\nsftbackup is intended"
        "for automated backups of servers, but when started manually, "
        "any other Linux device can be backed up. As sftbackup is just "
        "a wrapper for Borg, you can just use Borg commands directly."
    ),
    maintainer="SFT Technologies",
    maintainer_email="jj@sft.mx",
    url="https://github.com/SFTtech/sftbackup",
    license='GPL3+',
    packages=[
        "sftbackup",
    ],
    data_files=[
        ("/usr/lib/systemd/system/", [
            "etc/sftbackup.service",
        ]),
        ("/etc/", [
            "etc/sftbackup.cfg",
        ]),
    ],
    platforms=[
        'Linux',
    ],
    classifiers=[
        ("License :: OSI Approved :: "
         "GNU General Public License v3 or later (GPLv3+)"),
        "Environment :: Console",
        "Operating System :: POSIX :: Linux"
    ],
)
