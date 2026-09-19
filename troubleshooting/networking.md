# Networking

Follow one packet. Every hop has a place to look, and the first hop where the packet disappears is your layer.

```text
VM (eth0) → tap<port> → br-int (OVS / OVN) → provider bridge or tunnel → physical NIC
          → fabric (VLAN / VXLAN / Geneve) → router → external network
```

| Hop | Where | What to check |
| --- | --- | --- |
| VM | guest | Interface up, address, routes, guest firewall |
| tap | compute node | `tap` + first 11 characters of the port UUID; exists and UP |
| br-int | compute node | Port present, flows matching, security group rules (OVS firewall or OVN ACLs) |
| Provider bridge / tunnel | compute or network node | Bridge mappings, tunnel endpoints, encapsulation |
| Physical NIC | node | Link, bond, VLAN, errors, MTU |
| Fabric | infrastructure | VLAN trunking, MTU, reachability between tunnel endpoints |
| Router | network node (ML2/OVS) or gateway chassis (ML2/OVN) | Router interfaces, SNAT, floating IP NAT |
| External network | infrastructure | Upstream routing, return path |

## Control plane: what OpenStack believes

```bash
openstack port show <port>              # bound? on which host? ACTIVE? which security groups?
openstack network show <network>        # type, segmentation ID, MTU
openstack subnet show <subnet>          # gateway, DHCP, host routes
openstack router show <router>          # external gateway, interfaces
openstack floating ip show <floating-ip> # attached to which port?
openstack network agent list --host <node>   # agents alive on that node?
```

## Compute or network node: what the host does

```bash
ip link | grep tap<first-11-chars-of-port-id>   # tap exists and is UP?
ip addr ; ip route                              # underlay addressing and routes
ovs-vsctl show                                  # bridges, ports, tunnels
ovs-vsctl --columns=name,ofport,external_ids find Interface \
  external_ids:iface-id=<port-uuid>             # which OVS port is this Neutron port?
ovs-ofctl dump-flows br-int                     # run twice: are n_packets moving?
ovs-appctl ofproto/trace br-int <flow>          # which rule handles or drops the packet?
tcpdump -eni tap<first-11-chars-of-port-id>     # does traffic leave the VM?
tcpdump -eni <physical-interface> <filter>      # does it reach the wire?
```

> [!TIP]
> Read counters, not rules. A flow whose `n_packets` never moves is not on the path, however plausible it looks.

## ML2/OVS specifics

Routers and DHCP live in network namespaces on the nodes that host them.

```bash
# on the node hosting the router or the DHCP server
ip netns                                          # qrouter-<router-id>, qdhcp-<network-id>
ip netns exec qrouter-<router-id> ip addr         # router interfaces and floating IPs
ip netns exec qrouter-<router-id> ip route
ip netns exec qdhcp-<network-id> ping -c 3 <vm-fixed-ip>
```

```bash
# control plane
openstack network agent list --agent-type l3
openstack network agent list --agent-type dhcp
openstack network agent list --router <router> --long   # HA state of an HA router
```

## ML2/OVN specifics

Neutron translates its resources into the OVN northbound database; `ovn-northd` compiles them into the southbound database; `ovn-controller` on each chassis programs OVS.

```bash
# on a node with access to the OVN databases
ovn-nbctl show                       # logical switches, routers and ports
ovn-sbctl show                       # chassis, and which ports are bound where
ovn-sbctl find Port_Binding logical_port=<port-uuid>
ovn-trace <logical-switch> '<microflow>'   # what the logical pipeline does with a packet
```

```bash
# on a compute node
ovn-appctl -t ovn-controller connection-status   # connected to the southbound DB?
ovs-vsctl get Open_vSwitch . external_ids        # ovn-remote, system-id, encapsulation
```

- DHCP is answered locally by `ovn-controller`; there is no DHCP agent.
- A port bound in Neutron but absent from `Port_Binding`, or bound to another chassis, points to OVN synchronisation or chassis registration.

## Frequent causes, and their signals

| Symptom | Likely cause | Signal |
| --- | --- | --- |
| Ping works, SSH hangs after the banner, TLS stalls | MTU | Overlay networks subtract encapsulation overhead; large packets are dropped |
| All VMs on one host unreachable | Host agent or ovn-controller, tunnel endpoint, NIC | Agent not alive, `connection-status` not connected, tunnel interface down |
| New VMs get no address, existing ones work | DHCP (agent or OVN), RabbitMQ between server and agents | DHCP agent down, port stays DOWN |
| Floating IP unreachable, fixed IP fine | Router, NAT, external network | Router not hosted, no external gateway, gateway chassis not bound |
| Intermittent loss on one network | Duplicate MAC or IP, fabric | `tcpdump -e` shows unexpected MAC addresses |

> [!WARNING]
> **Changes state.** Restarting the Open vSwitch agent, `ovn-controller` or `openvswitch` on a compute node can interrupt traffic for every instance on that host, depending on version and configuration. It is a data-plane action, not a control-plane one. Plan it like a maintenance.

## Go deeper

Episodes of [One Command, One Investigation](../series/one-command-one-investigation/README.md) on the commands of this page: [#07 `openstack port show`](../series/one-command-one-investigation/07-openstack-port-show.md) · [#08 `openstack network agent list`](../series/one-command-one-investigation/08-openstack-network-agent-list.md) · [#09 `ovs-vsctl`, `ovs-ofctl`, `ofproto/trace`](../series/one-command-one-investigation/09-ovs-vsctl-ofctl.md) · [#10 `ovn-nbctl`, `ovn-sbctl`, `ovn-trace`](../series/one-command-one-investigation/10-ovn-nbctl-sbctl.md) · [#11 `ip netns`: DHCP, router and metadata namespaces](../series/one-command-one-investigation/11-ip-netns.md).

Looking for an exact error message? See the [index by error message](../errors.md).

---
Next: [Storage](storage.md) · Back to [VM unreachable](vm-unreachable.md)
