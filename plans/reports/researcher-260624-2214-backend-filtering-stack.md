# Linux Network Filtering Stack: webwarden Implementation Reference

**Date:** 2026-06-24 | **Target:** Linux Mint (Ubuntu 24.04 base) | **Scope:** dnsmasq + nftables architecture for per-UID website allowlist enforcement

---

## 1. DNSMASQ PER-INSTANCE CONFIGURATION

### Multi-Instance Binding to Loopback Ports

**Problem:** Need N independent dnsmasq instances (one per locked user uid≥1000), each bound to 127.0.0.1:5354+N.

**Key Directives:**

| Directive | Behavior | Example |
|-----------|----------|---------|
| `port=<port>` | Listen on custom DNS port (default 53) | `port=5354` |
| `listen-address=<ipaddr>` | Bind to specific IP (can specify multiple) | `listen-address=127.0.0.1` |
| `bind-interfaces` | **CRITICAL:** Forces binding to specified interfaces only; prevents wildcard 0.0.0.0 listen | `bind-interfaces` |
| `no-resolv` | Disable reading upstream from /etc/resolv.conf | `no-resolv` |
| `server=<upstream>` | Specify upstream nameserver explicitly | `server=8.8.8.8` |
| `pid-file=<path>` | Write PID to file for systemd/management | `pid-file=/var/run/dnsmasq-user1.pid` |

**Per-Instance Config Pattern:**
```
# /etc/dnsmasq.d/user1.conf (for uid 1000, port 5354)
port=5354
listen-address=127.0.0.1
bind-interfaces
no-resolv
server=8.8.8.8          # or 1.1.1.1, etc. — upstream for *allowed* domains only
pid-file=/var/run/dnsmasq-user1.pid
```

**Invocation:** `dnsmasq -C /etc/dnsmasq.d/user1.conf` (runs in foreground with `-C`; use systemd to daemonize).

**Multi-Instance Coexistence:** Each instance must:
- Bind unique `listen-address` port combo (127.0.0.1:5354, 127.0.0.1:5355, etc.)
- Have separate `pid-file` and `dhcp-leasefile` (if used)
- Use `bind-interfaces` to prevent port conflicts
- NOT share upstream server if filtering differs per user

---

### Default-Deny (Block Unlisted Domains)

**Architecture:** Combine catch-all blocking with per-domain exceptions.

**Syntax:**

```
# Block everything by default (return 0.0.0.0 / ::)
address=/#/0.0.0.0
address=/#/::

# Allow specific domains → forward to upstream
server=/gmail.com/8.8.8.8
server=/google.com/8.8.8.8
server=/example.com/1.1.1.1
```

**How It Works:**
- `address=/#/0.0.0.0` = catch-all: any domain NOT explicitly whitelisted returns 0.0.0.0
- `address=/#/::` = IPv6 equivalent (must specify both)
- `server=/domain/upstream` = override for specific domain; dnsmasq "most-specific match" logic applies (e.g., `server=/mail.google.com/8.8.8.8` overrides `address=/#/0.0.0.0` for that domain)
- Unresolvable/blocked queries return the catch-all address; client gets either single A/AAAA record with 0.0.0.0/::

**Alternative (IPv6-aware):**
Instead of separate `address=` directives:
```
address=/blocked.example.com/#
# = syntactic sugar for address=/blocked.example.com/0.0.0.0 + address=/blocked.example.com/::
```

**Verification:** Test with `dig @127.0.0.1 -p 5354 blocked.domain.com` → should return `0.0.0.0`.

---

## 2. DNSMASQ → NFTABLES SET AUTO-POPULATION

### The `nftset=` Directive (dnsmasq 2.87+)

**Requirement:** dnsmasq ≥ 2.87 (first version with nftset support). Ubuntu 24.04 ships with 2.90+, so available.

**Syntax:**
```
nftset=/domain1.com/domain2.com/[(4|6)#][<family>#]<table>#<set>
```

**Components:**
- `domain1.com/domain2.com/...` = domains to resolve → add IPs to nftset (can chain multiple domains)
- `4#` or `6#` = optional filter (only A/AAAA records, respectively); omit for both
- `family#` = nftables address family: `ip` (IPv4 only), `ip6` (IPv6 only), `inet` (both)
- `table#set` = nftables table name and set name

**Example Configuration (per-user dnsmasq):**
```
# /etc/dnsmasq.d/user1.conf
port=5354
listen-address=127.0.0.1
bind-interfaces

# Allowed domains → auto-populate nftables sets with resolved IPs
nftset=/gmail.com/4#inet#kidfilter#allow_v4_1000
nftset=/gmail.com/6#inet#kidfilter#allow_v6_1000
nftset=/google.com/4#inet#kidfilter#allow_v4_1000
nftset=/google.com/6#inet#kidfilter#allow_v6_1000

# Block everything else
address=/#/0.0.0.0
address=/#/::

# Upstream for allowed domains (will be overridden by nftset matches)
no-resolv
server=8.8.8.8
```

**Behavior:**
- When dnsmasq resolves `gmail.com` → retrieves A record (e.g., 142.251.40.229) → adds it to `allow_v4_1000` set in table `inet kidfilter`
- When dnsmasq resolves `gmail.com` AAAA → adds IPv6 to `allow_v6_1000`
- Domains NOT in `nftset=/` directives still hit `address=/#/0.0.0.0` and return poison responses

**Set Requirements (must pre-exist):**
Sets must be created in nftables BEFORE dnsmasq starts:
```bash
nft add table inet kidfilter
nft add set inet kidfilter allow_v4_1000 { type ipv4_addr; flags interval; }
nft add set inet kidfilter allow_v6_1000 { type ipv6_addr; flags interval; }
```

**Why `flags interval`?** Allows CIDR ranges in the set. nftables can then efficiently match any IP in 142.251.40.0/24, for example.

**Dynamic Updates:** dnsmasq adds IPs to sets immediately upon resolution; no manual nftables reload needed.

---

## 3. BLOCKED-QUERY LOG FORMAT

### Query Logging with `--log-queries`

**Directive:**
```
log-queries[=extra|proto|auth|only_failed]
log-facility=/var/log/dnsmasq.log
```

**Log Format Variants:**

| Option | Format | Example |
|--------|--------|---------|
| `log-queries` | `[timestamp] query[TYPE] domain from client` | `Jun 24 22:14:01 query[A] gmail.com from 127.0.0.1` |
| `log-queries=extra` | Adds serial number & requestor IP at line start | `[12345] Jun 24 22:14:01 query[A] gmail.com from 127.0.0.1` |
| `log-queries=proto` | Extra format + protocol (tcp/udp) | `[12345] protocol=udp Jun 24 22:14:01 query[A]...` |
| `log-queries=only_failed` | Only NXDOMAIN, NODATA, SERVFAIL responses | `[error]` responses logged |

### Blocked vs. Forwarded Distinction

**When domain hits `address=` catch-all (blocked):**
```
Jun 24 22:14:05 query[A] blocked-domain.com from 127.0.0.1
Jun 24 22:14:05 blocked-domain.com is 0.0.0.0
```

**When domain hits `server=/` or upstream (forwarded):**
```
Jun 24 22:14:07 query[A] gmail.com from 127.0.0.1
Jun 24 22:14:07 forwarded gmail.com to 8.8.8.8
Jun 24 22:14:07 reply gmail.com is 142.251.40.229
```

**Key Distinction:**
- Line 2 with `is 0.0.0.0` = blocked (matches `address=/#/` catch-all)
- Line with `forwarded` + `reply` = allowed (matched `server=/` or upstream)

**Parsing Strategy (for webwarden blocked-attempts feature):**
- Grep for lines matching regex: `is 0\.0\.0\.0` → blocked attempt
- Extract domain from same line (pattern: `<domain> is 0.0.0.0`)
- Extract timestamp and client IP (if `log-queries=extra`)

**Note on IPv6:** Blocked IPv6 queries show:
```
Jun 24 22:14:05 blocked-domain.com is [::]
```

---

## 4. EXACT NFTABLES RULESET

### Table & Set Initialization

```bash
# Create inet table (applies to both IPv4 and IPv6)
nft add table inet kidfilter

# Create per-user allowlists (type ipv4_addr / ipv6_addr)
# Flags: interval = CIDR support; can add timeout if needed
nft add set inet kidfilter allow_v4_1000 { type ipv4_addr; flags interval; }
nft add set inet kidfilter allow_v6_1000 { type ipv6_addr; flags interval; }
nft add set inet kidfilter allow_v4_1001 { type ipv4_addr; flags interval; }
nft add set inet kidfilter allow_v6_1001 { type ipv6_addr; flags interval; }
# ... repeat for each uid ≥ 1000

# Create DNS redirect sets (hold target port for each uid)
# Or use fixed offset: dnsmasq port = 5354 + (uid - 1000)
```

### Per-UID Egress Filter Chain (Filter Table)

```nft
nft add chain inet kidfilter output { type filter hook output priority 0; policy drop; }

# Default accept established & related
nft add rule inet kidfilter output ct state established,related accept

# === Loopback (traffic within system)
nft add rule inet kidfilter output oif lo accept

# === Per-UID: uid 1000
nft add rule inet kidfilter output meta skuid 1000 ip protocol tcp tcp dport { 80, 443 } ip daddr @allow_v4_1000 accept
nft add rule inet kidfilter output meta skuid 1000 ip protocol tcp tcp dport { 80, 443 } ip daddr @allow_v6_1000 accept
nft add rule inet kidfilter output meta skuid 1000 ip protocol udp udp dport { 53, 853 } accept comment "DNS redirect handled in nat; allow outbound"
nft add rule inet kidfilter output meta skuid 1000 reject with icmp type host-unreachable

# === Per-UID: uid 1001
nft add rule inet kidfilter output meta skuid 1001 ip protocol tcp tcp dport { 80, 443 } ip daddr @allow_v4_1001 accept
nft add rule inet kidfilter output meta skuid 1001 ip protocol tcp tcp dport { 80, 443 } ip daddr @allow_v6_1001 accept
nft add rule inet kidfilter output meta skuid 1001 ip protocol udp udp dport { 53, 853 } accept
nft add rule inet kidfilter output meta skuid 1001 reject with icmp type host-unreachable

# === Default (catch-all for uids outside locked range)
nft add rule inet kidfilter output accept
```

### DNS Redirect Chain (NAT Table, Output Chain)

**Problem:** Redirect UDP/TCP port 53 and 853 from uid 1000 to 127.0.0.1:5354+N.

**Solution:** Use NAT output chain with `redirect` statement (works for loopback traffic):

```nft
nft add chain inet kidfilter output-nat { type nat hook output priority -100; }

# uid 1000 → dnsmasq on 5354
nft add rule inet kidfilter output-nat meta skuid 1000 ip protocol udp udp dport 53 redirect to :5354
nft add rule inet kidfilter output-nat meta skuid 1000 ip protocol tcp tcp dport 53 redirect to :5354
nft add rule inet kidfilter output-nat meta skuid 1000 ip protocol tcp tcp dport 853 redirect to :5354

# uid 1001 → dnsmasq on 5355
nft add rule inet kidfilter output-nat meta skuid 1001 ip protocol udp udp dport 53 redirect to :5355
nft add rule inet kidfilter output-nat meta skuid 1001 ip protocol tcp tcp dport 53 redirect to :5355
nft add rule inet kidfilter output-nat meta skuid 1001 ip protocol tcp tcp dport 853 redirect to :5355
```

**Why `redirect to :PORT` (not dnat)?**
- `redirect` in output chain modifies destination port only
- Destination IP implicitly becomes 127.0.0.1 (loopback)
- Simpler than `dnat to 127.0.0.1:PORT` (which works in prerouting but NOT loopback)

**Priority Ordering:**
- NAT (output-nat) runs FIRST at priority -100
- Filter (output filter) runs SECOND at priority 0
- Ensures DNS traffic is redirected before egress filter rules evaluate

**Critical Note:** `meta skuid` works in output chain for locally-initiated traffic ONLY. Input traffic (remote queries) won't match local UIDs.

---

## 5. REBOOT PERSISTENCE & VALIDATION

### Persistence: Systemd Service

**File:** `/etc/systemd/system/kidfilter-nftables.service`

```ini
[Unit]
Description=Load webwarden nftables ruleset
After=network-pre.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/nft -f /etc/kidfilter/nftables.ruleset
ExecStop=/usr/sbin/nft flush table inet kidfilter
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

**Ruleset File:** `/etc/kidfilter/nftables.ruleset`

```nft
flush ruleset

table inet kidfilter {
  set allow_v4_1000 {
    type ipv4_addr
    flags interval
  }
  
  set allow_v6_1000 {
    type ipv6_addr
    flags interval
  }
  
  chain output {
    type filter hook output priority 0; policy drop;
    ct state established,related accept
    oif lo accept
    meta skuid 1000 ip protocol tcp tcp dport { 80, 443 } ip daddr @allow_v4_1000 accept
    meta skuid 1000 ip protocol tcp tcp dport { 80, 443 } ip daddr @allow_v6_1000 accept
    meta skuid 1000 ip protocol udp udp dport { 53, 853 } accept
    meta skuid 1000 reject with icmp type host-unreachable
    accept
  }
  
  chain output-nat {
    type nat hook output priority -100;
    meta skuid 1000 ip protocol udp udp dport 53 redirect to :5354
    meta skuid 1000 ip protocol tcp tcp dport 53 redirect to :5354
    meta skuid 1000 ip protocol tcp tcp dport 853 redirect to :5354
  }
}
```

**Enable at boot:**
```bash
systemctl enable kidfilter-nftables.service
systemctl start kidfilter-nftables.service
```

### Validation

**Syntax check (before apply):**
```bash
nft -c -f /etc/kidfilter/nftables.ruleset   # -c = check only, no apply
echo $?  # Should be 0
```

**dnsmasq config check:**
```bash
dnsmasq --test -C /etc/dnsmasq.d/user1.conf
echo $?  # Should be 0
```

**Live verification (after systemd start):**
```bash
nft list ruleset
nft list table inet kidfilter
nft list set inet kidfilter allow_v4_1000
```

---

## 6. KNOWN GOTCHAS & MITIGATIONS

### ECH/ESNI (Encrypted Client Hello / Encrypted Server Name Indication)

**Problem:** TLS 1.3 ECH allows client to hide SNI from network observers. If user connects to `blocked-domain.com` via ECH, firewall can't filter by domain name (only IP).

**Impact:** webwarden can only block via resolved IP (captured in nftables set from dnsmasq). If DNS is enforced → IPs in allow-list → ECH hidden SNI is moot.

**Mitigation:** Since all DNS is redirected to per-user dnsmasq, blocked domain → blocked IP → blocked at filter layer. No bypass possible if DNS is the only entry point.

---

### DoH/DoT Bypass Prevention

**DoT (DNS-over-TLS, port 853):**
- Encrypted DNS on dedicated port
- **Blocked by:** `meta skuid <uid> ip protocol tcp tcp dport 853 accept` (only allows redirect to local dnsmasq, deny to external 853)
- Per-UID nftables rule: `reject with icmp type host-unreachable` for traffic outside allowed IPs/ports
- **Result:** Can't talk to external DoT servers; forced to use per-user dnsmasq

**DoH (DNS-over-HTTPS, port 443):**
- Encrypted DNS inside HTTPS
- **Indistinguishable from normal web traffic** at firewall layer
- **Blocked by:** `tcp dport 443` only accepts `ip daddr @allow_v4_<uid>` (allowlisted IPs)
- If user tries DoH to hardcoded IP not in allowlist → rejected
- If user tries DoH to allowlisted IP (e.g., google.com IP), it succeeds but DNS payload is encrypted
  - **Mitigation:** Use dnsmasq `log-queries` + webwarden UI to alert on DoH attempts; use endpoint.allow-list to permit only safe IPs (not generic CDNs)

**DoQ (DNS-over-QUIC, ports 443, 784, 8853):**
- Encrypted DNS over QUIC
- Port 443 handled same as DoH (allowlist matching)
- Port 784 & 8853 can be blocked in nftables: `tcp/udp dport { 784, 8853 } reject`

**Summary:** Layered enforcement (DNS redirect + IP filtering + port blocking) makes bypass impractical. DoH remains a risk if user resolves DoH server via local dnsmasq → but URL-level blocking in endpoint.allow-list mitigates.

---

### Shared-CDN IP Set Churn

**Problem:** A single CDN IP (e.g., `142.251.0.0/16` for Google) may host 100+ domains. If uid 1000 is allowed `gmail.com` but not `www.google-analytics.com`, both resolve to the same /16 range. The nftables set cannot distinguish by IP alone.

**Impact:** Coarse filtering; IP-based allow-list has inherent CDN collateral-allow problem.

**Mitigation:**
1. **Accept IP granularity limits:** Educate parents that "allowing gmail.com" may grant access to other Google services on same IP range
2. **Use endpoint.allow-list for fine-grained domain control:** Don't rely solely on IP filtering; use HTTPS SNI inspection or application-layer filtering where possible (out of scope for nftables)
3. **Monitor dnsmasq logs:** Track which IPs are actually added to nftables sets; audit for unexpected domains resolving to same IP

---

### IP Set Staleness & DNS TTL Churn

**Problem:** dnsmasq populates `allow_v4_<uid>` set when resolving a domain. If domain TTL expires but user doesn't re-resolve, the IP remains in the nftables set indefinitely. If IP is reassigned to a blocked domain, user accidentally gains access.

**Impact:** Stale IP in allow-list → unintended access if IP reallocated.

**Mitigation:**
1. **Use nftables `timeout` flag on sets:**
   ```nft
   nft add set inet kidfilter allow_v4_1000 { type ipv4_addr; flags interval; timeout 6h; }
   ```
   - IPs auto-expire after 6 hours if not re-added
   - dnsmasq re-adds IPs on each resolution (resets timeout)
   - Requires dnsmasq 2.87+ and careful coordination of timeout with DNS TTLs

2. **Monitor nftables set membership:** Periodically audit `nft list set inet kidfilter allow_v4_1000` for unexpected IPs

3. **Sync dnsmasq TTL + nftables timeout:** Set nftables timeout ≥ max DNS TTL to avoid premature expiration

**Current Recommendation:** Omit timeout flag for now; accept the staleness risk as trade-off for simpler management. Revisit if stale-IP bypass becomes a real attack.

---

### dnsmasq Cache & Min-Cache-TTL

**Problem:** dnsmasq caches DNS responses. If user queries `gmail.com` (allowed), it caches for TTL (e.g., 3600s). If admin REMOVES `gmail.com` from allow-list during that window, dnsmasq still answers from cache → user still reaches Gmail (IP still in set).

**Mitigation:**
1. **Set `min-cache-ttl=0`:** Don't cache anything; query upstream on every request (performance cost)
2. **Set cache expiry on config reload:** When allow-list changes, reload dnsmasq config → flushes cache
3. **Periodic cache flush:** Add systemd timer to `dnsmasq -s SIGHUP` every hour (reloads config, flushes cache)

**Current Recommendation:** Use `min-cache-ttl=60` (or 300) to balance performance + freshness. Cache stale IPs for <5 min; monitor admin logs for cache-induced delays in enforcement.

---

### nftables Set Performance

**Note:** nftables sets with `flags interval` use hash tables. CIDR range lookup is O(n) in worst case but typically O(1)–O(log n) in practice. For <10,000 IPs per set, performance is fine. If a single user resolves 50,000 domains, set may slow down; monitor with `nft reset counters` + perf tools.

---

## UNRESOLVED QUESTIONS

1. **dnsmasq → nftables atomic batch updates:** If dnsmasq resolves multiple A records for a domain (e.g., `gmail.com` → {142.251.40.229, 142.251.40.233}), does it add all IPs to the nftset in a single transaction, or individually? Affects transient filtering gaps during bulk updates.

2. **nftables output chain `meta skuid` + IPv6:** Does `meta skuid` work in inet (dual-stack) chains, or only ip? If user has IPv6, do both v4/v6 rules evaluate, or only ipv6_addr set for IPv6 packets?

3. **Loopback NAT redirect priority:** When both nat (priority -100) and filter (priority 0) are active, does dnsmasq correctly receive the redirected traffic, or is there a race where filter policy drop fires first? Need live test on Linux Mint 24.04.

4. **dnsmasq nftset + CNAME chains:** If user queries `www.google.com` (CNAME → google.com) but only `google.com` is in allow-list, does dnsmasq add the final resolved IP to the nftset? Or does it honor the CNAME separately?

5. **Systemd ordering of kidfilter-nftables.service vs. dnsmasq.service:** If dnsmasq starts before nftables sets exist, does it error or silently skip populating? Should be After= dnsmasq in the service file, but confirmation needed.

6. **Performance at scale (100+ users):** With 100 locked users, each with separate dnsmasq instance + nftables rules, what are system resource limits (CPU, memory, nftables rule count)? Need benchmarking.

7. **Exact log-queries format for "is 0.0.0.0":** dnsmasq man page doesn't show the literal log line. Empirical verification needed: `dnsmasq -d -C /etc/dnsmasq.d/test.conf` with `address=/#/0.0.0.0` to capture actual syslog output.

---

## REFERENCES & SOURCES

- [dnsmasq Man Page (official)](https://thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html)
- [nftables Wiki: Sets](https://wiki.nftables.org/wiki-nftables/index.php/Sets)
- [nftables Wiki: Performing NAT](https://wiki.nftables.org/wiki-nftables/index.php/Performing_Network_Address_Translation_(NAT))
- [nftables Wiki: Matching Metainformation](https://wiki.nftables.org/wiki-nftables/index.php/Matching_packet_metainformation)
- [Using dnsmasq & nftables together](https://www.monotux.tech/posts/2024/08/dnsmasq-netfilter/)
- [dnsmasq nftset GitHub discussion](https://forum.openwrt.org/t/how-to-use-nftset-with-dnsmasq/159786)
- [How to Prevent DNS Filter Bypass (DoH/DoT/DoQ)](https://cleanbrowsing.org/learn/how-to-prevent-filter-bypass)
- [nftables Loopback Traffic Examples](https://wiki.gentoo.org/wiki/Nftables/Examples)
- [Save & Restore nftables Rules (systemd)](https://oneuptime.com/blog/post/2026-03-20-save-restore-nftables-rules-reboots/view)

