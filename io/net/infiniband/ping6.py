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
# Author: Manvanthara B Puttashankar <manvanth@linux.vnet.ibm.com>

"""
Ping6 - Send ICMP ECHO_REQUEST to network hosts.
"""

import time
import netifaces
from netifaces import AF_INET, AF_INET6
from avocado import Test
from avocado import main
from avocado.utils.software_manager import SoftwareManager
from avocado.utils import process, distro


class Ping6(Test):
    """
    ping6 Test.
    """
    def setUp(self):
        """
        Setup and install dependencies for the test.
        """
        self.test_name = "ping6"
        self.basic = self.params.get("basic_option", default="None")
        self.ext = self.params.get("ext_option", default="None")
        self.flag = self.params.get("ext_flag", default="0")
        if self.basic == "None" and self.ext == "None":
            self.skip("No option given")
        if self.flag == "1" and self.ext != "None":
            self.option = self.ext
        else:
            self.option = self.basic
        if process.system("ibstat", shell=True, ignore_status=True) != 0:
            self.skip("MOFED is not installed. Skipping")
        pkgs = []
        detected_distro = distro.detect()
        if detected_distro.name == "Ubuntu":
            pkgs.extend(["openssh-client", "iputils-ping"])
        elif detected_distro.name == "SuSE":
            pkgs.extend(["openssh", "iputils"])
        else:
            pkgs.extend(["openssh-clients", "iputils"])
        smm = SoftwareManager()
        for pkg in pkgs:
            if not smm.check_installed(pkg) and not smm.install(pkg):
                self.skip("Not able to install %s" % pkg)
        interfaces = netifaces.interfaces()
        self.iface = self.params.get("interface", default="")
        self.peer_iface = self.params.get("peer_interface", default="")
        self.ipv6_peer = self.params.get("peer_ipv6", default="")
        self.peer_ip = self.params.get("peer_ip", default="")
        if self.iface not in interfaces:
            self.skip("%s interface is not available" % self.iface)
        if self.peer_ip == "":
            self.skip("%s peer machine is not available" % self.peer_ip)
        self.timeout = "2m"
        self.local_ip = netifaces.ifaddresses(self.iface)[AF_INET][0]['addr']
        if 10 in netifaces.ifaddresses(self.iface):
            self.l_v6 = netifaces.ifaddresses(self.iface)[AF_INET6][0]['addr']
        else:
            self.l_v6 = ""
        self.option = self.option.replace("peer_interface", self.peer_iface)
        self.option = self.option.replace("interface", self.iface)
        self.option = self.option.replace("local_ipv6", self.l_v6)
        self.option = self.option.replace("peer_ipv6", self.ipv6_peer)
        self.option = self.option.replace("local_ip", self.local_ip)
        self.option = self.option.replace("peer_ip", self.peer_ip)
        self.option_list = self.option.split(",")

        if detected_distro.name == "Ubuntu":
            cmd = "service ufw stop"
        # FIXME: "redhat" as the distro name for RHEL is deprecated
        # on Avocado versions >= 50.0.  This is a temporary compatibility
        # enabler for older runners, but should be removed soon
        elif detected_distro.name in ['rhel', 'fedora', 'redhat']:
            cmd = "systemctl stop firewalld"
        elif detected_distro.name == "SuSE":
            cmd = "rcSuSEfirewall2 stop"
        elif detected_distro.name == "centos":
            cmd = "service iptables stop"
        else:
            self.skip("Distro not supported")
        if process.system("%s && ssh %s %s" % (cmd, self.peer_ip, cmd),
                          ignore_status=True, shell=True) != 0:
            self.skip("Unable to disable firewall")

    def test(self):
        """
        Test ping6
        """
        self.log.info(self.test_name)
        logs = "> /tmp/ib_log 2>&1 &"
        cmd = "ssh %s \" timeout %s %s %s %s\" " \
            % (self.peer_ip, self.timeout, self.test_name,
               self.option_list[0], logs)
        if process.system(cmd, shell=True, ignore_status=True) != 0:
            self.fail("SSH connection (or) Server command failed")
        time.sleep(5)
        self.log.info("Client data - %s(%s)" %
                      (self.test_name, self.option_list[0]))
        cmd = "timeout %s %s %s" \
            % (self.timeout, self.test_name, self.option_list[1])
        if process.system(cmd, shell=True, ignore_status=True) != 0:
            self.fail("Client command failed")
        time.sleep(5)
        self.log.info("Server data - %s(%s)" %
                      (self.test_name, self.option_list[1]))
        cmd = "ssh %s \"timeout %s cat /tmp/ib_log && rm -rf /tmp/ib_log\" " \
            % (self.peer_ip, self.timeout)
        if process.system(cmd, shell=True, ignore_status=True) != 0:
            self.fail("Server output retrieval failed")


if __name__ == "__main__":
    main()
