#!/usr/bin/env python

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: 2016 IBM
# Author: Narasimhan V <sim@linux.vnet.ibm.com>

"""
PCI Hotplug can remove and add pci devices when the system is active.
This test verifies that for supported slots.
"""

import os
import time
import re
from avocado import Test
from avocado import main
from avocado.utils import process


class PCIHotPlugTest(Test):

    """
    PCI Hotplug can remove and add pci devices when the system is active.
    This test verifies that for supported slots.

    :param device: Name of the pci device
    """

    def setUp(self):
        """
        Setup the device.
        """
        cmd = "uname -p"
        if 'ppc' not in process.system_output(cmd, ignore_status=True):
            self.skip("Processor is not ppc64")
        self.return_code = 0
        self.device = self.params.get('pci_device', default=' ')
        if not os.path.isdir('/sys/bus/pci/devices/%s' % self.device):
            self.skip("PCI device given does not exist")
        cmd = "cat /sys/bus/pci/devices/%s/devspec ; echo" % self.device
        self.devspec = process.system_output(cmd, shell=True).strip('\n')
        cmd = "cat /proc/device-tree/%s/ibm,loc-code ; echo" % self.devspec
        self.slot = process.system_output(cmd, shell=True).strip('\0\n')
        self.slot = re.match(r'((\w+)[\.])+(\w+)-P(\d+)-C(\d+)|Slot(\d+)',
                             self.slot).group()
        if not os.path.isdir('/sys/bus/pci/slots/%s' % self.slot):
            self.skip("%s Slot not available" % self.slot)
        if not os.path.exists('/sys/bus/pci/slots/%s/power' % self.slot):
            self.skip("%s Slot does not support hotplug" % self.slot)

    def test(self):
        """
        Creates namespace on the device.
        """
        cmd = "echo 0 > /sys/bus/pci/slots/%s/power" % self.slot
        process.run(cmd, shell=True, sudo=True)
        time.sleep(5)
        cmd = "lspci -k -s %s" % self.device
        if process.system_output(cmd, shell=True).strip('\n') is not '':
            self.return_code = 1
        cmd = "echo 1 > /sys/bus/pci/slots/%s/power" % self.slot
        process.run(cmd, shell=True, sudo=True)
        time.sleep(5)
        cmd = "lspci -k -s %s" % self.device
        if process.system_output(cmd, shell=True).strip('\n') is '':
            self.return_code = 2
        if self.return_code == 1:
            self.fail('%s not removed' % self.device)
        if self.return_code == 2:
            self.fail('%s not attached back' % self.device)


if __name__ == "__main__":
    main()
