# NVMe-oF TCP Target Test Suite

## Overview
This test suite provides automated testing for NVMe over Fabrics (NVMe-oF) TCP target configuration on RHEL systems. It follows the standard NVMe-TCP target setup procedures and validates proper configuration.

## Test File
- **Test Script**: `nvmet_tcp_target.py`
- **Configuration**: `nvmet_tcp_target.yaml`

## Prerequisites
- RHEL 8.4+ or RHEL 9.x
- Kernel with `nvmet` and `nvmet-tcp` modules
- NVMe block device(s) available
- Root access
- nvme-cli package installed

## Available Tests

### 1. test_load_modules
Loads and verifies NVMe target kernel modules (nvmet, nvmet-tcp).

### 2. test_full_target_setup
Complete end-to-end NVMe-TCP target setup including:
- Loading kernel modules
- Mounting configfs
- Creating NVMe subsystem
- Creating and enabling namespaces
- Configuring NVMe-TCP port
- Binding subsystem to port
- Configuring firewall
- Verifying configuration

### 3. test_verify_only
Verifies existing NVMe-TCP target configuration without making changes.

## Configuration Parameters

### Basic Parameters
- `backend_device`: Block device to export (default: /dev/nvme0n1)
- `target_ip`: IP address for NVMe-TCP target (default: 192.168.100.10)
- `target_port`: Port number for NVMe-TCP service (default: 4420)
- `subsystem_nqn`: NVMe Qualified Name for subsystem (default: nqn.2026-01.lab:nvme:target1)
- `namespace_count`: Number of namespaces to create (default: 1)
- `port_id`: Port identifier (default: 1)
- `cleanup_on_teardown`: Whether to cleanup after test (default: false)

## Test Scenarios

### Single Namespace (Default)
```bash
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
  -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml \
  --mux-filter-only /TestScenarios/single_namespace
```

### Multiple Namespaces
```bash
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
  -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml \
  --mux-filter-only /TestScenarios/multiple_namespaces
```

### Custom Port Configuration
```bash
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
  -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml \
  --mux-filter-only /TestScenarios/custom_port
```

### Multipath Setup
```bash
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
  -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml \
  --mux-filter-only /TestScenarios/multipath_setup
```

## Usage Examples

### List Available Tests
```bash
cd /home/avocado-fvt-wrapper/tests/avocado-misc-tests/io/disk/ssd
avocado list nvmet_tcp_target.py
```

### Run Full Target Setup
```bash
avocado run --max-parallel-tasks=1 \
  nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
  -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml
```

### Run Only Module Loading Test
```bash
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_load_modules
```

### Verify Existing Configuration
```bash
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_verify_only
```

### Run with Custom Parameters
```bash
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
  --test-parameter backend_device=/dev/nvme1n1 \
  --test-parameter target_ip=192.168.1.49 \
  --test-parameter target_port=8009 \
  --test-parameter subsystem_nqn=nqn.2026-01.custom:target
```

## Manual Verification

After running the test, verify the configuration:

```bash
# Check loaded modules
lsmod | grep nvmet

# List NVMe target configuration
nvmetcli ls

# Check kernel messages
dmesg | grep nvmet_tcp

# Verify subsystem
ls -la /sys/kernel/config/nvmet/subsystems/

# Verify ports
ls -la /sys/kernel/config/nvmet/ports/
```

## Cleanup

To manually cleanup the target configuration:

```bash
# Unbind subsystem from port
rm /sys/kernel/config/nvmet/ports/1/subsystems/nqn.2026-01.lab:nvme:target1

# Disable namespace
echo 0 > /sys/kernel/config/nvmet/subsystems/nqn.2026-01.lab:nvme:target1/namespaces/1/enable

# Remove namespace
rmdir /sys/kernel/config/nvmet/subsystems/nqn.2026-01.lab:nvme:target1/namespaces/1

# Remove subsystem
rmdir /sys/kernel/config/nvmet/subsystems/nqn.2026-01.lab:nvme:target1

# Remove port
rmdir /sys/kernel/config/nvmet/ports/1
```

## Troubleshooting

### Module Loading Fails
```bash
# Check if modules are available
modinfo nvmet
modinfo nvmet-tcp

# Check kernel version
uname -r
```

### Device Path Issues
```bash
# List available NVMe devices
nvme list

# Check device exists
ls -la /dev/nvme*
```

### Port Binding Fails
```bash
# Check if port is already in use
netstat -tuln | grep 4420

# Check firewall status
systemctl status firewalld
```

## Integration with Existing Tests

This test can be combined with other NVMe tests:

```bash
# Run NVMe target setup followed by initiator tests
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
  nvmetest.py:NVMeTest.test_read \
  -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml
```

## References
- [RHEL NVMe-oF Documentation](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_storage_devices/configuring-nvme-over-fabrics-using-nvme-tcp_managing-storage-devices)
- [NVMe-CLI GitHub](https://github.com/linux-nvme/nvme-cli)
- [IBM Storage Ceph NVMe Configuration](https://www.ibm.com/docs/en/storage-ceph/8.1.0?topic=initiator-configuring-nvme-red-hat-enterprise-linux)

## Author
Generated for IBM NVMe-oF TCP Target Testing - 2026
