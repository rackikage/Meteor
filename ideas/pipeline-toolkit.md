# Agent Layer Pipeline Toolkit

```
PHASE 0: AI RUNTIMES ─┬─ Agent Frameworks ─── SDKs ─── LLM Providers
                       ├─────────────────────────────────────────┘
                       ▼
PHASE 1: RECON ───────┬─ OSINT ─── Asset Discovery ─── Network Scan ─── Web Crawl
                       ▼
PHASE 2: INGEST ──────┬─ File Read ─── Web Fetch ─── Packet Capture ─── Crawl
                       ▼
PHASE 3: ANALYZE ─────┬─ Code Analysis ─── Binary RE ─── Data Proc ─── Crypto
                       ▼
PHASE 4: EXPLOIT ─────┬─ Web Attack ─── Browser Auto ─── Auth Crack ─── Fuzz
                       ▼
PHASE 5: PIVOT ───────┬─ PrivEsc ─── Lateral ─── Cred Dump ─── PTH
                       ▼
PHASE 6: C2/TUNNEL ───┬─ C2 Frameworks ─── Proxies ─── Tunnels ─── Exfil
                       ▼
PHASE 7: MEMORY ──────┬─ Vector DBs ─── Knowledge ─── SQL ─── Cache
                       ▼
PHASE 8: COMMS ───────┬─ SMS ─── Messaging ─── Webhooks ─── Email
                       ▼
PHASE 9: EVASION ─────┬─ Proxies ─── Encryption ─── Stego ─── Log Wipe
                       ▼
PHASE 10: FORENSIC ───┬─ Memory ─── Disk ─── Network ─── Timeline
```

> Agent-ready CLI tools organized by pipeline phase | 500+ entries
> No paid API keys required (free tiers noted where applicable)

---

## PHASE 0: AGENT RUNTIMES & AI INFRASTRUCTURE

The base layer — AI agent frameworks, SDKs, and LLM providers that power autonomous agents.

### 0.1 — AI Agent Frameworks & CLI Runtimes

| # | Tool | Description | Link |
|---|------|-------------|------|
| 1 | Armature / Forge CLI | OSS agent SDK — 50 tools, multi-provider, MCP-native, MIT | https://github.com/MARUCIE/armature-agent-sdk |
| 2 | OpenCode | CLI agent (this project), local-first, keyless models | https://github.com/anomalyco/opencode |
| 3 | Codex CLI | OpenAI's terminal agent runtime | https://github.com/openai/codex |
| 4 | OpenHands | OSS coding agent (fka OpenDevin) | https://github.com/All-Hands-AI/OpenHands |
| 5 | Meka | Rust agent harness — REPL, ACP, HTTP API, MCP | https://github.com/k4yt3x/meka |
| 6 | GitAgent | Git-native agent — identity/rules/memory in-repo | https://github.com/open-gitagent/gitagent |
| 7 | Nomi | State-driven agent — plan-review, capability-gated | https://github.com/klarlabs-studio/nomi |
| 8 | Nanobot | Ultra-lightweight agent — WebUI, MCP, chat channels | https://github.com/chengchaos/nanobot |
| 9 | GenericAgent | ~3K-line self-evolving agent — browser/terminal/ADB | https://github.com/sirbrasscat/GenericAgent |
| 10 | Synapse | OSS agent — sandboxed execution, 20+ tools, eval | https://github.com/droxer/HiAgent |
| 11 | Powergentic CLI | Copilot-like CLI — *.agent.md, AGENTS.md | https://github.com/powergentic/cli |
| 12 | Cline | VS Code + CLI agent with MCP | https://github.com/cline/cline |
| 13 | Goose | OSS agent by Block | https://github.com/block/goose |
| 14 | Pi | Terminal agent for developers | https://github.com/pi-ai/pi |
| 15 | Aider | AI pair programming in terminal | https://github.com/paul-gauthier/aider |
| 16 | Continue | Open-source AI code assistant | https://github.com/continuedev/continue |
| 17 | Claude Code | Anthropic's terminal agent | https://docs.anthropic.com |
| 18 | Claude Operator | Anthropic's computer-use agent | https://docs.anthropic.com |
| 19 | OpenAI Operator | OpenAI's computer-use agent | https://openai.com |
| 20 | AutoGPT | Autonomous GPT-4 agent | https://github.com/Significant-Gravitas/AutoGPT |
| 21 | Superagent | OSS agent framework for production | https://github.com/homanp/superagent |
| 22 | TaskWeaver | Microsoft's code-first agent framework | https://github.com/microsoft/TaskWeaver |
| 23 | AgentGPT | Browser-based autonomous agent | https://github.com/reworkd/AgentGPT |
| 24 | Camel | Multi-agent communication framework | https://github.com/camel-ai/camel |

### 0.2 — Agent SDKs & Orchestration

| # | Tool | Description | Link |
|---|------|-------------|------|
| 25 | LangChain | Most popular LLM framework | https://github.com/langchain-ai/langchain |
| 26 | LangGraph | Stateful multi-agent orchestration | https://github.com/langchain-ai/langgraph |
| 27 | LangServe | LangChain API deployment | https://github.com/langchain-ai/langserve |
| 28 | CrewAI | Multi-agent collaboration | https://github.com/crewAIInc/crewAI |
| 29 | AutoGen | Microsoft's multi-agent platform | https://github.com/microsoft/autogen |
| 30 | Semantic Kernel | Microsoft's enterprise AI SDK | https://github.com/microsoft/semantic-kernel |
| 31 | Dify | LLM app dev platform | https://github.com/langgenius/dify |
| 32 | Flowise | Low-code LLM app builder | https://github.com/FlowiseAI/Flowise |
| 33 | RAGFlow | OSS RAG engine | https://github.com/infiniflow/ragflow |
| 34 | MCP Servers | Model Context Protocol — 100+ servers | https://github.com/modelcontextprotocol |
| 35 | Smolagents | HuggingFace's minimal agent framework | https://github.com/huggingface/smolagents |
| 36 | pydantic-ai | Pydantic's agent framework | https://github.com/pydantic/pydantic-ai |
| 37 | atomic-agents | Minimal atomic agent framework | https://github.com/atomic-agents/atomic-agents |
| 38 | BAML | Type-safe LLM calling | https://github.com/boundaryml/baml |
| 39 | Vercel AI SDK | TypeScript toolkit for AI agents | https://github.com/vercel/ai |
| 40 | Mastra | TypeScript agent framework | https://github.com/mastra-ai/mastra |
| 41 | Agno | Python agent framework (fka phidata) | https://github.com/agno-agi/agno |
| 42 | Letta | Stateful agents with memory | https://github.com/letta-ai/letta |
| 43 | Mem0 | Memory layer for AI agents | https://github.com/mem0ai/mem0 |
| 44 | ZerePy | Python agent framework on ZeroMQ | https://github.com/zerepy/zerepy |

### 0.3 — LLM Providers & Inference (Agent-Ready)

| # | Tool | Description | Link |
|---|------|-------------|------|
| 45 | Ollama | Local LLM runtime | https://ollama.ai |
| 46 | vLLM | High-throughput LLM serving | https://github.com/vllm-project/vllm |
| 47 | llama.cpp | C++ LLM inference (CPU/GPU) | https://github.com/ggerganov/llama.cpp |
| 48 | LocalAI | Self-hosted OpenAI-compat API | https://localai.io |
| 49 | Open WebUI | ChatGPT-style UI for local LLMs | https://openwebui.com |
| 50 | LiteLLM | Proxy for 100+ providers | https://github.com/BerriAI/litellm |
| 51 | Groq | Ultra-fast inference (keyless free models) | https://groq.com |
| 52 | Cerebras | Fastest inference hardware | https://cerebras.ai |
| 53 | Cloudflare Workers AI | Serverless AI inference | https://workers.ai |
| 54 | HuggingFace Inference API | Free model hosting | https://huggingface.co/inference-api |
| 55 | Together AI | Hosted OSS models | https://togetherai.ai |
| 56 | Fireworks AI | Fast OSS model serving | https://fireworks.ai |
| 57 | Anyscale | Distributed serving (Ray) | https://anyscale.com |
| 58 | Modal | Serverless GPU compute | https://modal.com |
| 59 | Replicate | Cloud API for OSS models | https://replicate.com |
| 60 | OpenRouter | Unified API for 200+ models | https://openrouter.ai |
| 61 | DeepSeek | Strong reasoning models (free tier) | https://deepseek.com |
| 62 | Pollinations | Free keyless model API | https://pollinations.ai |
| 63 | Tabby | Self-hosted code assistant | https://tabby.tabbyml.com |
| 64 | Continue + Ollama | Full local coding stack | https://continue.dev |

---

## PHASE 1: RECONNAISSANCE

Discovering targets, surfaces, assets, and identities. First phase of any pipeline.

### 1.1 — OSINT & Identity Discovery

| # | Tool | Description | Link |
|---|------|-------------|------|
| 65 | theHarvester | Email/subdomain/name OSINT | https://github.com/laramies/theHarvester |
| 66 | Recon-ng | Web reconnaissance framework | https://github.com/lanmaster53/recon-ng |
| 67 | Maltego | Link analysis & graphing | https://maltego.com |
| 68 | SpiderFoot | OSINT automation | https://github.com/smicallef/spiderfoot |
| 69 | Sherlock | Username search across networks | https://github.com/sherlock-project/sherlock |
| 70 | Holehe | Email-to-account correlation | https://github.com/megadose/holehe |
| 71 | PhoneInfoga | Phone number OSINT | https://github.com/sundowndev/phoneinfoga |
| 72 | Hunter.io | Email domain OSINT | https://hunter.io |
| 73 | Skymem | Email address lookup | https://skymem.info |
| 74 | IntelX | Dark web & data leak search | https://intelx.io |
| 75 | Dehashed | Password leak search engine | https://dehashed.com |
| 76 | BreachDirectory | Breach data lookup | https://breachdirectory.org |
| 77 | LeakCheck | Credential leak search | https://leakcheck.io |
| 78 | SocialScan | Social media OSINT | https://github.com/iojw/socialscan |
| 79 | Twint | Twitter OSINT (no API needed) | https://github.com/twintproject/twint |
| 80 | Instaloader | Instagram OSINT/downloader | https://github.com/instaloader/instaloader |
| 81 | Cree.py | Geolocation OSINT | https://github.com/ilektrojohn/creepy |
| 82 | Datasploit | Automated OSINT | https://github.com/DataSploit/datasploit |
| 83 | Mr.Holmes | OSINT suite | https://github.com/Lucksi/Mr.Holmes |
| 84 | Little Brother | OSINT toolkit | https://github.com/lulz3xploit/LittleBrother |
| 85 | OSRFramework | Open-source recon framework | https://github.com/i3visio/osrframework |

### 1.2 — Domain & Subdomain Discovery

| # | Tool | Description | Link |
|---|------|-------------|------|
| 86 | Amass | Subdomain enumeration (OWASP) | https://github.com/owasp-amass/amass |
| 87 | Sublist3r | Fast subdomain enumeration | https://github.com/aboul3la/Sublist3r |
| 88 | Assetfinder | Domain/asset discovery | https://github.com/tomnomnom/assetfinder |
| 89 | Findomain | Subdomain discovery | https://github.com/Findomain/Findomain |
| 90 | Subfinder | Subdomain discovery (ProjectDiscovery) | https://github.com/projectdiscovery/subfinder |
| 91 | Dnsx | Multi-purpose DNS toolkit | https://github.com/projectdiscovery/dnsx |
| 92 | Dnsrecon | DNS enumeration | https://github.com/darkoperator/dnsrecon |
| 93 | Dnsdumpster | DNS recon (web + CLI) | https://dnsdumpster.com |
| 94 | MassDNS | High-performance DNS resolver | https://github.com/blechschmidt/massdns |
| 95 | ShuffleDNS | Wrapper around MassDNS | https://github.com/projectdiscovery/shuffledns |
| 96 | Puredns | DNS resolver for wildcard busting | https://github.com/d3mondev/puredns |
| 97 | Alterx | Subdomain permutation generator | https://github.com/projectdiscovery/alterx |
| 98 | CRT.sh | Certificate transparency log search | https://crt.sh |

### 1.3 — Global Asset & Internet Scanning

| # | Tool | Description | Link |
|---|------|-------------|------|
| 99 | Shodan | Internet-connected device search | https://shodan.io |
| 100 | Censys | Internet asset discovery | https://censys.io |
| 101 | FOFA | Cyberspace mapping engine | https://fofa.info |
| 102 | ZoomEye | Cyberspace search engine | https://zoomeye.org |
| 103 | Greynoise | Internet noise & threat intel | https://greynoise.io |
| 104 | Shodan CLI | Command-line Shodan | https://cli.shodan.io |
| 105 | Nmap | Network discovery & scanning | https://nmap.org |
| 106 | Masscan | Mass IP port scanner | https://github.com/robertdavidgraham/masscan |
| 107 | Zmap | Internet-wide scanner | https://zmap.io |
| 108 | RustScan | Blazing-fast port scanner | https://github.com/RustScan/RustScan |
| 109 | Naabu | Port scanner (ProjectDiscovery) | https://github.com/projectdiscovery/naabu |
| 110 | Angry IP Scanner | Fast IP/port scanner | https://angryip.org |
| 111 | Unicornscan | High-performance async scanner | https://github.com/dankrause/unicornscan |

### 1.4 — Network Probing & Fingerprinting

| # | Tool | Description | Link |
|---|------|-------------|------|
| 112 | WhatWeb | Website fingerprinting | https://github.com/urbanadventurer/WhatWeb |
| 113 | Wappalyzer | Tech stack detection | https://wappalyzer.com |
| 114 | httpx | HTTP probing toolkit | https://github.com/projectdiscovery/httpx |
| 115 | Httprobe | Live host probing | https://github.com/tomnomnom/httprobe |
| 116 | GAU | Get All URLs (Wayback+OTX+CommonCrawl) | https://github.com/lc/gau |
| 117 | Waybackurls | URL discovery from Wayback Machine | https://github.com/tomnomnom/waybackurls |
| 118 | Katana | Next-gen web crawler | https://github.com/projectdiscovery/katana |
| 119 | Photon | OSINT web crawler | https://github.com/s0md3v/Photon |
| 120 | FavFreak | Favicon hash lookup | https://github.com/devanshbatham/FavFreak |
| 121 | Unfurl | URL extraction/analysis | https://github.com/tomnomnom/unfurl |
| 122 | Gf | Pattern matching for grep | https://github.com/tomnomnom/gf |
| 123 | Anew | Line deduplication | https://github.com/tomnomnom/anew |
| 124 | ParamSpider | URL parameter discovery | https://github.com/devanshbatham/ParamSpider |

### 1.5 — Social Engineering Recon

| # | Tool | Description | Link |
|---|------|-------------|------|
| 125 | SET | Social Engineer Toolkit | https://github.com/trustedsec/social-engineer-toolkit |
| 126 | Gophish | OSS phishing framework | https://getgophish.com |
| 127 | EvilGinx2 | Nginx reverse proxy for creds | https://github.com/kgretzky/evilginx2 |
| 128 | Modlishka | Reverse proxy phishing | https://github.com/drk1wi/Modlishka |
| 129 | King Phisher | Phishing campaign toolkit | https://github.com/rsmusllp/king-phisher |
| 130 | CUPP | Common User Password Profiler | https://github.com/Mebus/cupp |
| 131 | CeWL | Custom wordlist from website | https://github.com/digininja/CeWL |
| 132 | Rsmangler | Wordlist permutation | https://github.com/digininja/rsmangler |

---

## PHASE 2: INGESTION & CRAWLING

Collecting data — pulling content from networks, files, web, and packets into analyzable form.

### 2.1 — Web Fetching & HTTP

| # | Tool | Description | Link |
|---|------|-------------|------|
| 133 | Curl | HTTP/S transfer (everything) | https://curl.se |
| 134 | Wget | HTTP/S recursive download | https://gnu.org/software/wget |
| 135 | HTTPie | Human-friendly HTTP client | https://httpie.io |
| 136 | Python Requests | HTTP library for agents | https://docs.python-requests.org |
| 137 | httpx (Python) | Modern async HTTP client | https://www.python-httpx.org |
| 138 | aria2 | Multi-protocol download utility | https://aria2.github.io |
| 139 | axel | Lightweight download accelerator | https://github.com/axel-download-accelerator/axel |
| 140 | Firecrawl | Web scraping for LLMs | https://firecrawl.dev |
| 141 | Jina Reader | LLM-friendly web content extraction | https://jina.ai/reader |
| 142 | ScrapeGraphAI | AI-powered web scraping | https://github.com/ScrapeGraphAI/Scrapegraph-ai |
| 143 | Crawl4AI | OSS LLM-friendly web crawler | https://github.com/unclecode/crawl4ai |

### 2.2 — Packet Capture & Network Ingestion

| # | Tool | Description | Link |
|---|------|-------------|------|
| 144 | Tcpdump | CLI packet capture | https://tcpdump.org |
| 145 | Tshark | CLI Wireshark | https://wireshark.org/docs/man-pages/tshark.html |
| 146 | Wireshark | GUI packet analyzer | https://wireshark.org |
| 147 | Scapy | Python packet manipulation | https://scapy.net |
| 148 | Netcat (nc) | TCP/UDP Swiss army knife | https://nc110.sourceforge.io |
| 149 | Ncat | Enhanced Netcat (Nmap) | https://nmap.org/ncat |
| 150 | Hping3 | Packet crafting & analysis | https://github.com/antirez/hping |
| 151 | MTR | Network diagnostics (traceroute+ping) | https://github.com/traviscross/mtr |
| 152 | Tcptraceroute | TCP-based traceroute | https://github.com/mct/tcptraceroute |
| 153 | Iperf3 | Network bandwidth testing | https://iperf.fr |

### 2.3 — File Parsing & Data Extraction

| # | Tool | Description | Link |
|---|------|-------------|------|
| 154 | Pandoc | Universal document converter | https://pandoc.org |
| 155 | Exiftool | Metadata extraction | https://exiftool.org |
| 156 | Strings | Extract strings from binaries | https://man7.org/linux/man-pages/man1/strings.1.html |
| 157 | Foremost | File carving | https://github.com/korczis/foremost |
| 158 | Binwalk | Firmware analysis & extraction | https://github.com/ReFirmLabs/binwalk |
| 159 | Photorec | File recovery | https://cgsecurity.org/wiki/PhotoRec |
| 160 | TestDisk | Partition recovery | https://cgsecurity.org/wiki/TestDisk |
| 161 | Ddrescue | Data recovery | https://gnu.org/software/ddrescue |
| 162 | BeautifulSoup | HTML parsing (Python) | https://crummy.com/software/BeautifulSoup |
| 163 | lxml | XML/HTML parser | https://lxml.de |
| 164 | pdfplumber | PDF data extraction | https://github.com/jsvine/pdfplumber |
| 165 | PyMuPDF | PDF manipulation | https://pymupdf.readthedocs.io |
| 166 | python-docx | Word document parsing | https://python-docx.readthedocs.io |
| 167 | openpyxl | Excel parsing | https://openpyxl.readthedocs.io |
| 168 | SQLite CLI | Embedded database CLI | https://sqlite.org/cli.html |

### 2.4 — Wireless & Signal Ingestion

| # | Tool | Description | Link |
|---|------|-------------|------|
| 169 | Aircrack-ng | WiFi capture & analysis | https://aircrack-ng.org |
| 170 | Kismet | Wireless network detector | https://kismetwireless.net |
| 171 | RTL-SDR | Cheap SDR (RX 24MHz-1.7GHz) | https://rtl-sdr.com |
| 172 | HackRF One | SDR TX/RX (1MHz-6GHz) | https://greatscottgadgets.com/hackrf |
| 173 | GNURadio | SDR signal processing framework | https://gnuradio.org |
| 174 | Universal Radio Hacker | Wireless protocol analysis | https://github.com/jopohl/urh |
| 175 | Flipper Zero | Multi-tool RFID/BLE/NFC | https://flipperzero.one |
| 176 | Proxmark3 | RFID/NFC cloning & analysis | https://proxmark.com |

---

## PHASE 3: ANALYSIS & INTELLIGENCE

Processing collected data — code analysis, binary reverse engineering, data transformation, crypto.

### 3.1 — Static Code Analysis (SAST)

| # | Tool | Description | Link |
|---|------|-------------|------|
| 177 | Semgrep | Multi-language SAST (rules + Pro) | https://semgrep.dev |
| 178 | CodeQL | GitHub's code analysis engine | https://codeql.github.com |
| 179 | SonarQube | Code quality & security | https://sonarsource.com |
| 180 | Snyk | Developer-first SCA+SAST | https://snyk.io |
| 181 | Socket | Supply chain security | https://socket.dev |
| 182 | Xint Code | LLM-native SAST, 2026 model | https://theori.com/xint |
| 183 | Sprocket Apex | AI penetration testing agent | https://sprocketsecurity.com/apex |
| 184 | Oxlint | Rust JS/TS linter (100x faster) | https://oxc.rs |
| 185 | Biome | Rust formatter+linter | https://biomejs.dev |
| 186 | Ruff | Rust Python linter | https://docs.astral.sh/ruff |
| 187 | basedpyright | Python type checker | https://docs.basedpyright.com |
| 188 | mypy | Python static type checker | https://mypy-lang.org |
| 189 | Bandit | Python security linter | https://github.com/PyCQA/bandit |
| 190 | ESLint | JS/TS linter | https://eslint.org |
| 191 | golangci-lint | Go linter suite | https://golangci-lint.run |
| 192 | Clippy | Rust linter | https://github.com/rust-lang/rust-clippy |

### 3.2 — Reverse Engineering & Binary Analysis

| # | Tool | Description | Link |
|---|------|-------------|------|
| 193 | Ghidra | NSA reverse engineering framework | https://ghidra-sre.org |
| 194 | Radare2 / Iaito | RE framework + Qt GUI | https://rada.re |
| 195 | IDA Free | Disassembler (free version) | https://hex-rays.com/ida-free |
| 196 | Binary Ninja | Binary analysis platform | https://binary.ninja |
| 197 | x64dbg | Windows debugger | https://x64dbg.com |
| 198 | GDB | GNU debugger | https://sourceware.org/gdb |
| 199 | LLDB | LLVM debugger | https://lldb.llvm.org |
| 200 | Objdump | Binary object analysis | binutils |
| 201 | Readelf | ELF file analysis | binutils |
| 202 | Strace | System call tracer | https://strace.io |
| 203 | Ltrace | Library call tracer | https://ltrace.org |
| 204 | Frida | Dynamic instrumentation | https://frida.re |
| 205 | Unicorn Engine | CPU emulator framework | https://unicorn-engine.org |
| 206 | QEMU | Full system emulator | https://qemu.org |
| 207 | dnSpy | .NET debugger & assembly editor | https://github.com/dnSpy/dnSpy |
| 208 | ILSpy | .NET decompiler | https://github.com/icsharpcode/ILSpy |
| 209 | Procmon | Windows process monitor | https://learn.microsoft.com/sysinternals |
| 210 | Process Hacker | Windows process analysis | https://processhacker.sourceforge.io |
| 211 | API Monitor | Windows API call monitoring | https://rohitab.com/apimonitor |
| 212 | Cheat Engine | Memory scanning/debugging | https://cheatengine.org |
| 213 | MemProcFS | Memory analysis as filesystem | https://github.com/ufrisk/MemProcFS |
| 214 | Flare VM | Windows RE VM (Mandiant) | https://github.com/mandiant/flare-vm |
| 215 | REMnux | Linux RE distro | https://remnux.org |

### 3.3 — Data Processing & Analytics

| # | Tool | Description | Link |
|---|------|-------------|------|
| 216 | jq | JSON processor | https://stedolan.github.io/jq |
| 217 | yq | YAML/XML processor | https://github.com/mikefarah/yq |
| 218 | csvkit | CSV toolkit | https://csvkit.readthedocs.io |
| 219 | Miller | CSV/JSON data processor | https://miller.readthedocs.io |
| 220 | xsv | Fast CSV utility (Rust) | https://github.com/BurntSushi/xsv |
| 221 | Ripgrep (rg) | Ultra-fast text search | https://github.com/BurntSushi/ripgrep |
| 222 | fd | Fast file finder | https://github.com/sharkdp/fd |
| 223 | Bat | Syntax-highlighted cat | https://github.com/sharkdp/bat |
| 224 | Fzf | Fuzzy finder | https://github.com/junegunn/fzf |
| 225 | DuckDB | In-process analytical DB | https://duckdb.org |
| 226 | Polars | Blazing-fast DataFrames (Rust) | https://pola.rs |
| 227 | DataFusion | In-memory query engine | https://github.com/apache/datafusion |
| 228 | ClickHouse | Columnar analytics DB | https://clickhouse.com |
| 229 | VictoriaMetrics | Metrics & time-series DB | https://victoriametrics.com |
| 230 | InfluxDB | Time-series database | https://influxdata.com |
| 231 | dbt | Data transformation tool | https://getdbt.com |
| 232 | Great Expectations | Data quality validation | https://greatexpectations.io |
| 233 | Airbyte | OSS data integration | https://airbyte.com |
| 234 | Meltano | OSS data pipeline platform | https://meltano.com |

### 3.4 — Cryptography & Password Analysis

| # | Tool | Description | Link |
|---|------|-------------|------|
| 235 | Hashcat | GPU-accelerated password recovery | https://hashcat.net/hashcat |
| 236 | John the Ripper | CPU password cracking | https://openwall.com/john |
| 237 | Hashtopolis | Distributed hashcat management | https://github.com/hashtopolis/server |
| 238 | OpenSSL | Encryption toolkit | https://openssl.org |
| 239 | GnuPG (GPG) | Encryption & signing | https://gnupg.org |
| 240 | Princeprocessor | PRINCE attack wordlist gen | https://github.com/hashcat/princeprocessor |
| 241 | Kwprocessor | Keyboard-walk password gen | https://github.com/hashcat/kwprocessor |
| 242 | maskprocessor | High-performance word gen | https://github.com/hashcat/maskprocessor |
| 243 | statsprocessor | Markov-chain password gen | https://github.com/hashcat/statsprocessor |
| 244 | SecLists | Wordlist collection | https://github.com/danielmiessler/SecLists |
| 245 | Probable-Wordlists | Real-world wordlists by freq | https://github.com/berzerk0/Probable-Wordlists |
| 246 | Pipal | Password analysis & stats | https://github.com/digininja/pipal |
| 247 | Crunch | Wordlist generator | https://github.com/crunchsec/crunch |
| 248 | RockYou | Classic password list | Kali Linux |

### 3.5 — Malware Analysis

| # | Tool | Description | Link |
|---|------|-------------|------|
| 249 | YARA | Malware pattern matching | https://virustotal.github.io/yara |
| 250 | CAPA | Malware capability analyzer | https://github.com/mandiant/capa |
| 251 | FLOSS | Obfuscated string extraction | https://github.com/mandiant/floss |
| 252 | Cuckoo Sandbox | Automated malware analysis | https://cuckoosandbox.org |
| 253 | CAPE | Malware sandbox (Cuckoo fork) | https://capev2.com |
| 254 | DRAKVUF | Dynamic malware analysis (Xen) | https://tklengyel.github.io/drakvuf |

---

## PHASE 4: EXPLOITATION

Taking action — web attacks, browser automation, authentication cracking, fuzzing.

### 4.1 — Web Application Testing

| # | Tool | Description | Link |
|---|------|-------------|------|
| 255 | Burp Suite | Web pentesting proxy | https://portswigger.net/burp |
| 256 | OWASP ZAP | Web app scanner | https://zaproxy.org |
| 257 | Nikto | Web server scanner | https://github.com/sullo/nikto |
| 258 | SQLMap | Automated SQL injection | https://sqlmap.org |
| 259 | Commix | Command injection detection | https://github.com/commixproject/commix |
| 260 | XSStrike | XSS detection & exploitation | https://github.com/s0md3v/XSStrike |
| 261 | Dalfox | XSS scanning tool | https://github.com/hahwul/dalfox |
| 262 | SSRFmap | SSRF exploitation | https://github.com/swisskyrepo/SSRFmap |
| 263 | GraphQLmap | GraphQL testing | https://github.com/swisskyrepo/GraphQLmap |
| 264 | jwt_tool | JWT testing | https://github.com/ticarpi/jwt_tool |
| 265 | JWT-Hack | JWT exploitation | https://github.com/hahwul/jwt-hack |
| 266 | Corsy | CORS misconfig scanner | https://github.com/s0md3v/Corsy |
| 267 | OpenRedirex | Open redirect checker | https://github.com/devanshbatham/OpenRedirex |
| 268 | WPScan | WordPress scanner | https://wpscan.com |
| 269 | Joomscan | Joomla scanner | https://github.com/rezasp/joomscan |
| 270 | CMSmap | CMS detection/scanner | https://github.com/Dionach/CMSmap |
| 271 | Droopescan | Drupal/WordPress/Joomla scan | https://github.com/droope/droopescan |
| 272 | Nuclei v3 | Template-based vuln scanner | https://github.com/projectdiscovery/nuclei |
| 273 | Interactsh | OOB interaction detection | https://github.com/projectdiscovery/interactsh |
| 274 | Tlsx | TLS/SSL scanner | https://github.com/projectdiscovery/tlsx |
| 275 | Proxify | Intercepting proxy (PD) | https://github.com/projectdiscovery/proxify |

### 4.2 — Directory & Content Discovery

| # | Tool | Description | Link |
|---|------|-------------|------|
| 276 | Dirb | Directory brute-forcer | https://github.com/v0re/dirb |
| 277 | Gobuster | URL/file/DNS busting (Go) | https://github.com/OJ/gobuster |
| 278 | Ffuf | Fast web fuzzer | https://github.com/ffuf/ffuf |
| 279 | Dirsearch | Web path discovery | https://github.com/maurosoria/dirsearch |
| 280 | Wfuzz | Web fuzzer | https://github.com/xmendez/wfuzz |

### 4.3 — Browser Automation (Agent-Driven)

| # | Tool | Description | Link |
|---|------|-------------|------|
| 281 | Playwright | Cross-browser automation | https://playwright.dev |
| 282 | Puppeteer | Headless Chrome/Chromium | https://pptr.dev |
| 283 | Selenium | Multi-browser framework | https://selenium.dev |
| 284 | Cypress | Front-end test framework | https://cypress.io |
| 285 | Playwright Python | Python Playwright bindings | https://pypi.org/project/playwright |
| 286 | Playwright Go | Go Playwright bindings | https://github.com/mxschmitt/playwright-go |
| 287 | Puppeteer Extra | Plugin-based extensions | https://github.com/berstend/puppeteer-extra |
| 288 | Playwright Stealth | Stealth plugin | https://github.com/nicedayzhu/playwright-stealth |
| 289 | SeleniumBase | Selenium + pytest + stealth | https://github.com/seleniumbase/SeleniumBase |
| 290 | DrissionPage | Python Chromium automation | https://github.com/g1879/DrissionPage |
| 291 | Browserbase | Cloud browser for AI agents | https://browserbase.com |
| 292 | Browserless | Headless browser as service | https://browserless.io |
| 293 | Stagehand | AI-driven web interaction | https://github.com/browserbase/stagehand |
| 294 | Browser Use | AI agent browser control | https://github.com/browser-use/browser-use |
| 295 | Splash | Lightweight browser (HTTP API) | https://splash.readthedocs.io |
| 296 | Chromium | Open-source headless browser | https://chromium.org |

### 4.4 — Authentication & Brute Force

| # | Tool | Description | Link |
|---|------|-------------|------|
| 297 | Hydra | Network login brute-forcer | https://github.com/vanhauser-thc/thc-hydra |
| 298 | Medusa | Parallel login brute-forcer | https://github.com/jmk-foofus/medusa |
| 299 | Crowbar | SSH/RDP brute-forcer | https://github.com/galkan/crowbar |
| 300 | Patator | Multi-protocol brute-forcer | https://github.com/lanjelot/patator |
| 301 | Ncrack | High-speed network auth cracker | https://nmap.org/ncrack |
| 302 | Kerbrute | Kerberos pre-auth brute-force | https://github.com/ropnop/kerbrute |

### 4.5 — Fuzzing Frameworks

| # | Tool | Description | Link |
|---|------|-------------|------|
| 303 | AFL++ | Feedback-driven fuzzer | https://github.com/AFLplusplus/AFLplusplus |
| 304 | LibFuzzer | In-process coverage-guided fuzzer | https://llvm.org/docs/LibFuzzer.html |
| 305 | Honggfuzz | Security-oriented fuzzer | https://github.com/google/honggfuzz |
| 306 | Boofuzz | Network protocol fuzzer | https://github.com/jtpereyda/boofuzz |
| 307 | Peach | Smart fuzzing framework | https://gitlab.com/peachtech/peach-fuzzer-community |
| 308 | Radamsa | General-purpose fuzzer | https://gitlab.com/akihe/radamsa |

---

## PHASE 5: PIVOT & POST-EXPLOITATION

Moving laterally, escalating privileges, dumping credentials, and expanding access.

### 5.1 — Privilege Escalation

| # | Tool | Description | Link |
|---|------|-------------|------|
| 309 | LinPEAS | Linux priv esc script | https://github.com/peass-ng/PEASS-ng |
| 310 | WinPEAS | Windows priv esc script | https://github.com/peass-ng/PEASS-ng |
| 311 | LinEnum | Linux enumeration | https://github.com/rebootuser/LinEnum |
| 312 | Linux Exploit Suggester | Kernel exploit suggestion | https://github.com/mzet-/linux-exploit-suggester |
| 313 | Windows Exploit Suggester | Windows kernel exploit | https://github.com/AonCyberLabs/Windows-Exploit-Suggester |
| 314 | GTFOBins | Linux binary abuse helpers | https://gtfobins.github.io |
| 315 | LOLBAS | Windows LOLBins/living-off-the-land | https://lolbas-project.github.io |
| 316 | Seatbelt | Windows host survey | https://github.com/GhostPack/Seatbelt |
| 317 | PowerUp | Windows privesc (PowerShell) | https://github.com/PowerShellMafia/PowerSploit |
| 318 | BeRoot | Windows/Linux privesc | https://github.com/AlessandroZ/BeRoot |

### 5.2 — Credential Dumping & Theft

| # | Tool | Description | Link |
|---|------|-------------|------|
| 319 | Mimikatz | Windows credential extraction | https://github.com/gentilkiwi/mimikatz |
| 320 | LaZagne | Local password recovery | https://github.com/AlessandroZ/LaZagne |
| 321 | Rubeus | Kerberos abuse toolkit | https://github.com/GhostPack/Rubeus |
| 322 | SharpDump | LSASS dump | https://github.com/GhostPack/SharpDump |
| 323 | SafetyKatz | Mini-mimikatz (C#) | https://github.com/GhostPack/SafetyKatz |
| 324 | ProcDump | Sysinternals process dumper | https://learn.microsoft.com/sysinternals |
| 325 | Procdump (Mimikatz) | LSASS process dump | Task Manager / ProcDump |
| 326 | KeeThief | KeePass extraction | https://github.com/GhostPack/KeeThief |
| 327 | SessionGopher | WinSCP/PuTTY session extract | https://github.com/Arvanaghi/SessionGopher |
| 328 | WCE | Windows Credential Editor | https://www.ampliasecurity.com |

### 5.3 — Lateral Movement

| # | Tool | Description | Link |
|---|------|-------------|------|
| 329 | CrackMapExec | Post-exploitation Swiss army knife | https://github.com/byt3bl33d3r/CrackMapExec |
| 330 | NetExec | CME fork (active dev) | https://github.com/Pennyw0rth/NetExec |
| 331 | Impacket | SMB/MS-RPC manipulation suite | https://github.com/fortra/impacket |
| 332 | Responder | LLMNR/NBT-NS/mDNS poisoner | https://github.com/lgandx/Responder |
| 333 | Evil-WinRM | WinRM shell for pentesting | https://github.com/Hackplayers/evil-winrm |
| 334 | BloodHound | AD relationship visualizer | https://github.com/BloodHoundAD/BloodHound |
| 335 | SharpHound | BloodHound ingestor | https://github.com/BloodHoundAD/SharpHound |
| 336 | Powermad | MADs abuse (PowerShell) | https://github.com/Kevin-Robertson/Powermad |
| 337 | PowerView | AD enumeration (PowerShell) | https://github.com/PowerShellMafia/PowerSploit |
| 338 | ADExplorer | AD explorer (Sysinternals) | https://learn.microsoft.com/sysinternals |
| 339 | MS17-010/EternalBlue | SMB exploit for lateral | Metasploit module |
| 340 | PSExec | Remote command execution | https://learn.microsoft.com/sysinternals |
| 341 | WMIExec | WMI remote execution | Impacket included |

### 5.4 — Active Directory Attacks

| # | Tool | Description | Link |
|---|------|-------------|------|
| 342 | DeathStar | Auto-domain priv esc | https://github.com/byt3bl33d3r/DeathStar |
| 343 | DCSync | Domain controller replication | Mimikatz/Impacket |
| 344 | AS-REP Roasting | Pre-auth Kerberos attack | Rubeus/Impacket |
| 345 | Kerberoasting | Service account attack | Rubeus/Impacket |
| 346 | Golden Ticket | KRBTGT hash abuse | Mimikatz |
| 347 | Silver Ticket | Service ticket forgery | Mimikatz |
| 348 | Skeleton Key | Domain persistence | Mimikatz |
| 349 | Dementor | Coerce auth relay | https://github.com/CraigFreyman/dementor |
| 350 | PrinterBug | SpoolService auth relay | https://github.com/leechristensen/SpoolSample |
| 351 | PetitPotam | NTLM relay coercer | https://github.com/topotam/PetitPotam |
| 352 | ZeroLogon | CVE-2020-1472 scanner | https://github.com/SecuraBV/CVE-2020-1472 |

### 5.5 — Cloud Post-Exploitation

| # | Tool | Description | Link |
|---|------|-------------|------|
| 353 | Pacu | AWS exploitation framework | https://github.com/RhinoSecurityLabs/pacu |
| 354 | Cloudsplaining | AWS IAM privilege analysis | https://github.com/salesforce/cloudsplaining |
| 355 | ScoutSuite | Multi-cloud audit tool | https://github.com/nccgroup/ScoutSuite |
| 356 | Prowler | AWS security assessment | https://github.com/prowler-cloud/prowler |
| 357 | CloudSploit | Cloud security scanning | https://github.com/aquasecurity/cloudsploit |
| 358 | CloudMapper | AWS visualization | https://github.com/duo-labs/cloudmapper |
| 359 | Stormspotter | Azure asset graph | https://github.com/Azure/Stormspotter |
| 360 | MicroBurst | Azure exploitation | https://github.com/NetSPI/MicroBurst |

---

## PHASE 6: C2 & TUNNELING

Command, control, persistence, and data exfiltration — maintaining access and moving data out.

### 6.1 — C2 Frameworks

| # | Tool | Description | Link |
|---|------|-------------|------|
| 361 | Metasploit | Full exploitation framework | https://metasploit.com |
| 362 | Empire | Post-exploitation agent framework | https://github.com/BC-SECURITY/Empire |
| 363 | Sliver | Go-based C2 | https://github.com/BishopFox/sliver |
| 364 | Havoc | Modern C2 framework | https://github.com/HavocFramework/Havoc |
| 365 | Covenant | .NET C2 framework | https://github.com/cobbr/Covenant |
| 366 | Mythic | Multi-agent C2 | https://github.com/its-a-feature/Mythic |
| 367 | Pupy | Cross-platform RAT (legit) | https://github.com/n1nj4sec/pupy |
| 368 | Starkiller | Havoc C2 frontend | https://github.com/BC-SECURITY/Starkiller |
| 369 | Merlin | Go-based C2 server | https://github.com/Ne0nd0g/merlin |
| 370 | NimPlant | Nim-based C2 implant | https://github.com/chvancooten/NimPlant |
| 371 | Cobalt Strike | Adversary simulation (legit) | https://cobaltstrike.com |
| 372 | Brute Ratel | Adversary simulation | https://bruteratel.com |
| 373 | DeimosC2 | Go + React C2 | https://github.com/DeimosC2/DeimosC2 |
| 374 | Faction | File-based C2 framework | https://github.com/FactionC2/Faction |
| 375 | RedGuard | C2 redirector/fronting | https://github.com/wikiZ/RedGuard |

### 6.2 — Tunnels & Reverse Proxies

| # | Tool | Description | Link |
|---|------|-------------|------|
| 376 | Chisel | Fast TCP/UDP tunnel (HTTP) | https://github.com/jpillora/chisel |
| 377 | Ligolo-ng | Advanced reverse tunneling | https://github.com/nicocha30/ligolo-ng |
| 378 | FRP | Fast reverse proxy | https://github.com/fatedier/frp |
| 379 | NPS | NAT penetration proxy | https://github.com/ehang-io/nps |
| 380 | Ngrok | Tunnel to localhost | https://ngrok.com |
| 381 | SSHuttle | Transparent proxy via SSH | https://github.com/sshuttle/sshuttle |
| 382 | rpivot | SOCKS reverse proxy | https://github.com/klsecservices/rpivot |
| 383 | Neo-reGeorg | HTTP tunnel | https://github.com/L-codes/Neo-reGeorg |
| 384 | Stowaway | Multi-hop proxy tool | https://github.com/ph4ntonn/Stowaway |
| 385 | Proxychains-ng | Proxy chaining | https://github.com/rofl0r/proxychains-ng |
| 386 | Cloudflare WARP | Global network proxy | https://1.1.1.1 |

### 6.3 — DNS & Covert Tunnels

| # | Tool | Description | Link |
|---|------|-------------|------|
| 387 | DNSCat2 | DNS command & control tunnel | https://github.com/iagox86/dnscat2 |
| 388 | Iodine | IPv4 over DNS tunnel | https://github.com/yarrick/iodine |
| 389 | DNSStager | DNS-based payload staging | https://github.com/mhaskar/DNSStager |
| 390 | Dnscat2-Powershell | PowerShell DNS C2 | https://github.com/lukebaggett/dnscat2-powershell |
| 391 | WebSocket Tunnel | WS-based tunneling | https://github.com/vi/websocat |

### 6.4 — Data Exfiltration

| # | Tool | Description | Link |
|---|------|-------------|------|
| 392 | Steghide | Image steganography | https://github.com/StefanoDeVuono/steghide |
| 393 | Zsteg | PNG/BMP steganography | https://github.com/zed-0xff/zsteg |
| 394 | Snow | Whitespace steganography | https://darkside.com.au/snow |
| 395 | ExifTool | Embed/exfil in metadata | https://exiftool.org |
| 396 | PowerSploit Exfil | PowerShell exfil scripts | https://github.com/PowerShellMafia/PowerSploit |
| 397 | GoPhish | Phishing exfil | https://getgophish.com |

---

## PHASE 7: MEMORY & STORAGE

Vector databases, knowledge management, SQL/NoSQL, and caching for agent state.

### 7.1 — Vector Databases

| # | Tool | Description | Link |
|---|------|-------------|------|
| 398 | Chroma | OSS vector database | https://github.com/chroma-core/chroma |
| 399 | Qdrant | Vector similarity search (Rust) | https://qdrant.tech |
| 400 | Milvus | Distributed vector DB | https://milvus.io |
| 401 | Weaviate | Vector + hybrid search | https://weaviate.io |
| 402 | Pinecone | Managed vector DB | https://pinecone.io |
| 403 | LanceDB | Embedded vector DB | https://lancedb.github.io/lancedb |
| 404 | pgvector | PostgreSQL vector extension | https://github.com/pgvector/pgvector |
| 405 | sqlite-vec | SQLite vector search | https://github.com/asg017/sqlite-vec |

### 7.2 — Knowledge Management

| # | Tool | Description | Link |
|---|------|-------------|------|
| 406 | Obsidian | Local-first knowledge base | https://obsidian.md |
| 407 | Logseq | OSS knowledge management | https://logseq.com |
| 408 | SiYuan | Local-first knowledge base | https://github.com/siyuan-note/siyuan |
| 409 | Affine | Privacy-focused collaborative docs | https://affine.pro |
| 410 | HedgeDoc | Collaborative markdown | https://hedgedoc.org |
| 411 | Memos | Lightweight self-hosted notes | https://usememos.com |
| 412 | BookStack | Self-hosted documentation | https://bookstackapp.com |
| 413 | Wiki.js | Modern wiki platform | https://js.wiki |
| 414 | Outline | Team knowledge base | https://outline.com |

### 7.3 — Database Tools

| # | Tool | Description | Link |
|---|------|-------------|------|
| 415 | SQLite CLI | Embedded database | https://sqlite.org/cli.html |
| 416 | psql | PostgreSQL CLI | https://postgresql.org |
| 417 | MySQL CLI | MySQL client | https://dev.mysql.com/doc/refman/en/mysql.html |
| 418 | Redis CLI | In-memory data store | https://redis.io |
| 419 | MongoDB Shell | MongoDB client | https://mongodb.com/products/shell |
| 420 | DBeaver | Universal DB client | https://dbeaver.io |
| 421 | sqlc | Type-safe SQL generation | https://sqlc.dev |
| 422 | SQLBoiler | Go ORM from database | https://github.com/volatiletech/sqlboiler |

---

## PHASE 8: COMMUNICATION & OUTPUT

Sending results, notifications, messaging, and reporting.

### 8.1 — Messaging & Notifications

| # | Tool | Description | Link |
|---|------|-------------|------|
| 423 | Signal-CLI | Signal messaging via CLI | https://github.com/AsamK/signal-cli |
| 424 | Telegram CLI | Telegram messaging CLI | https://github.com/vysheng/tg |
| 425 | Telegram Bot API | Free bot messaging | https://core.telegram.org/bots/api |
| 426 | Discord Webhooks | Free webhook notifications | https://discord.com/developers/docs/resources/webhook |
| 427 | Slack CLI | Slack from terminal | https://api.slack.com/slack-cli |
| 428 | Matrix Clients | Decentralized messaging | https://matrix.org |
| 429 | IRC (irssi) | CLI IRC client | https://irssi.org |
| 430 | Apprise | Multi-platform notifications | https://github.com/caronc/apprise |
| 431 | Ntfy.sh | Pub-sub push notifications | https://ntfy.sh |
| 432 | Gotify | Self-hosted push notifications | https://gotify.net |
| 433 | Pushover | Push notifications (one-time) | https://pushover.net |
| 434 | Mattermost | Self-hosted Slack alternative | https://mattermost.com |
| 435 | Zulip | Threaded team chat | https://zulip.com |
| 436 | RocketChat | OSS team messaging | https://rocket.chat |

### 8.2 — Email

| # | Tool | Description | Link |
|---|------|-------------|------|
| 437 | SMTP CLI (msmtp) | Lightweight email sending | https://marlam.de/msmtp |
| 438 | Mailutils | GNU mail utilities | https://mailutils.org |
| 439 | Swaks | SMTP testing toolkit | https://jetmore.org/john/code/swaks |
| 440 | SendEmail | Simple SMTP client | https://github.com/mogaal/sendemail |

### 8.3 — SMS APIs (Free Tier Available)

| # | Tool | Description | Link |
|---|------|-------------|------|
| 441 | Twilio CLI | SMS/voice (free tier) | https://twilio.com/docs/twilio-cli |
| 442 | Vonage CLI | SMS API (free tier) | https://developer.vonage.com |
| 443 | Plivo CLI | SMS/voice API | https://plivo.com |
| 444 | AWS SNS CLI | Notification service (free tier) | https://aws.amazon.com/sns |
| 445 | Telnyx | SMS/voice API | https://telnyx.com |

### 8.4 — Reporting & Documentation

| # | Tool | Description | Link |
|---|------|-------------|------|
| 446 | Pandoc | Universal doc converter | https://pandoc.org |
| 447 | Dillinger | Markdown to HTML | https://dillinger.io |
| 448 | MkDocs | Project documentation | https://mkdocs.org |
| 449 | Docusaurus | Documentation site builder | https://docusaurus.io |
| 450 | slither-format | Automated report generation | https://github.com/crytic/slither |

---

## PHASE 9: DEFENSE & EVASION

OPSEC, proxy chains, encryption, log cleaning, and avoiding detection.

### 9.1 — Anonymity & Proxies

| # | Tool | Description | Link |
|---|------|-------------|------|
| 451 | Tor | Anonymous network | https://torproject.org |
| 452 | Proxychains-ng | Force proxy on any app | https://github.com/rofl0r/proxychains-ng |
| 453 | Torsocks | Route through Tor | https://gitlab.torproject.org/tpo/core/torsocks |
| 454 | OpenVPN | VPN client/server | https://openvpn.net |
| 455 | WireGuard | Fast modern VPN | https://wireguard.com |
| 456 | Tailscale | Zero-config WireGuard mesh | https://tailscale.com |
| 457 | ZeroTier | SDN / peer-to-peer VPN | https://zerotier.com |

### 9.2 — Encryption & Steganography

| # | Tool | Description | Link |
|---|------|-------------|------|
| 458 | OpenSSL | Encryption toolkit | https://openssl.org |
| 459 | GnuPG | Encryption & signing | https://gnupg.org |
| 460 | VeraCrypt | Disk encryption | https://veracrypt.fr |
| 461 | Steghide | Steganography in images | https://github.com/StefanoDeVuono/steghide |
| 462 | Zsteg | PNG/BMP steganography | https://github.com/zed-0xff/zsteg |
| 463 | Age | Modern file encryption | https://age-encryption.org |
| 464 | Minisign | Minimal crypto signing | https://github.com/jedisct1/minisign |

### 9.3 — Log Cleaning & Anti-Forensics

| # | Tool | Description | Link |
|---|------|-------------|------|
| 465 | Timestomp | Change file timestamps | Metasploit/Impacket |
| 466 | Meterpreter Cleanup | Anti-forensics scripts | Metasploit |
| 467 | Prefetch Parser | Prefetch file management | https://github.com/PoorBillionaire/PECmd |
| 468 | Logtamer | Log tampering for Windows | https://github.com/jaredcatkinson/LogTamer |
| 469 | Clear-EventLog | PowerShell event log clear | PowerShell cmdlet |
| 470 | BleachBit | System cleaner | https://bleachbit.org |
| 471 | Shred | Secure file deletion | Linux coreutils |
| 472 | wipe | Secure file erasure | https://github.com/berke/wipe |

### 9.4 — EDR & AV Evasion

| # | Tool | Description | Link |
|---|------|-------------|------|
| 473 | AMSI Bypass | Bypass Windows AMSI | Various PS scripts |
| 474 | Shellter | Dynamic PE shellcode injector | https://shellterproject.com |
| 475 | Veil | Payload generator (evasion) | https://github.com/Veil-Framework/Veil |
| 476 | PEzor | PE packer/evasion | https://github.com/phra/PEzor |
| 477 | ScareCrow | EDR evasion loader | https://github.com/optiv/ScareCrow |
| 478 | Nimcrypt | Nim-based crypter | https://github.com/icyguider/Nimcrypt |
| 479 | Donut | Position-independent shellcode | https://github.com/TheWover/donut |
| 480 | msfvenom | Payload generation | Metasploit |

---

## PHASE 10: FORENSICS & INCIDENT RESPONSE

Post-mortem, memory analysis, disk forensics, timeline creation.

### 10.1 — Memory Forensics

| # | Tool | Description | Link |
|---|------|-------------|------|
| 481 | Volatility 2 | Memory forensics framework | https://volatilityfoundation.org |
| 482 | Volatility 3 | Memory forensics (Python 3) | https://github.com/volatilityfoundation/volatility3 |
| 483 | MemProcFS | Memory as filesystem | https://github.com/ufrisk/MemProcFS |
| 484 | Rekall | Memory forensics (Google fork) | https://github.com/google/rekall |
| 485 | AVML | Linux memory acquisition | https://github.com/microsoft/avml |
| 486 | LiME | Linux Memory Extractor | https://github.com/504ensicsLabs/LiME |
| 487 | DumpIt | Windows memory dump | https://www.magnetforensics.com |
| 488 | WinPmem | Windows memory acquisition | https://github.com/Velocidex/WinPmem |

### 10.2 — Disk Forensics & File Analysis

| # | Tool | Description | Link |
|---|------|-------------|------|
| 489 | Autopsy | Digital forensics platform | https://autopsy.com |
| 490 | Sleuth Kit | CLI forensic toolkit | https://sleuthkit.org |
| 491 | Guymager | Disk imaging | https://guymager.sourceforge.io |
| 492 | Ddrescue | Data recovery | https://gnu.org/software/ddrescue |
| 493 | Photorec | File recovery | https://cgsecurity.org/wiki/PhotoRec |
| 494 | TestDisk | Partition recovery | https://cgsecurity.org/wiki/TestDisk |
| 495 | FTK Imager | Forensic imaging (free) | https://accessdata.com |
| 496 | Bulk Extractor | Forensic data extraction | https://github.com/simsong/bulk_extractor |
| 497 | Plaso (log2timeline) | Timeline analysis | https://github.com/log2timeline/plaso |
| 498 | RECmd | Registry explorer CLI | https://github.com/EricZimmerman/RECmd |
| 499 | RegRipper | Registry analysis | https://github.com/keydet89/RegRipper3.0 |
| 500 | KAPE | Artifact collection & parsing | https://kroll.com/kape |

### 10.3 — Endpoint Detection & Log Analysis

| # | Tool | Description | Link |
|---|------|-------------|------|
| 501 | Wazuh | OSS SIEM + XDR | https://wazuh.com |
| 502 | Elastic Security | SIEM + endpoint (free tier) | https://elastic.co/security |
| 503 | Velociraptor | Endpoint visibility & IR | https://github.com/Velocidex/velociraptor |
| 504 | Osquery | SQL-based OS instrumentation | https://osquery.io |
| 505 | Fleet | Osquery fleet management | https://fleetdm.com |
| 506 | Kolide | Osquery endpoint management | https://kolide.com |
| 507 | Hayabusa | Windows event log SIEM | https://github.com/Yamato-Security/hayabusa |
| 508 | Chainsaw | Windows event log hunting | https://github.com/countercept/chainsaw |
| 509 | Sysmon | Windows system monitoring | https://learn.microsoft.com/sysinternals/downloads/sysmon |
| 510 | Suricata | Network IDS/IPS | https://suricata.io |
| 511 | Snort | Network intrusion detection | https://snort.org |
| 512 | Zeek (Bro) | Network analysis framework | https://zeek.org |
| 513 | Lynis | System auditing | https://cisofy.com/lynis |
| 514 | Rkhunter | Rootkit hunter | https://rkhunter.sourceforge.net |
| 515 | Chkrootkit | Rootkit detection | https://chkrootkit.org |
| 516 | ClamAV | Antivirus (OSS) | https://clamav.net |

### 10.4 — Cloud Forensics

| # | Tool | Description | Link |
|---|------|-------------|------|
| 517 | AWS CloudTrail | AWS API audit | https://aws.amazon.com/cloudtrail |
| 518 | Azure Activity Log | Azure subscription audit | Azure Portal |
| 519 | GCP Audit Logs | GCP audit logging | GCP Console |
| 520 | DumpsterDiver | Cloud data exfil detection | https://github.com/securing/DumpsterDiver |

---

## CROSS-CUTTING: DEVELOPMENT & INFRASTRUCTURE

Tools used across multiple pipeline phases — CI/CD, containers, IaC, monitoring.

### Dev Tools

| # | Tool | Description | Link |
|---|------|-------------|------|
| 521 | Git | Version control | https://git-scm.com |
| 522 | gh | GitHub CLI | https://cli.github.com |
| 523 | glab | GitLab CLI | https://gitlab.com/gitlab-org/cli |
| 524 | Make | Build automation | https://gnu.org/software/make |
| 525 | Just | Command runner (Rust) | https://github.com/casey/just |
| 526 | Task | Task runner (Go) | https://taskfile.dev |
| 527 | Tmux | Terminal multiplexer | https://github.com/tmux/tmux |
| 528 | Screen | Terminal multiplexer | https://gnu.org/software/screen |
| 529 | Nix | Package manager / declarative config | https://nixos.org |
| 530 | asdf | Version manager (multiple runtimes) | https://asdf-vm.com |
| 531 | mise | Dev tools version manager | https://mise.jdx.dev |
| 532 | direnv | Directory env vars | https://direnv.net |
| 533 | chezmoi | Dotfile manager | https://chezmoi.io |
| 534 | Htop | Interactive process viewer | https://htop.dev |
| 535 | Btop | Resource monitor (Rust) | https://github.com/aristocratos/btop |
| 536 | Ncdu | Disk usage analyzer | https://dev.yorhel.nl/ncdu |
| 537 | Tldr | Simplified man pages | https://tldr.sh |

### CI/CD & Automation

| # | Tool | Description | Link |
|---|------|-------------|------|
| 538 | Airflow | DAG-based workflow | https://airflow.apache.org |
| 539 | Prefect | Workflow orchestration | https://prefect.io |
| 540 | n8n | Workflow automation (self-host) | https://n8n.io |
| 541 | Node-RED | Low-code flow programming | https://nodered.org |
| 542 | Huginn | Self-hosted agent system | https://github.com/huginn/huginn |
| 543 | Drone CI | OSS CI/CD | https://drone.io |
| 544 | Jenkins | CI/CD automation | https://jenkins.io |
| 545 | Act | Run GitHub Actions locally | https://github.com/nektos/act |
| 546 | Earthly | CI/CD framework (Earthfile) | https://earthly.dev |
| 547 | Dagger | CI/CD as code | https://dagger.io |

### Container & Orchestration

| # | Tool | Description | Link |
|---|------|-------------|------|
| 548 | Docker | Container runtime | https://docker.com |
| 549 | Docker Compose | Multi-container orchestration | https://docs.docker.com/compose |
| 550 | Podman | Daemonless containers | https://podman.io |
| 551 | Buildah | Container image builder | https://buildah.io |
| 552 | Skopeo | Container image inspection | https://github.com/containers/skopeo |
| 553 | Dive | Docker image layer explorer | https://github.com/wagoodman/dive |
| 554 | Kubectl | Kubernetes CLI | https://kubernetes.io |
| 555 | Minikube | Local Kubernetes | https://minikube.sigs.k8s.io |
| 556 | Kind | K8s-in-Docker | https://kind.sigs.k8s.io |
| 557 | K3s | Lightweight K8s | https://k3s.io |
| 558 | Helm | K8s package manager | https://helm.sh |
| 559 | K9s | K8s terminal UI | https://k9scli.io |
| 560 | stern | Multi-pod log tailing | https://github.com/stern/stern |
| 561 | kubectx/kubens | K8s context/namespace switching | https://github.com/ahmetb/kubectx |
| 562 | Garden | K8s dev/test environments | https://garden.io |

### Infrastructure as Code

| # | Tool | Description | Link |
|---|------|-------------|------|
| 563 | Terraform | IaC for cloud | https://terraform.io |
| 564 | OpenTofu | Terraform OSS fork | https://opentofu.org |
| 565 | Pulumi | IaC with real languages | https://pulumi.com |
| 566 | Ansible | Automation & config mgmt | https://ansible.com |
| 567 | Vagrant | VM environment mgmt | https://vagrantup.com |
| 568 | Packer | Machine image builder | https://packer.io |
| 569 | CloudFormation | AWS IaC | AWS native |

### Security Monitoring

| # | Tool | Description | Link |
|---|------|-------------|------|
| 570 | Wazuh | OSS SIEM + XDR | https://wazuh.com |
| 571 | Grafana | Metrics & dashboards | https://grafana.com |
| 572 | Prometheus | OSS monitoring & alerting | https://prometheus.io |
| 573 | Grafana Loki | Log aggregation | https://grafana.com/oss/loki |
| 574 | SigNoz | OpenTelemetry-native observability | https://signoz.io |
| 575 | OpenSearch | OSS search + SIEM | https://opensearch.org |
| 576 | Splunk | Enterprise SIEM | https://splunk.com |
| 577 | Uptime Kuma | Self-hosted uptime monitor | https://github.com/louislam/uptime-kuma |
| 578 | Healthchecks | Cron job monitoring | https://healthchecks.io |
| 579 | Netdata | Real-time infrastructure monitor | https://netdata.cloud |
| 580 | Checkmk | IT monitoring | https://checkmk.com |
| 581 | Icinga | OSS monitoring | https://icinga.com |
| 582 | Nagios | Legacy OSS monitoring | https://nagios.org |

### Honeypots & Deception

| # | Tool | Description | Link |
|---|------|-------------|------|
| 583 | Cowrie | SSH/Telnet honeypot | https://github.com/cowrie/cowrie |
| 584 | T-Pot | All-in-one honeypot platform | https://github.com/telekom-security/tpotce |
| 585 | Dionaea | Malware capture honeypot | https://github.com/DinoTools/dionaea |
| 586 | Honeytrap | Network service honeypot | https://github.com/honeytrap/honeytrap |
| 587 | OpenCanary | Multi-service honeypot | https://github.com/thinkst/opencanary |

### Mobile Security

| # | Tool | Description | Link |
|---|------|-------------|------|
| 588 | Frida | Dynamic instrumentation | https://frida.re |
| 589 | Objection | Mobile exploration w/ Frida | https://github.com/sensepost/objection |
| 590 | JADX | Dex-to-Java decompiler | https://github.com/skylot/jadx |
| 591 | APKTool | APK reverse engineering | https://apktool.org |
| 592 | MobSF | Mobile app pentesting | https://github.com/MobSF/Mobile-Security-Framework-MobSF |
| 593 | Magisk | Android root + modules | https://github.com/topjohnwu/Magisk |
| 594 | scrcpy | Android mirroring & control | https://github.com/Genymobile/scrcpy |
| 595 | ADB | Android debug bridge | Android SDK |
| 596 | Genymotion | Android emulator | https://genymotion.com |

### IoT & Hardware

| # | Tool | Description | Link |
|---|------|-------------|------|
| 597 | Flipper Zero | Multi-tool (RFID/BLE/NFC) | https://flipperzero.one |
| 598 | Proxmark3 | RFID/NFC analysis | https://proxmark.com |
| 599 | HackRF One | SDR transmit/receive | https://greatscottgadgets.com/hackrf |
| 600 | RTL-SDR | SDR receiver | https://rtl-sdr.com |
| 601 | Arduino CLI | Embedded dev CLI | https://arduino.cc |
| 602 | ESP32 Tools | IoT firmware analysis | ESP-IDF toolchain |

### Cloud & Network Intelligence Platforms

| # | Tool | Description | Link |
|---|------|-------------|------|
| 603 | Kentik AI Advisor | AI network intelligence | https://kentik.com |
| 604 | Netdata Topology | Real-time topology from kernel | https://netdata.cloud |
| 605 | Cisco ThousandEyes | Internet/SaaS path visibility | https://thousandeyes.com |
| 606 | NetBrain | Context-aware digital twin | https://netbrain.com |
| 607 | Datadog Cloud NPM | Service-to-service traffic mapping | https://datadoghq.com |
| 608 | Dynatrace Davis AI | AI root cause analysis | https://dynatrace.com |
| 609 | Zabbix 7 | OSS monitoring (AI baselining) | https://zabbix.com |
| 610 | Crowdsec | OSS collaborative IPS | https://crowdsec.net |

### Cloud Security Platforms (CNAPP)

| # | Tool | Description | Link |
|---|------|-------------|------|
| 611 | Wiz | Cloud security posture leader | https://wiz.io |
| 612 | CrowdStrike Falcon Cloud | CNAPP/CWPP | https://crowdstrike.com |
| 613 | Prisma Cloud | Full lifecycle cloud security | https://paloaltonetworks.com/prisma |
| 614 | Aqua Security | Container/K8s security | https://aquasec.com |
| 615 | Sysdig | Runtime container/K8s security | https://sysdig.com |
| 616 | Falco | OSS K8s runtime security | https://falco.org |
| 617 | Checkov | IaC vulnerability scanning | https://checkov.io |
| 618 | OPA (OpenPolicyAgent) | Cloud-native policy engine | https://openpolicyagent.org |
| 619 | Kyverno | K8s policy engine | https://kyverno.io |
| 620 | Trivy | OSS vulnerability scanner | https://github.com/aquasecurity/trivy |
| 621 | Grype | OSS vulnerability scanner | https://github.com/anchore/grype |
| 622 | Syft | OSS SBOM generator | https://github.com/anchore/syft |
| 623 | OWASP DC | Dependency vulnerability scan | https://owasp.org/www-project-dependency-check |

### Blockchain Security

| # | Tool | Description | Link |
|---|------|-------------|------|
| 624 | Slither | Solidity static analyzer | https://github.com/crytic/slither |
| 625 | Echidna | EVM fuzzer | https://github.com/crytic/echidna |
| 626 | Foundry | Smart contract toolchain | https://book.getfoundry.sh |
| 627 | Mythril | EVM security analysis | https://github.com/Consensys/mythril |
| 628 | Hardhat | Ethereum dev environment | https://hardhat.org |
| 629 | DappTools | CLI Ethereum development | https://dapp.tools |
| 630 | Semantic Gaps | Solidity code analysis | https://github.com/Consensys/semantic-gaps |

---

## APPENDIX: PIPELINE FLOW CHART

```
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 0: AI RUNTIMES                                                    │
│  Agent Frameworks → SDKs → LLM Providers                                 │
│  (Armature, LangChain, Ollama, Groq...)                                  │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: RECONNAISSANCE                                                 │
│  OSINT → Asset Discovery → Network Scan → Web Crawl → Fingerprint        │
│  (theHarvester, Amass, Nmap, Shodan, WhatWeb...)                        │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: INGESTION & CRAWLING                                          │
│  Web Fetch → Packet Capture → File Parse → Signal Capture                │
│  (Curl, Tcpdump, Pandoc, Pandas, BeautifulSoup...)                      │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: ANALYSIS & INTELLIGENCE                                       │
│  SAST → Binary RE → Data Analytics → Crypto → Malware Analysis          │
│  (Semgrep, Ghidra, Polars, Hashcat, YARA...)                            │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: EXPLOITATION                                                  │
│  Web Attack → Browser Auto → Brute Force → Fuzz → Phishing              │
│  (Burp, Playwright, Hydra, SQLMap, AFL++...)                            │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 5: PIVOT & POST-EXPLOITATION                                     │
│  PrivEsc → Cred Dump → Lateral → AD Attack → Cloud Pivot                │
│  (LinPEAS, Mimikatz, CrackMapExec, BloodHound, Pacu...)                 │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 6: C2 & TUNNELING                                                │
│  C2 Frameworks → Reverse Proxies → Tunnels → Data Exfil                 │
│  (Metasploit, Sliver, Chisel, Ligolo, DNSCat2...)                       │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 7: MEMORY & STORAGE                                              │
│  Vector DBs → Knowledge Mgmt → SQL/NoSQL → Cache                        │
│  (Chroma, Obsidian, DuckDB, PostgreSQL...)                              │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 8: COMMUNICATION                                                 │
│  Messaging → Email → SMS → Webhooks → Reporting                          │
│  (Signal, Telegram, Apprise, Twilio, Pandoc...)                         │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 9: DEFENSE & EVASION                                             │
│  Anonymity → Encryption → Stego → Log Clean → EDR Evasion               │
│  (Tor, Proxychains, GPG, Steghide, Veil...)                             │
└───────────────────────────────────┬──────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 10: FORENSICS & IR                                               │
│  Memory → Disk → Endpoint → Timeline → Cloud                            │
│  (Volatility, Autopsy, Osquery, Hayabusa, Plaso...)                     │
└──────────────────────────────────────────────────────────────────────────┘

CROSS-CUTTING LAYERS:
  ┌────────────────────────────────────────────────────────────────────────┐
  │ Dev Tools │ CI/CD │ Containers │ IaC │ Monitoring │ Honeypots │ Mobile │
  └────────────────────────────────────────────────────────────────────────┘
```

---

## QUICK STATS

| Pipeline Phase | Count |
|----------------|-------|
| Phase 0: AI Runtimes & Frameworks | 64 |
| Phase 1: Reconnaissance | 68 |
| Phase 2: Ingestion & Crawling | 44 |
| Phase 3: Analysis & Intelligence | 79 |
| Phase 4: Exploitation | 53 |
| Phase 5: Pivot & Post-Exploitation | 48 |
| Phase 6: C2 & Tunneling | 37 |
| Phase 7: Memory & Storage | 22 |
| Phase 8: Communication | 23 |
| Phase 9: Defense & Evasion | 30 |
| Phase 10: Forensics & IR | 36 |
| Cross-Cutting (Dev, Infra, Cloud, Mobile) | 78 |
| **Total (deduplicated)** | **~630** |

---

> **Use responsibly.** All tools listed have legitimate use in security research,
> penetration testing, system administration, and development. You must own the
> systems you test or have explicit written authorization.
> No paid API keys required — free tiers and CLI tools only.
