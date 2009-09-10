'''Attach generally useful information, not specific to any package.

Copyright (C) 2009 Canonical Ltd.
Author: Matt Zimmerman <mdz@canonical.com>

This program is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation; either version 2 of the License, or (at your
option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
the full text of the license.
'''

import apport.packaging
import re
from apport.hookutils import *

def add_info(report):
    # crash reports from live system installer often expose target mount
    for f in ('ExecutablePath', 'InterpreterPath'):
        if f in report and report[f].startswith('/target/'):
            report[f] = report[f][7:]

    # if we are running from a live system, add the build timestamp
    attach_file_if_exists(report, '/cdrom/.disk/info', 'LiveMediaBuild')

    # This includes the Ubuntu packaged kernel version
    attach_file_if_exists(report, '/proc/version_signature', 'ProcVersionSignature')

    # There are enough of these now that it is probably worth refactoring...
    # -mdz
    if report['ProblemType'] == 'Package':
        if report['Package'] not in ['grub', 'grub2']:
            # linux-image postinst emits this when update-grub fails
            # https://wiki.ubuntu.com/KernelTeam/DebuggingUpdateErrors
            if 'DpkgTerminalLog' in report and re.search(r'^User postinst hook script \[.*update-grub\] exited with value', report['DpkgTerminalLog'], re.MULTILINE):
                # File these reports on the grub package instead
                grub_package = apport.packaging.get_file_package('/usr/sbin/update-grub')
                if grub_package is None or grub_package == 'grub':
                    report['SourcePackage'] = 'grub'
                else:
                    report['SourcePackage'] = 'grub2'

        if report['Package'] != 'initramfs-tools':
            # update-initramfs emits this when it fails, usually invoked from the linux-image postinst
            # https://wiki.ubuntu.com/KernelTeam/DebuggingUpdateErrors
            if 'DpkgTerminalLog' in report and re.search(r'^update-initramfs: failed for ', report['DpkgTerminalLog'], re.MULTILINE):
                # File these reports on the initramfs-tools package instead
                report['SourcePackage'] = 'initramfs-tools'

        if report['Package'].startswith('linux-image-') and 'DpkgTerminalLog' in report:
            # /etc/kernel/*.d failures from kernel package postinst
            m = re.search(r'^run-parts: (/etc/kernel/\S+\.d/\S+) exited with return code \d+', report['DpkgTerminalLog'], re.MULTILINE)
            if m:
                path = m.group(1)
                package = apport.packaging.get_file_package(path)
                if package:
                    report['SourcePackage'] = package
                    report['ErrorMessage'] = m.group(0)
                else:
                    report['UnreportableReason'] = 'This failure was caused by a program which did not originate from Ubuntu'

    if 'Package' in report:
        package = report['Package'].split()[0]
        if package and 'attach_conffiles' in dir():
            attach_conffiles(report, package)