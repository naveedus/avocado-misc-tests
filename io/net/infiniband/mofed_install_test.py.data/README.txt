MOFED Installation Test
=======================

This test validates the installation and functionality of Mellanox OFED (MOFED) drivers.

PARAMETERS:
-----------

"mofed_source": Source for MOFED installation (required)
  Options: "distro" (use distribution packages) or "mlnx" (use Mellanox packages)
  Example: mofed_source: "mlnx"

"mofed_version": MOFED version to install (optional, for mlnx source)
  Example: mofed_version: "5.4-1.0.3.0"

"interface": Network interface to test (required)
  Can be interface name or MAC address
  Example: interface: "ib0"

"peer_ip": IP address of peer machine (required)
  Example: peer_ip: "192.168.1.20"

"peer_user": SSH username for peer machine (default: "root")
  Example: peer_user: "root"

"peer_password": SSH password for peer machine (required)
  Example: peer_password: "password"

"host_ip": IP address for host interface (required)
  Example: host_ip: "192.168.1.10"

"netmask": Network mask (required)
  Example: netmask: "255.255.255.0"

TEST CASES:
-----------

1. Installs MOFED drivers from specified source
2. Validates driver installation
3. Configures InfiniBand/RoCE interface
4. Performs connectivity tests to peer
5. Validates RDMA functionality

RUNNING TESTS:
--------------

# Test with Mellanox MOFED
avocado run avocado-misc-tests/io/net/infiniband/mofed_install_test.py -m mofed_install_test.yaml

# Test with distribution packages
avocado run avocado-misc-tests/io/net/infiniband/mofed_install_test.py -m mofed_install_test_distro.yaml

PREREQUISITES:
--------------

1. InfiniBand or RoCE capable hardware
2. Peer machine with RDMA support
3. Root/sudo privileges
4. Internet connection (for downloading MOFED packages)

NOTES:
------

- Test will uninstall existing MOFED before installing new version
- Requires system reboot after MOFED installation
- Validates both InfiniBand and RoCE modes
- Checks for proper driver loading and device detection

# Assisted with AI tools
