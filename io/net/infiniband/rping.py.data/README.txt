RPING Test - RDMA Ping Test
=============================

This test validates RDMA connectivity using the rping utility, which tests RDMA read and write operations.

PARAMETERS:
-----------

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

"count": Number of ping iterations (default: "10")
  Example: count: "10"

"size": Size of data to transfer in bytes (default: "64")
  Example: size: "64"

"verbose": Enable verbose output (default: false)
  Example: verbose: true

TEST CASES:
-----------

1. Starts rping server on peer machine
2. Runs rping client from host
3. Tests RDMA read operations
4. Tests RDMA write operations
5. Validates data integrity
6. Measures RDMA performance

RUNNING TESTS:
--------------

# Run rping test with InfiniBand
avocado run avocado-misc-tests/io/net/infiniband/rping.py -m rping_infiniband.yaml

# Run rping test with RoCE
avocado run avocado-misc-tests/io/net/infiniband/rping.py -m rping_roce.yaml

PREREQUISITES:
--------------

1. librdmacm-utils package installed (provides rping utility)
2. InfiniBand or RoCE capable hardware
3. Peer machine with RDMA support
4. RDMA drivers loaded (rdma_cm, ib_core, etc.)
5. Network connectivity between host and peer

NOTES:
------

- rping is part of librdmacm-utils package
- Test validates both RDMA read and write operations
- Supports both InfiniBand and RoCE protocols
- Server runs on peer, client runs on host
- Test automatically cleans up server process after completion

TROUBLESHOOTING:
----------------

- Ensure RDMA drivers are loaded: `lsmod | grep rdma`
- Check RDMA devices: `ibv_devices` or `rdma link`
- Verify network connectivity: `ping <peer_ip>`
- Check firewall settings (RDMA uses dynamic ports)
- Ensure rping utility is installed: `which rping`

# Assisted with AI tools
