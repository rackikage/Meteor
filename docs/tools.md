# Meteor Tools

Every capability the Meteor MCP kit projects, grouped by tool. Any MCP-capable agent (Claude Code, Cursor, OpenCode) mounts `meteor-mcp` and drives these directly — no bias toward any one tool. Calls are dispatched through [`app/runtime/tool_executor.py`](../app/runtime/tool_executor.py) and registered in [`app/tools/bootstrap.py`](../app/tools/bootstrap.py).

**97 capabilities across 36 tools.** Generated from `ToolExecutor.CAPABILITIES` — the single source of truth every consumer (MCP server, optional REPL, in-process runtime) projects.

Regenerate: `./scripts/generate-tools-doc.py`

## arsenal

| operation | params | description |
|-----------|--------|-------------|
| `arsenal.detect` | *`phase`?* | List installed pentest tools grouped by pipeline phase |
| `arsenal.run` | `tool`, *`args`?*, *`timeout`?* | Run any installed tool with a raw arg string (structured output) |

## binwalk

| operation | params | description |
|-----------|--------|-------------|
| `binwalk.scan` | `path`, *`extract`?* | firmware/file signature analysis |

## browser

| operation | params | description |
|-----------|--------|-------------|
| `browser.click` | `selector` | Click an element |
| `browser.fill` | `selector`, `value` | Fill a form field |
| `browser.js` | `script` | Run JS in browser |
| `browser.read` | — | Read current browser page text |

## clipboard

| operation | params | description |
|-----------|--------|-------------|
| `clipboard.copy` | `text` | Copy to clipboard |
| `clipboard.paste` | — | Paste from clipboard |

## dnsrecon

| operation | params | description |
|-----------|--------|-------------|
| `dnsrecon.enum` | `domain` | DNS enumeration for a domain |

## enum4linux

| operation | params | description |
|-----------|--------|-------------|
| `enum4linux.scan` | `target` | SMB/Samba enumeration of a host |

## exiftool

| operation | params | description |
|-----------|--------|-------------|
| `exiftool.extract` | `path` | extract file metadata |

## exploit

| operation | params | description |
|-----------|--------|-------------|
| `exploit.chain` | `ip`, `port`, `service`, *`banner`?* | Suggest authorized scanner chain for a fingerprinted service |
| `exploit.cve_map` | *`enrich`?*, *`limit`?* | Map graph vulnerability rows; optional NVD enrichment |
| `exploit.gaps` | *`cidr`?*, *`gateway`?* | Firewall/perimeter gap analysis from graph + 2027 defensive context |
| `exploit.intel` | `ip`, `port`, `service`, *`banner`?* | CVE + Exploit-DB research with attack score and next-tool hints |
| `exploit.prioritize` | *`cidr`?*, *`limit`?* | Rank in-graph hosts by service risk and stored CVE severity |

## feroxbuster

| operation | params | description |
|-----------|--------|-------------|
| `feroxbuster.scan` | `url`, *`wordlist`?* | feroxbuster recursive content discovery |

## ffuf

| operation | params | description |
|-----------|--------|-------------|
| `ffuf.fuzz` | `url`, *`wordlist`?* | ffuf web fuzzer (URL needs FUZZ keyword) |

## filesystem

| operation | params | description |
|-----------|--------|-------------|
| `filesystem.append` | `path`, `content` | Append text to a file |
| `filesystem.copy` | `src`, `dst` | Copy a file |
| `filesystem.edit` | `path`, `old_string`, `new_string`, *`replace_all`?* | Surgical in-place edit: replace old_string with new_string (unique unless replace_all) |
| `filesystem.glob` | `pattern` | Find files by pattern |
| `filesystem.grep` | `pattern`, `path` | Search file contents |
| `filesystem.list` | `path` | List directory contents |
| `filesystem.md5` | `path` | MD5 hash of file |
| `filesystem.mkdir` | `path` | Create directory |
| `filesystem.move` | `src`, `dst` | Move a file |
| `filesystem.read` | `path` | Read a file |
| `filesystem.read_range` | `path`, `start_line`, `end_line` | Read a line range from a file |
| `filesystem.remove` | `path` | Delete a file |
| `filesystem.remove_tree` | `path` | Recursively delete a directory tree |
| `filesystem.sha256` | `path` | SHA256 hash of file |
| `filesystem.stat` | `path` | Get file metadata |
| `filesystem.walk` | `path` | Recursively walk a directory tree |
| `filesystem.which` | `executable` | Find executable on PATH |
| `filesystem.write` | `path`, `content` | Write/overwrite a whole file |

## gobuster

| operation | params | description |
|-----------|--------|-------------|
| `gobuster.dir` | `url`, *`extensions`?*, *`wordlist`?* | gobuster directory/file brute-force |
| `gobuster.dns` | `domain`, *`wordlist`?* | gobuster DNS subdomain brute-force |

## graph

| operation | params | description |
|-----------|--------|-------------|
| `graph.counts` | — | Row counts per asset graph table |
| `graph.query` | `sql` | Run a read-only SELECT/WITH query over the asset graph |
| `graph.schema` | — | Asset graph schema reference (tables + columns) |
| `graph.tables` | — | List asset graph tables |

## grinder

| operation | params | description |
|-----------|--------|-------------|
| `grinder.grind_host` | `target` | Autonomous deep scan of one host into the asset graph |
| `grinder.grind_sector` | *`cidr`?* | Scan every in-scope host known to the asset graph |
| `grinder.grind_subnet` | `cidr`, *`scan`?* | Autonomous scan of a whole subnet into the graph (scan=common|subset|sweep) |

## hydra

| operation | params | description |
|-----------|--------|-------------|
| `hydra.bruteforce` | `target`, `service`, *`passlist`?*, *`userlist`?*, *`username`?* | hydra network login brute-force |

## infiltration

| operation | params | description |
|-----------|--------|-------------|
| `infiltration.footprint` | *`engagement_cidr`?* | Passive engagement footprint: local scope, graph stats, arsenal inventory |
| `infiltration.intercept` | *`max_events`?* | Capture grinder discovery events from the asset bus (pipeline intel, not wiretap) |
| `infiltration.peek` | *`limit`?* | Latest hosts/services from the asset graph |
| `infiltration.status` | *`engagement_cidr`?* | Full pipeline snapshot: footprint + intercept + graph peek |

## interpreter

| operation | params | description |
|-----------|--------|-------------|
| `interpreter.bash` | `code` | Run a bash snippet locally via shell (blocked: reverse/bind patterns) |
| `interpreter.reset` | — | Clear persistent Python session state |
| `interpreter.run` | `code` | Execute Python in a persistent local session (Open Interpreter style) |
| `interpreter.status` | — | Interpreter session keys and history length |

## keychain

| operation | params | description |
|-----------|--------|-------------|
| `keychain.delete` | `service`, `account` | Delete credential |
| `keychain.list` | — | List stored services |
| `keychain.retrieve` | `service`, `account` | Get credential |
| `keychain.store` | `service`, `account`, `secret` | Store credential |

## loopfreak

| operation | params | description |
|-----------|--------|-------------|
| `loopfreak.cycle` | *`engagement_cidr`?*, *`max_rounds`?*, *`stop_on_plateau`?* | Multi-round recon loop until graph host count plateaus |
| `loopfreak.pulse` | *`engagement_cidr`?* | One Loop Freak round: footprint → intercept → prioritize |
| `loopfreak.status` | — | Loop Freak state and default tool chain |

## masscan

| operation | params | description |
|-----------|--------|-------------|
| `masscan.scan` | `target`, *`ports`?*, *`rate`?* | masscan high-rate port scan |

## network

| operation | params | description |
|-----------|--------|-------------|
| `network.scope` | — | Discover local gateway, CIDR, and priority targets |

## nikto

| operation | params | description |
|-----------|--------|-------------|
| `nikto.scan` | `target` | nikto web server vulnerability scan |

## nmap

| operation | params | description |
|-----------|--------|-------------|
| `nmap.discover` | `cidr` | Nmap host discovery on a CIDR |
| `nmap.scan` | `target`, *`ports`?* | Nmap TCP scan (default top 1000 ports) |
| `nmap.script` | `target`, `script`, *`ports`?* | Nmap NSE script run (e.g. vuln, default) |
| `nmap.service_version` | `target`, *`ports`?* | Nmap -sV service/version detection |

## notify

| operation | params | description |
|-----------|--------|-------------|
| `notify.send` | `title`, `message` | Send notification |

## nuclei

| operation | params | description |
|-----------|--------|-------------|
| `nuclei.scan` | `target`, *`severity`?*, *`templates`?* | nuclei template-based vulnerability scan |

## pentest

| operation | params | description |
|-----------|--------|-------------|
| `pentest.firewall_analyze` | — | Graph-based perimeter exposure |
| `pentest.kernel_posture` | — | Local kernel/sysctl firewall posture |
| `pentest.posture` | — | Combined kernel + graph firewall posture |
| `pentest.probe` | `target` | Async TCP probe engine |

## process

| operation | params | description |
|-----------|--------|-------------|
| `process.kill` | `pid` | Terminate a process |
| `process.list` | — | List running processes |
| `process.stats` | — | Get system resource stats |

## reverse

| operation | params | description |
|-----------|--------|-------------|
| `reverse.analyze` | `path`, *`include_strings`?* | Full static RE report: identify + strings + scan + symbols |
| `reverse.identify` | `path` | File type, hashes, entropy — static metadata for a local binary |
| `reverse.scan` | `path` | Binwalk signature scan (no extraction) |
| `reverse.strings` | `path`, *`min_len`?* | Extract printable strings from a local file |
| `reverse.symbols` | `path` | Dynamic symbol table via readelf/objdump/nm |

## scheduler

| operation | params | description |
|-----------|--------|-------------|
| `scheduler.add` | `name`, `command`, `schedule` | Schedule a task |
| `scheduler.list` | — | List scheduled tasks |
| `scheduler.remove` | `name` | Remove schedule task |

## searchsploit

| operation | params | description |
|-----------|--------|-------------|
| `searchsploit.search` | `term` | search Exploit-DB for a term |

## shell

| operation | params | description |
|-----------|--------|-------------|
| `shell.run` | `command` | Run a shell command |

## smbmap

| operation | params | description |
|-----------|--------|-------------|
| `smbmap.scan` | `target`, *`password`?*, *`username`?* | enumerate SMB shares on a host |

## sqlmap

| operation | params | description |
|-----------|--------|-------------|
| `sqlmap.scan` | `url`, *`data`?*, *`extra`?*, *`level`?*, *`risk`?* | sqlmap automated SQL injection against a URL |

## web

| operation | params | description |
|-----------|--------|-------------|
| `web.cves` | `service` | Look up CVEs for a service/banner (NVD) |
| `web.exploit_surface` | `ip`, `port`, `service`, *`banner`?* | CVE + Exploit-DB intel with attack score and recommended next tools (research only, no payloads) |
| `web.exploits` | `service` | Search Exploit-DB for a service/banner |
| `web.research` | `ip`, `port`, `service` | Full service intel: CVEs + exploits + web hits |
| `web.search` | `query` | General web search (DuckDuckGo) |

## whatweb

| operation | params | description |
|-----------|--------|-------------|
| `whatweb.fingerprint` | `target`, *`aggression`?* | whatweb tech-stack fingerprint |

## wpscan

| operation | params | description |
|-----------|--------|-------------|
| `wpscan.scan` | `url`, *`extra`?* | WordPress security scan |

> Params shown *`like this?`* are optional (typed schema surfaced to MCP clients). See [`mcp-arsenal.md`](mcp-arsenal.md) for how MCP works, offensive-tool gating, and env-based scoping.
