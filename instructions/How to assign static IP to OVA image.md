## Steps

- Identify available network interface
  
  ```sh
   ip link show
  ```
   1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
   2: ens33: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP mode DEFAULT group default qlen 1000 link/ether 00:0c:29:00:22:80 brd ff:ff:ff:ff:ff:ff
 
- Enable the network interface

```sh
sudo ifconfig ens33 up
```

```sh
sudo nano 01-network-manager-all.yaml
```

- Add below content to `/etc/netplan/01-network-manager-all.yaml`. Mention network interface name and other network details accordingly.

Sample:
```yaml
network:
    ethernets:
        ens33:
            addresses: [91.109.26.22/27]
            gateway4: 91.109.26.30
            nameservers:
              addresses: [8.8.4.4,8.8.8.8]
    version: 2
```

- Once done run below commands to apply network changes

```sh
sudo netplan apply
reboot
```
Refer this link for more information - https://www.howtoforge.com/linux-basics-set-a-static-ip-on-ubuntu
