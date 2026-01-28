NMCLI Bonding Test Suite
=========================

This test suite validates network bonding configuration using NetworkManager's nmcli tool.
It supports all standard bonding modes and includes failover testing.

PARAMETERS:
-----------

"bonding_mode": Bonding mode to test (required)
  Values: "0" (balance-rr), "1" (active-backup), "2" (balance-xor),
          "4" (802.3ad/LACP), "5" (balance-tlb), "6" (balance-alb)
  Example: bonding_mode: "1"

"host_ips": Space-separated IP addresses for host interfaces (required)
  Must match number of bond_interfaces
  Example: host_ips: "192.168.1.10 192.168.1.11"

"netmask": Network mask for all interfaces (required)
  Example: netmask: "255.255.255.0"

"bond_interfaces": Space-separated host interface names (required)
  Minimum 2 interfaces recommended for failover testing
  Example: bond_interfaces: "eth0 eth1"

"bond_name": Name for the bond interface (default: "tempbond")
  Example: bond_name: "bond0"

"peer_public_ip": Public IP address of peer machine (required)
  Used for SSH connection to peer
  Example: peer_public_ip: "192.168.1.20"

"peer_ips": Space-separated IP addresses for peer interfaces (required)
  Must match number of peer_interfaces
  Example: peer_ips: "192.168.1.20 192.168.1.21"

"peer_interfaces": Space-separated peer interface names (required)
  Example: peer_interfaces: "eth0 eth1"

"peer_user": SSH username for peer machine (default: "root")
  Example: peer_user: "root"

"peer_password": SSH password for peer machine (required)
  Example: peer_password: "password"

"miimon": Link monitoring interval in milliseconds (default: "100")
  Example: miimon: "100"

"fail_over_mac": Fail over MAC address policy (default: "2")
  Values: "0" (none), "1" (active), "2" (follow)
  Example: fail_over_mac: "2"

"downdelay": Delay before disabling slave after link failure (default: "0")
  In milliseconds, must be multiple of miimon
  Example: downdelay: "0"

"sleep_time": Sleep time between operations in seconds (default: "10")
  Example: sleep_time: "10"

"peer_wait_time": Wait time for peer operations in seconds (default: "5")
  Example: peer_wait_time: "5"

"mtu": MTU size for testing (default: "1500")
  Example: mtu: "1500"

"peer_bond_needed": Whether to setup bonding on peer (default: false)
  If true, creates mode 0 bond on peer machine
  Example: peer_bond_needed: false

MODE-SPECIFIC PARAMETERS:
-------------------------

Mode 0 (balance-rr):
  - packets_per_slave: Number of packets to transmit before moving to next slave
  - resend_igmp: Number of IGMP membership reports to send

Mode 1 (active-backup):
  - primary: Primary slave interface name
  - primary_reselect: Primary reselection policy (always/better/failure)
  - num_unsol_na: Number of unsolicited IPv6 Neighbor Advertisements
  - resend_igmp: Number of IGMP membership reports to send

Mode 2 (balance-xor):
  - xmit_hash_policy: Transmit hash policy (layer2/layer2+3/layer3+4)

Mode 4 (802.3ad/LACP):
  - lacp_rate: LACP rate (slow/fast)
  - xmit_hash_policy: Transmit hash policy (layer2/layer2+3/layer3+4)

Mode 5 (balance-tlb):
  - tlb_dynamic_lb: Enable dynamic load balancing
  - primary: Primary slave interface name
  - primary_reselect: Primary reselection policy
  - xmit_hash_policy: Transmit hash policy
  - lp_interval: Learning packet interval in seconds

Mode 6 (balance-alb):
  - primary: Primary slave interface name
  - primary_reselect: Primary reselection policy
  - lp_interval: Learning packet interval in seconds

TEST CASES:
-----------

1. test_bond_setup()
   - Creates bond interface on host (and optionally peer)
   - Adds slave interfaces to bond
   - Configures IP addresses
   - Validates bond creation and link status
   - Performs ping test to verify connectivity

2. test_bond_failover()
   - Tests slave interface failover by bringing interfaces down/up
   - Validates bond remains functional with one slave down
   - Tests all slaves down scenario
   - Performs MTU testing with various sizes (2000-9000)
   - Validates ping connectivity after each change

3. test_bond_cleanup()
   - Removes bond interface
   - Restores original interface configuration
   - Cleans up peer bonding if configured
   - Unloads bonding kernel module

RUNNING TESTS:
--------------

# Run all bonding tests in sequence
avocado run avocado-misc-tests/io/net/nmcli_bonding.py:Bonding.test_bond_setup -m nmcli_bonding.yaml
avocado run avocado-misc-tests/io/net/nmcli_bonding.py:Bonding.test_bond_failover -m nmcli_bonding.yaml
avocado run avocado-misc-tests/io/net/nmcli_bonding.py:Bonding.test_bond_cleanup -m nmcli_bonding.yaml

# Run specific bonding mode
avocado run avocado-misc-tests/io/net/nmcli_bonding.py -m nmcli_bonding_mode1.yaml

PREREQUISITES:
--------------

1. NetworkManager must be installed and running
2. nmcli command must be available
3. At least 2 network interfaces on host and peer
4. SSH access to peer machine
5. Root/sudo privileges on both machines
6. Interfaces must not be in use (no active connections)
7. For LACP mode (4): Switch must support 802.3ad

NOTES:
------

- Test automatically flushes IP addresses before starting
- Bond interface is created using nmcli (NetworkManager)
- Different from bonding.py which uses sysfs interface
- LACP mode requires switch configuration
- MTU testing skipped for vNIC interfaces (only tests 9000)
- Peer bonding always uses mode 0 (balance-rr)
- Test validates bond status via /proc/net/bonding/<bond_name>

TROUBLESHOOTING:
----------------

- If peer connection fails in LACP mode, test retries up to 5 times
- Firewall must be disabled on both host and peer
- Ensure interfaces are not managed by other network managers
- Check NetworkManager service status if bond creation fails
- Verify peer machine is accessible via SSH before running test

# Assisted with AI tools