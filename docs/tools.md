# Meteor Tools

Every capability Meteor can invoke, grouped by tool. Meteor selects these on its
own — no bias toward any one tool — and folds the results into a normal reply.
Calls are dispatched through
[`app/runtime/tool_executor.py`](../app/runtime/tool_executor.py) and registered
permissively in [`app/tools/bootstrap.py`](../app/tools/bootstrap.py).

**44 capabilities across 12 tools.**

## shell

| operation | params | description |
|-----------|--------|-------------|
| `shell.run` | `command` | Run a shell command |

## filesystem

| operation | params | description |
|-----------|--------|-------------|
| `filesystem.copy` | `src`, `dst` | Copy a file |
| `filesystem.glob` | `pattern` | Find files by pattern |
| `filesystem.grep` | `pattern`, `path` | Search file contents |
| `filesystem.list` | `path` | List directory contents |
| `filesystem.md5` | `path` | MD5 hash of file |
| `filesystem.mkdir` | `path` | Create directory |
| `filesystem.move` | `src`, `dst` | Move a file |
| `filesystem.read` | `path` | Read a file |
| `filesystem.remove` | `path` | Delete a file |
| `filesystem.sha256` | `path` | SHA256 hash of file |
| `filesystem.stat` | `path` | Get file metadata |
| `filesystem.which` | `executable` | Find executable on PATH |
| `filesystem.write` | `path`, `content` | Write to a file |

## process

| operation | params | description |
|-----------|--------|-------------|
| `process.kill` | `pid` | Terminate a process |
| `process.list` | — | List running processes |
| `process.stats` | — | Get system resource stats |

## network

| operation | params | description |
|-----------|--------|-------------|
| `network.scope` | — | Discover local gateway, CIDR, and priority targets |

## nmap

| operation | params | description |
|-----------|--------|-------------|
| `nmap.discover` | `cidr` | Nmap host discovery on a CIDR |
| `nmap.scan` | `target` | Nmap TCP scan (default top 1000 ports) |
| `nmap.script` | `target`, `script` | Nmap NSE script run (e.g. vuln, default) |
| `nmap.service_version` | `target` | Nmap -sV service/version detection |

## pentest

| operation | params | description |
|-----------|--------|-------------|
| `pentest.firewall_analyze` | — | Graph-based perimeter exposure |
| `pentest.kernel_posture` | — | Local kernel/sysctl firewall posture |
| `pentest.posture` | — | Combined kernel + graph firewall posture |
| `pentest.probe` | `target` | Async TCP probe engine |

## web

| operation | params | description |
|-----------|--------|-------------|
| `web.cves` | `service` | Look up CVEs for a service/banner (NVD) |
| `web.exploits` | `service` | Search Exploit-DB for a service/banner |
| `web.research` | `ip`, `port`, `service` | Full service intel: CVEs + exploits + web hits |
| `web.search` | `query` | General web search (DuckDuckGo) |

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

