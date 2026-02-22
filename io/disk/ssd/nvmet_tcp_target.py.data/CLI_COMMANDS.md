# NVMe-oF TCP Target - CLI Commands Reference

This document contains all CLI commands used to set up and test the NVMe-oF TCP target.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Target Setup](#target-setup)
3. [Target Verification](#target-verification)
4. [Initiator Testing](#initiator-testing)
5. [Cleanup](#cleanup)

---

## Prerequisites

### Check NVMe Devices
```bash
# List all NVMe devices
ls -la /dev/nvme*

# Show NVMe device details
lsblk | grep nvme

# Get device information
nvme list
```

### Check Network Configuration
```bash
# Show IP addresses
ip a | grep "inet " | grep -v "127.0.0.1"

# Show specific interface
ip addr show enP32769p1s0
```

### Install Required Packages
```bash
# Install nvme-cli (if not already installed)
dnf install nvme-cli -y

# Check nvme-cli version
nvme version
```

---

## Target Setup

### 1. Load Kernel Modules
```bash
# Load NVMe target modules
modprobe nvmet
modprobe nvmet-tcp

# Verify modules are loaded
lsmod | grep nvmet
```

### 2. Mount ConfigFS
```bash
# Mount configfs (if not already mounted)
mount -t configfs none /sys/kernel/config

# Verify mount
mount | grep configfs
```

### 3. Create NVMe Subsystem
```bash
# Set variables
SUBSYS_NQN="nqn.2026-01.lab:nvme:target1"
BACKEND_DEV="/dev/nvme0n1"

# Create subsystem directory
mkdir -p /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN

# Allow any host to connect (for lab/test environment)
echo 1 > /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN/attr_allow_any_host
```

### 4. Create and Enable Namespace
```bash
# Create namespace directory
mkdir -p /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN/namespaces/1

# Set backend device path
echo -n $BACKEND_DEV > /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN/namespaces/1/device_path

# Enable namespace
echo 1 > /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN/namespaces/1/enable
```

### 5. Configure TCP Port
```bash
# Set variables
TARGET_IP="192.168.1.49"
PORT="4420"
PORT_ID="1"

# Create port directory
mkdir -p /sys/kernel/config/nvmet/ports/$PORT_ID

# Configure transport type
echo tcp > /sys/kernel/config/nvmet/ports/$PORT_ID/addr_trtype

# Configure address family
echo ipv4 > /sys/kernel/config/nvmet/ports/$PORT_ID/addr_adrfam

# Set target IP address
echo $TARGET_IP > /sys/kernel/config/nvmet/ports/$PORT_ID/addr_traddr

# Set port number
echo $PORT > /sys/kernel/config/nvmet/ports/$PORT_ID/addr_trsvcid
```

### 6. Bind Subsystem to Port
```bash
# Create symbolic link to bind subsystem to port
ln -s /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN \
      /sys/kernel/config/nvmet/ports/$PORT_ID/subsystems/$SUBSYS_NQN
```

---

## Target Verification

### Check Target Configuration
```bash
# List target configuration using nvmetcli
nvmetcli ls

# Check dmesg for nvmet_tcp messages
dmesg | grep nvmet_tcp | tail -10

# Verify subsystem exists
ls -la /sys/kernel/config/nvmet/subsystems/

# Verify port configuration
ls -la /sys/kernel/config/nvmet/ports/

# Check namespace status
cat /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN/namespaces/1/enable
```

### Firewall Configuration (if needed)
```bash
# Check if firewalld is running
systemctl is-active firewalld

# Add port to firewall (if firewalld is active)
firewall-cmd --add-port=4420/tcp --permanent
firewall-cmd --reload
```

---

## Initiator Testing

### 1. Discovery
```bash
# Discover NVMe-oF targets
nvme discover -t tcp -a 192.168.1.49 -s 4420

# Discover with verbose output
nvme discover -t tcp -a 192.168.1.49 -s 4420 -v
```

### 2. Connect to Target
```bash
# Connect to specific subsystem
nvme connect -t tcp -n nqn.2026-01.lab:nvme:target1 -a 192.168.1.49 -s 4420

# Connect with verbose output
nvme connect -t tcp -n nqn.2026-01.lab:nvme:target1 -a 192.168.1.49 -s 4420 -v
```

### 3. Verify Connection
```bash
# List all NVMe devices (including NVMe-oF)
nvme list

# List subsystems
nvme list-subsys

# Find connected NVMe-oF device
ls -la /dev/nvme* | grep nvme[2-9]

# Get specific device info
NVME_DEV="/dev/nvme2n1"
nvme id-ctrl $NVME_DEV
nvme id-ns $NVME_DEV
```

### 4. I/O Testing
```bash
# Write test (10MB)
dd if=/dev/zero of=/dev/nvme2n1 bs=1M count=10 oflag=direct

# Read test (10MB)
dd if=/dev/nvme2n1 of=/dev/null bs=1M count=10 iflag=direct

# Sequential write test (100MB)
dd if=/dev/zero of=/dev/nvme2n1 bs=1M count=100 oflag=direct

# Random I/O test using fio (if installed)
fio --name=randwrite --ioengine=libaio --iodepth=16 --rw=randwrite \
    --bs=4k --direct=1 --size=1G --numjobs=1 --runtime=60 \
    --group_reporting --filename=/dev/nvme2n1
```

### 5. Disconnect
```bash
# Disconnect from specific subsystem
nvme disconnect -n nqn.2026-01.lab:nvme:target1

# Disconnect all NVMe-oF connections
nvme disconnect-all
```

---

## Cleanup

### Remove Target Configuration
```bash
# Set variables
SUBSYS_NQN="nqn.2026-01.lab:nvme:target1"
PORT_ID="1"

# 1. Unbind subsystem from port
unlink /sys/kernel/config/nvmet/ports/$PORT_ID/subsystems/$SUBSYS_NQN

# 2. Disable namespace
echo 0 > /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN/namespaces/1/enable

# 3. Remove namespace directory
rmdir /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN/namespaces/1

# 4. Remove subsystem directory
rmdir /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN

# 5. Remove port directory
rmdir /sys/kernel/config/nvmet/ports/$PORT_ID
```

### Complete Cleanup Script
```bash
#!/bin/bash
# Complete cleanup of all NVMe target configurations

# Unbind all subsystems from ports
for link in /sys/kernel/config/nvmet/ports/*/subsystems/*; do
    [ -L "$link" ] && unlink "$link" 2>/dev/null
done

# Disable all namespaces
for ns in /sys/kernel/config/nvmet/subsystems/*/namespaces/*; do
    [ -d "$ns" ] && echo 0 > "$ns/enable" 2>/dev/null
done

# Remove all namespaces
for ns in /sys/kernel/config/nvmet/subsystems/*/namespaces/*; do
    [ -d "$ns" ] && rmdir "$ns" 2>/dev/null
done

# Remove all subsystems
for subsys in /sys/kernel/config/nvmet/subsystems/*; do
    [ -d "$subsys" ] && rmdir "$subsys" 2>/dev/null
done

# Remove all ports
for port in /sys/kernel/config/nvmet/ports/*; do
    [ -d "$port" ] && rmdir "$port" 2>/dev/null
done

echo "Cleanup complete"
```

---

## Avocado Test Execution

### Run Single Test
```bash
# Change to test directory
cd /home/avocado-fvt-wrapper/tests/avocado-misc-tests/io/disk/ssd

# Run specific test method
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_load_modules

# Run full target setup test
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup
```

### Run with YAML Configuration
```bash
# Run with specific test scenario
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
    -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml \
    --mux-filter-only /TestScenarios/single_namespace

# Run all test scenarios
avocado run nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
    -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml

# Run with serial execution
avocado run --max-parallel-tasks=1 \
    nvmet_tcp_target.py:NVMeTCPTargetTest.test_full_target_setup \
    -m nvmet_tcp_target.py.data/nvmet_tcp_target.yaml
```

### View Test Results
```bash
# List recent test jobs
avocado jobs list

# Show job results
avocado jobs show <JOB_ID>

# View test log
cat /root/avocado-fvt-wrapper/results/job-<DATE>-<ID>/job.log

# View specific test debug log
cat /root/avocado-fvt-wrapper/results/job-<DATE>-<ID>/test-results/<TEST_NAME>/debug.log
```

---

## Troubleshooting Commands

### Check Module Status
```bash
# Check if modules are loaded
lsmod | grep nvmet

# Check module information
modinfo nvmet
modinfo nvmet-tcp

# Check kernel messages
dmesg | grep -i nvme | tail -20
```

### Check Port Status
```bash
# Check if port is listening
ss -tlnp | grep 4420
netstat -tlnp | grep 4420

# Check network connectivity
ping 192.168.1.49
telnet 192.168.1.49 4420
```

### Check Device Status
```bash
# Check block device
lsblk /dev/nvme0n1

# Check device errors
smartctl -a /dev/nvme0n1

# Check I/O statistics
iostat -x /dev/nvme0n1 1
```

### Debug Connection Issues
```bash
# Enable debug logging
echo 1 > /sys/module/nvmet/parameters/debug

# Check connection attempts in dmesg
dmesg -w | grep nvmet

# Verify subsystem configuration
cat /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN/attr_allow_any_host
cat /sys/kernel/config/nvmet/subsystems/$SUBSYS_NQN/namespaces/1/enable
```

---

## Quick Reference

### One-Line Target Setup
```bash
modprobe nvmet nvmet-tcp && \
mkdir -p /sys/kernel/config/nvmet/subsystems/nqn.2026-01.lab:nvme:target1/namespaces/1 && \
echo 1 > /sys/kernel/config/nvmet/subsystems/nqn.2026-01.lab:nvme:target1/attr_allow_any_host && \
echo -n /dev/nvme0n1 > /sys/kernel/config/nvmet/subsystems/nqn.2026-01.lab:nvme:target1/namespaces/1/device_path && \
echo 1 > /sys/kernel/config/nvmet/subsystems/nqn.2026-01.lab:nvme:target1/namespaces/1/enable && \
mkdir -p /sys/kernel/config/nvmet/ports/1 && \
echo tcp > /sys/kernel/config/nvmet/ports/1/addr_trtype && \
echo ipv4 > /sys/kernel/config/nvmet/ports/1/addr_adrfam && \
echo 192.168.1.49 > /sys/kernel/config/nvmet/ports/1/addr_traddr && \
echo 4420 > /sys/kernel/config/nvmet/ports/1/addr_trsvcid && \
ln -s /sys/kernel/config/nvmet/subsystems/nqn.2026-01.lab:nvme:target1 /sys/kernel/config/nvmet/ports/1/subsystems/nqn.2026-01.lab:nvme:target1
```

### One-Line Initiator Test
```bash
nvme discover -t tcp -a 192.168.1.49 -s 4420 && \
nvme connect -t tcp -n nqn.2026-01.lab:nvme:target1 -a 192.168.1.49 -s 4420 && \
sleep 2 && \
nvme list | grep tcp && \
dd if=/dev/zero of=/dev/nvme2n1 bs=1M count=10 oflag=direct && \
dd if=/dev/nvme2n1 of=/dev/null bs=1M count=10 iflag=direct && \
nvme disconnect -n nqn.2026-01.lab:nvme:target1
```

---

## Environment Variables

```bash
# Common variables used in commands
export SUBSYS_NQN="nqn.2026-01.lab:nvme:target1"
export TARGET_IP="192.168.1.49"
export PORT="4420"
export PORT_ID="1"
export BACKEND_DEV="/dev/nvme0n1"
export NVME_DEV="/dev/nvme2n1"
```

---

## Additional Resources

- NVMe-oF Specification: https://nvmexpress.org/specifications/
- Linux NVMe Target Documentation: https://docs.kernel.org/nvme/nvme-pci-endpoint-target.html
- nvme-cli GitHub: https://github.com/linux-nvme/nvme-cli

---

**Document Information:**
- Created: 2026-02-22
- Author: Naveed AUS <naveedaus@in.ibm.com>
- Test Server: 10.48.35.49
- Copyright: 2026 Naveed AUS, IBM Corporation
- Assisted with AI tools
