# NVMe-oF Remote Testing Design

This document describes the architecture and design for testing NVMe-oF TCP targets from remote initiator systems.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Network Topology](#network-topology)
3. [Test Execution Models](#test-execution-models)
4. [Implementation Approaches](#implementation-approaches)
5. [Test Scenarios](#test-scenarios)
6. [Automation Framework](#automation-framework)

---

## Architecture Overview

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     Test Orchestrator                            │
│                  (Control/Management Node)                       │
│  - Test scheduling                                               │
│  - Result collection                                             │
│  - Configuration management                                      │
└────────────┬────────────────────────────────┬───────────────────┘
             │                                │
             │                                │
    ┌────────▼────────┐              ┌───────▼────────┐
    │  Target System  │              │ Initiator System│
    │  (10.48.35.49)  │◄────────────►│  (Remote LPAR) │
    │                 │   NVMe-oF    │                 │
    │  - nvmet-tcp    │   TCP/IP     │  - nvme-cli     │
    │  - Backend      │   Network    │  - Test tools   │
    │    devices      │              │  - I/O workload │
    └─────────────────┘              └─────────────────┘
```

### Key Roles

1. **Target System** (10.48.35.49)
   - Runs NVMe-oF TCP target (nvmet-tcp)
   - Exports backend NVMe devices
   - Managed via SSH/Avocado tests

2. **Initiator System** (Remote LPAR)
   - Connects to NVMe-oF targets
   - Runs I/O workloads and validation tests
   - Reports results back to orchestrator

3. **Test Orchestrator** (Optional)
   - Coordinates test execution
   - Manages configuration
   - Collects and aggregates results

---

## Network Topology

### Basic Setup (2-Node)

```
Target System (10.48.35.49)
├── Management Network: 10.48.35.49/21
├── Data Network 1: 192.168.1.49/24  ← NVMe-oF Traffic
└── Data Network 2: 192.168.2.49/24  ← NVMe-oF Traffic (Multipath)

Initiator System (Remote)
├── Management Network: 10.48.35.X/21
├── Data Network 1: 192.168.1.X/24   ← NVMe-oF Traffic
└── Data Network 2: 192.168.2.X/24   ← NVMe-oF Traffic (Multipath)
```

### Requirements

- **Network Connectivity**: Direct L2/L3 connectivity between target and initiator
- **Bandwidth**: Minimum 1Gbps, recommended 10Gbps or higher
- **Latency**: Low latency network (<1ms for best performance)
- **Firewall**: Port 4420 (default NVMe-oF TCP) must be open
- **MTU**: Jumbo frames (9000) recommended for better performance

---

## Test Execution Models

### Model 1: Sequential Execution
**Pros**: Simple, easy to debug  
**Cons**: Slower, no parallelization

### Model 2: Parallel Execution
**Pros**: Faster, tests scalability  
**Cons**: More complex coordination

### Model 3: Continuous Testing
**Pros**: Real-world scenario, stress testing  
**Cons**: Requires monitoring infrastructure

---

## Implementation Approaches

### Approach 1: SSH-Based Remote Execution
- Use Paramiko/Fabric/Ansible
- Direct SSH to target and initiator
- Simple orchestration scripts

### Approach 2: Avocado Distributed Testing
- Leverage Avocado framework
- Remote test execution
- Built-in result collection

### Approach 3: Ansible Playbook Orchestration
- Infrastructure as code
- Declarative configuration
- Easy to maintain and scale

### Approach 4: Custom Python Framework
- Full control over test flow
- Custom reporting
- Flexible integration

---

## Test Scenarios

### Scenario 1: Basic Connectivity
Verify target accessibility from initiator

### Scenario 2: I/O Performance
Measure throughput and IOPS using FIO

### Scenario 3: Multipath
Test failover between multiple paths

### Scenario 4: Stress Test
Heavy load with multiple concurrent jobs

### Scenario 5: Reconnection
Connection stability testing

---

## Best Practices

1. **Network**: Dedicated network, jumbo frames, VLAN isolation
2. **Target**: Separate devices, enable cleanup, monitor resources
3. **Initiator**: Latest nvme-cli, multipath config, appropriate queue depth
4. **Testing**: Baseline first, gradual load increase, failure scenarios
5. **Analysis**: Compare baselines, check logs, analyze trends

---

**Document Information:**
- Created: 2026-02-22
- Author: Naveed AUS <naveedaus@in.ibm.com>
- Copyright: 2026 Naveed AUS, IBM Corporation
- Assisted with AI tools
