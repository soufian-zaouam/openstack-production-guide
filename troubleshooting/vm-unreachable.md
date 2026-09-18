# VM is ACTIVE but unreachable

`ACTIVE` means Nova believes the VM is running. It says nothing about the network path or the guest. Walk the path in order, and stop where the evidence changes.

> [!TIP]
> Security groups are not the first suspect by default. A port that is DOWN or unbound, or a dead agent, produces the same symptom. Check steps 1 to 3 before reading rules.

## 1. VM state

**Is it really running where Nova says?**

```bash
# control plane
openstack server show <vm> -c status -c OS-EXT-STS:power_state \
  -c OS-EXT-SRV-ATTR:host -c OS-EXT-SRV-ATTR:instance_name
# on that compute node
virsh domstate <instance_name>
```

Signal: power state not Running, or a domain that does not exist on the host Nova names.

## 2. Compute host and its network agent

**Are the host and its networking components healthy?**

```bash
# control plane
openstack compute service list --host <compute>
openstack network agent list --host <compute>
```

Signal: the Open vSwitch agent (ML2/OVS) or the OVN controller agent (ML2/OVN) not alive on that host.

## 3. Neutron port

**Is the port bound on that host, and ACTIVE?**

```bash
openstack port list --server <vm>
openstack port show <port> -c status -c binding_host_id -c binding_vif_type \
  -c fixed_ips -c mac_address -c admin_state_up
```

Signals: `status` DOWN, `binding_vif_type` = `binding_failed` or `unbound`, `binding_host_id` different from the VM's host.

## 4. Network and subnet

**Is the addressing plan what the guest expects?**

```bash
openstack network show <network> -c mtu -c provider:network_type -c port_security_enabled
openstack subnet show <subnet> -c cidr -c gateway_ip -c enable_dhcp -c host_routes -c dns_nameservers
```

Signal: a wrong gateway, DHCP disabled, or an MTU the guest does not use. An MTU mismatch lets ping through and breaks SSH or TLS.

## 5. Security groups

**Is this traffic allowed?**

```bash
openstack port show <port> -c security_group_ids -c port_security_enabled
openstack security group rule list <security-group> --long
```

Signal: no ingress rule for the protocol and port, or a remote prefix that does not include the client.

## 6. Floating IP

**Is the floating IP attached and routable?**

```bash
openstack floating ip show <floating-ip> -c port_id -c fixed_ip_address -c status -c router_id
openstack router show <router> -c external_gateway_info
```

Signal: floating IP not associated with the VM's port, or a router without an external gateway.

## 7. DHCP and metadata

**Did the guest get its address and its configuration?**

- Console log (`openstack console log show <vm>`): look for DHCP lease and cloud-init metadata lines.
- ML2/OVS: the DHCP agent serving the network is alive (`openstack network agent list --agent-type dhcp`), and the `qdhcp-<network-id>` namespace exists on its node.
- ML2/OVN: DHCP is answered by `ovn-controller` on the compute node itself; check that it is connected (step 9).
- Metadata: the metadata agent (OVS) or OVN metadata agent is alive on the relevant node.

## 8. Router

**Is the router up, and hosted where it should be?**

```bash
openstack router show <router> -c status -c external_gateway_info -c interfaces_info
# ML2/OVS: which L3 agent hosts it, and its HA state
openstack network agent list --router <router> --long
```

For ML2/OVN, the gateway chassis where the router's external port is bound appears in `ovn-sbctl show` (see [Networking](networking.md)).

## 9. OVS / OVN data plane

**Do packets leave the tap and match the right flows?**

```bash
# on the compute node
ip link show tap<first-11-chars-of-port-id>
tcpdump -eni tap<first-11-chars-of-port-id>
ovs-ofctl dump-flows br-int          # run twice: are packet counters moving?
# ML2/OVN
ovn-appctl -t ovn-controller connection-status
```

Signal: no packets on the tap (guest side problem), packets on the tap but not on the physical interface (host side), or counters that never move.

## 10. Guest OS

**Is the guest itself refusing?**

Use the console (`openstack console url show <vm>`) or the console log: interface up, address configured, default route, guest firewall, service listening.

## 11. Test from several points

**Where exactly does reachability stop?**

| Works from | Fails from | Suspect |
| --- | --- | --- |
| Nowhere, not even the same network | — | Guest, tap / port binding, security groups on the port |
| Same network only | Router, external | Gateway in the guest, router interface, router hosting |
| Router namespace or gateway | External | Floating IP / SNAT, external network, upstream routing |
| Small packets (ping) | Large packets (SSH, TLS) | MTU along the overlay or the physical path |
| VMs on other hosts | VMs on one host | That host: agent / ovn-controller, tunnel endpoint, NIC, bond |

With ML2/OVS, testing from the DHCP or router namespace is a precise probe:

```bash
# on the node hosting the namespace
ip netns exec qdhcp-<network-id> ping -c 3 <vm-fixed-ip>
```

## Go deeper

Episodes of [One Command, One Investigation](../series/one-command-one-investigation/README.md) on the commands of this page: [#01 `openstack server show`](../series/one-command-one-investigation/01-openstack-server-show.md) · [#04 `virsh list --all`, `virsh domstate --reason`](../series/one-command-one-investigation/04-virsh-list-domstate.md) · [#06 `openstack console log show`](../series/one-command-one-investigation/06-openstack-console-log-show.md) · [#07 `openstack port show`](../series/one-command-one-investigation/07-openstack-port-show.md) · [#08 `openstack network agent list`](../series/one-command-one-investigation/08-openstack-network-agent-list.md) · [#09 `ovs-vsctl`, `ovs-ofctl`, `ofproto/trace`](../series/one-command-one-investigation/09-ovs-vsctl-ofctl.md) · [#10 `ovn-nbctl`, `ovn-sbctl`, `ovn-trace`](../series/one-command-one-investigation/10-ovn-nbctl-sbctl.md) · [#11 `ip netns`: DHCP, router and metadata namespaces](../series/one-command-one-investigation/11-ip-netns.md).

Incident case studies where this page's checks were used under pressure: [Ceph full OSD and CRUSH weights](../incidents/ceph-full-osd-crush-weights.md).

Looking for an exact error message? See the [index by error message](../errors.md).

---
Next: [Networking](networking.md) · Back to [first commands](vm-first-commands.md)
