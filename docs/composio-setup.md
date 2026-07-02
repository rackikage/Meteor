# Composio setup (OSINT / connector auth)

Composio links external apps to agents. Use it for **recon and OSINT** (GitHub,
search, ticketing) — not for harvesting exploit payloads or reverse shells.

## Login (interactive — run in your terminal)

```bash
/home/emperor/.composio/composio login
```

Browser opens; authenticate at https://dashboard.composio.dev/

## Link toolkits

```bash
# Examples — pick what you need for authorized research
/home/emperor/.composio/composio link github
/home/emperor/.composio/composio search "web search osint"
/home/emperor/.composio/composio connections list
```

## Execute a connected tool

```bash
/home/emperor/.composio/composio execute GITHUB_GET_THE_AUTHENTICATED_USER
```

## Meteor integration (manual today)

Meteor's native exploit intel is `web.exploit_surface`, `web.research`, and
`searchsploit__search` via `meteor-mcp`. Composio complements that for apps
Meteor does not wrap — run Composio from shell or a future MCP bridge, not as
a payload scraper.

## Not supported

- ParseHub / bulk scraping of malicious shell code
- Open Interpreter driving unauthorized exploit deployment
- Adding reverse-shell payload libraries to Meteor

Authorized pentest only. Set `METEOR_MCP_ALLOWED_CIDR` before offensive tools.
