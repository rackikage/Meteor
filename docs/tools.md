# Meteor Tools

Every capability Meteor can invoke, grouped by tool. Meteor selects these on its own — no bias toward any one tool — and folds the results into a normal reply. Calls are dispatched through [`app/runtime/tool_executor.py`](../app/runtime/tool_executor.py) and registered permissively in [`app/tools/bootstrap.py`](../app/tools/bootstrap.py).

**75 capabilities across 31 tools.** This file is generated from `ToolExecutor.CAPABILITIES` — the single source of truth the desktop app and the MCP server both project.

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

## shell

| operation | params | description |
|-----------|--------|-------------|
| `shell.run` | `command` | Run a shell command |

## process

| operation | params | description |
|-----------|--------|-------------|
| `process.kill` | `pid` | Terminate a process |
| `process.list` | — | List running processes |
| `process.stats` | — | Get system resource stats |

## clipboard

| operation | params | description |
|-----------|--------|-------------|
| `clipboard.copy` | `text` | Copy to clipboard |
| `clipboard.paste` | — | Paste from clipboard |

## notify

| operation | params | description |
|-----------|--------|-------------|
| `notify.send` | `title`, `message` | Send notification |

## keychain

| operation | params | description |
|-----------|--------|-------------|
| `keychain.delete` | `service`, `account` | Delete credential |
| `keychain.list` | — | List stored services |
| `keychain.retrieve` | `service`, `account` | Get credential |
| `keychain.store` | `service`, `account`, `secret` | Store credential |

## scheduler

| operation | params | description |
|-----------|--------|-------------|
| `scheduler.add` | `name`, `command`, `schedule` | Schedule a task |
| `scheduler.list` | — | List scheduled tasks |
| `scheduler.remove` | `name` | Remove schedule task |

## browser

| operation | params | description |
|-----------|--------|-------------|
| `browser.click` | `selector` | Click an element |
| `browser.fill` | `selector`, `value` | Fill a form field |
| `browser.js` | `script` | Run JS in browser |
| `browser.read` | — | Read current browser page text |

## nmap

| operation | params | description |
|-----------|--------|-------------|
| `nmap.discover` | `cidr` | Nmap host discovery on a CIDR |
| `nmap.scan` | `target`, *`ports`?* | Nmap TCP scan (default top 1000 ports) |
| `nmap.script` | `target`, `script`, *`ports`?* | Nmap NSE script run (e.g. vuln, default) |
| `nmap.service_version` | `target`, *`ports`?* | Nmap -sV service/version detection |

## pentest

| operation | params | description |
|-----------|--------|-------------|
| `pentest.firewall_analyze` | — | Graph-based perimeter exposure |
| `pentest.kernel_posture` | — | Local kernel/sysctl firewall posture |
| `pentest.posture` | — | Combined kernel + graph firewall posture |
| `pentest.probe` | `target` | Async TCP probe engine |

## network

| operation | params | description |
|-----------|--------|-------------|
| `network.scope` | — | Discover local gateway, CIDR, and priority targets |

## grinder

| operation | params | description |
|-----------|--------|-------------|
| `grinder.grind_host` | `target` | Autonomous deep scan of one host into the asset graph |
| `grinder.grind_sector` | *`cidr`?* | Scan every in-scope host known to the asset graph |
| `grinder.grind_subnet` | `cidr`, *`scan`?* | Autonomous scan of a whole subnet into the graph (scan=common|subset|sweep) |

## graph

| operation | params | description |
|-----------|--------|-------------|
| `graph.counts` | — | Row counts per asset graph table |
| `graph.query` | `sql` | Run a read-only SELECT/WITH query over the asset graph |
| `graph.schema` | — | Asset graph schema reference (tables + columns) |
| `graph.tables` | — | List asset graph tables |

## web

| operation | params | description |
|-----------|--------|-------------|
| `web.cves` | `service` | Look up CVEs for a service/banner (NVD) |
| `web.exploits` | `service` | Search Exploit-DB for a service/banner |
| `web.research` | `ip`, `port`, `service` | Full service intel: CVEs + exploits + web hits |
| `web.search` | `query` | General web search (DuckDuckGo) |

## arsenal

| operation | params | description |
|-----------|--------|-------------|
| `arsenal.detect` | *`phase`?* | List installed pentest tools grouped by pipeline phase |
| `arsenal.run` | `tool`, *`args`?*, *`timeout`?* | Run any installed tool with a raw arg string (structured output) |

## sqlmap

| operation | params | description |
|-----------|--------|-------------|
| `sqlmap.scan` | `url`, *`data`?*, *`level`?*, *`risk`?*, *`extra`?* | sqlmap automated SQL injection against a URL |

## nuclei

| operation | params | description |
|-----------|--------|-------------|
| `nuclei.scan` | `target`, *`templates`?*, *`severity`?* | nuclei template-based vulnerability scan |

## nikto

| operation | params | description |
|-----------|--------|-------------|
| `nikto.scan` | `target` | nikto web server vulnerability scan |

## whatweb

| operation | params | description |
|-----------|--------|-------------|
| `whatweb.fingerprint` | `target`, *`aggression`?* | whatweb tech-stack fingerprint |

## wpscan

| operation | params | description |
|-----------|--------|-------------|
| `wpscan.scan` | `url`, *`extra`?* | WordPress security scan |

## gobuster

| operation | params | description |
|-----------|--------|-------------|
| `gobuster.dir` | `url`, *`wordlist`?*, *`extensions`?* | gobuster directory/file brute-force |
| `gobuster.dns` | `domain`, *`wordlist`?* | gobuster DNS subdomain brute-force |

## ffuf

| operation | params | description |
|-----------|--------|-------------|
| `ffuf.fuzz` | `url`, *`wordlist`?* | ffuf web fuzzer (URL needs FUZZ keyword) |

## feroxbuster

| operation | params | description |
|-----------|--------|-------------|
| `feroxbuster.scan` | `url`, *`wordlist`?* | feroxbuster recursive content discovery |

## hydra

| operation | params | description |
|-----------|--------|-------------|
| `hydra.bruteforce` | `target`, `service`, *`username`?*, *`userlist`?*, *`passlist`?* | hydra network login brute-force |

## searchsploit

| operation | params | description |
|-----------|--------|-------------|
| `searchsploit.search` | `term` | search Exploit-DB for a term |

## dnsrecon

| operation | params | description |
|-----------|--------|-------------|
| `dnsrecon.enum` | `domain` | DNS enumeration for a domain |

## enum4linux

| operation | params | description |
|-----------|--------|-------------|
| `enum4linux.scan` | `target` | SMB/Samba enumeration of a host |

## smbmap

| operation | params | description |
|-----------|--------|-------------|
| `smbmap.scan` | `target`, *`username`?*, *`password`?* | enumerate SMB shares on a host |

## masscan

| operation | params | description |
|-----------|--------|-------------|
| `masscan.scan` | `target`, *`ports`?*, *`rate`?* | masscan high-rate port scan |

## exiftool

| operation | params | description |
|-----------|--------|-------------|
| `exiftool.extract` | `path` | extract file metadata |

## binwalk

| operation | params | description |
|-----------|--------|-------------|
| `binwalk.scan` | `path`, *`extract`?* | firmware/file signature analysis |

> Params shown *`like this?`* are optional (typed schema surfaced to MCP clients). See [`mcp-arsenal.md`](mcp-arsenal.md) for the MCP server, offensive-tool gating, and env-based scoping.
