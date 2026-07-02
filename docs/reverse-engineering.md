# Reverse Engineering in Meteor

Static analysis workflow for **local artifacts you are authorized to examine**
(firmware dumps, malware samples in an isolated lab, binaries you built, mobile
IPAs/APKs on your own device).

Meteor does **not** execute unknown binaries. The `reverse.*` tools are read-only
static helpers; dynamic analysis belongs in a dedicated sandbox (VM, Cuckoo,
Ghidra debugger with isolation).

---

## Tool reference

| Capability | MCP name | Purpose |
|------------|----------|---------|
| `reverse.identify` | `reverse__identify` | `file(1)`, size, SHA-256 sample, entropy |
| `reverse.strings` | `reverse__strings` | Printable strings + “interesting” filter |
| `reverse.scan` | `reverse__scan` | Binwalk signatures (**no extraction**) |
| `reverse.symbols` | `reverse__symbols` | `readelf -s` / `objdump -T` / `nm -D` |
| `reverse.analyze` | `reverse__analyze` | Combined report |

Related arsenal tools (same registry):

- `binwalk.scan` — can extract with `extract=true` (use only in lab)
- `exiftool.extract` — metadata for documents/images
- `searchsploit.search` — public exploit-db references (research)

---

## Recommended workflow

```
1. reverse.identify(path)     → type, entropy, packed hint
2. reverse.strings(path)      → URLs, keys, suspicious literals
3. reverse.scan(path)         → embedded filesystems / compression
4. reverse.symbols(path)      → imported APIs (libc, network, exec)
5. reverse.analyze(path)      → one-shot summary for KITT/MCP agents
```

### Entropy heuristic

Sample entropy **> ~7.2** often indicates packing, encryption, or compressed
payloads. Follow with `binwalk.scan` and manual extraction in an **air-gapped
VM**.

### Interesting strings

`reverse.strings` flags lines containing `http`, `password`, `api`, `key`,
`secret`, `cmd`, `exec`, `shell`. Treat as **indicators**, not proof — verify
in context.

---

## Architecture (layer design)

```
Local file (authorized)
       │
       ▼
ReverseEngineeringLayer  ← app/reverse/layer.py
       ├── identify  → file, hashes, entropy
       ├── strings   → strings(1) or regex fallback
       ├── scan      → binwalk (read-only)
       ├── symbols   → readelf/objdump/nm
       └── analyze   → aggregates all passes
```

Registered as `reverse` in `bootstrap_tools()` → `ToolExecutor.CAPABILITIES` →
`meteor-mcp` projection (`reverse__analyze`, etc.).

**MCP policy:** `reverse.*` is **not offensive** — local file reads only. Works
under `METEOR_MCP_READ_ONLY=1` if the file path is readable within
`METEOR_MCP_ALLOWED_ROOT` when set.

---

## Chain with exploit layer

After static RE on a firmware blob or suspicious binary:

1. `exploit.cve_map` — CVEs already in graph from grinder/nuclei
2. `searchsploit.search` — public PoC references (lab only)
3. `exploit.chain` — scoped scanner sequence for exposed services
4. `docs/firewalls-network-security-2027.md` — if artifact is router/firewall FW

---

## Ethics & legal

- Analyze only files you **own** or have **written permission** to test
- Malware RE: isolated VM, no network, snapshot before opening samples
- Do not use RE output to build/distribute malware or bypass licensing unlawfully
- Meteor surfaces **structure and intel**; operators choose authorized next steps

---

## Dependencies

| Binary | Package (Arch example) |
|--------|-------------------------|
| `file` | `file` |
| `strings` | `binutils` |
| `binwalk` | `binwalk` (AUR/community) |
| `readelf` / `objdump` / `nm` | `binutils` |

Install missing tools; Meteor degrades gracefully (`builtin_regex` for strings,
error message if binwalk absent).

---

## Example (MCP / KITT)

```json
{"tool": "reverse", "operation": "analyze", "params": {"path": "/lab/sample.bin"}}
```

Agent reads `identify.entropy_sample`, `strings.interesting`, `scan.signatures`,
then may call `searchsploit.search` with a product string — **research only**.

See also: `app/reverse/layer.py`, `skills/kitt/SKILL.md`, `docs/mcp-arsenal.md`.
