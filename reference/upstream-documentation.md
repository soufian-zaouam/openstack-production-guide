# Upstream documentation

Statements in this guide about OpenStack behaviour are based on the official project documentation. OpenStack changes with every release: when a detail matters for a decision, check the documentation for the release you run.

## OpenStack services

- Nova: [system architecture](https://docs.openstack.org/nova/latest/user/architecture.html) · [cells v2](https://docs.openstack.org/nova/latest/admin/cells.html) · [upgrades](https://docs.openstack.org/nova/latest/admin/upgrades.html) · [API microversion history](https://docs.openstack.org/nova/latest/reference/api-microversion-history.html)
- Nova compute features: [CPU topologies and pinning](https://docs.openstack.org/nova/latest/admin/cpu-topologies.html) · [huge pages](https://docs.openstack.org/nova/latest/admin/huge-pages.html) · [PCI passthrough](https://docs.openstack.org/nova/latest/admin/pci-passthrough.html)
- Nova operations: [live migration configuration](https://docs.openstack.org/nova/latest/admin/configuring-migrations.html) · [evacuate](https://docs.openstack.org/nova/latest/admin/evacuate.html) · [nova-manage](https://docs.openstack.org/nova/latest/cli/nova-manage.html) · [nova-status](https://docs.openstack.org/nova/latest/cli/nova-status.html)
- [Placement](https://docs.openstack.org/placement/latest/) and the [osc-placement client plugin](https://docs.openstack.org/osc-placement/latest/)
- Neutron: [administration guide](https://docs.openstack.org/neutron/latest/admin/) · [OVN](https://docs.openstack.org/neutron/latest/ovn/index.html) · [MTU considerations](https://docs.openstack.org/neutron/latest/admin/config-mtu.html)
- [Cinder administration](https://docs.openstack.org/cinder/latest/admin/)
- Keystone: [Fernet tokens FAQ](https://docs.openstack.org/keystone/latest/admin/fernet-token-faq.html)
- [OpenStack client command reference](https://docs.openstack.org/python-openstackclient/latest/cli/command-list.html)
- [oslo.messaging RabbitMQ driver](https://docs.openstack.org/oslo.messaging/latest/admin/rabbit.html)
- [Large Scale SIG documentation](https://docs.openstack.org/large-scale/)

## Lifecycle and security

- [OpenStack release series and their status](https://releases.openstack.org/)
- [Stable branch policy](https://docs.openstack.org/project-team-guide/stable-branches.html)
- [Nova release notes](https://docs.openstack.org/releasenotes/nova/)
- [Consistent and secure default RBAC](https://governance.openstack.org/tc/goals/selected/consistent-and-secure-rbac.html)
- [OpenStack Security Advisories](https://security.openstack.org/ossalist.html)

## Shared components

- Galera: [crash recovery](https://galeracluster.com/library/documentation/crash-recovery.html) · [monitoring the cluster](https://galeracluster.com/library/documentation/monitoring-cluster.html)
- MariaDB: [Galera cluster status variables](https://mariadb.com/kb/en/galera-cluster-status-variables/)
- RabbitMQ: [clustering and network partitions](https://www.rabbitmq.com/docs/partitions) · [quorum queues](https://www.rabbitmq.com/docs/quorum-queues) · [monitoring](https://www.rabbitmq.com/docs/monitoring)
- Ceph: [RBD exclusive locks](https://docs.ceph.com/en/latest/rbd/rbd-exclusive-locks/)

## Related book

- [OpenStack, the Day After Tomorrow — Operating Mission-Critical OpenStack Platforms](https://github.com/soufian-zaouam/openstack-the-day-after-tomorrow): the operating reasoning behind this guide.
