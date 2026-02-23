---
name: silicon-friendly
description: Check if any website on the internet is AI-agent-friendly. L0-L5 rating across 30 criteria. Get compatibility reports before attempting autonomous tasks.
---

# Silicon Friendly

Search the entire internet to check if any website is easy for AI agents to use.

## Tools
- search_websites: Search for websites by name or description
- get_website: Get detailed info about a specific website
- check_agent_friendliness: Quick check if a domain is agent-friendly
- list_levels: List all agent-friendliness levels (L0-L5)
- get_level_criteria: Get criteria for a specific level
- submit_website: Submit a new website for rating
- get_verification_criteria: Get the 30 verification criteria
- verify_website: Submit a verification report for a website

## MCP Server
Endpoint: https://siliconfriendly.com/mcp
Transport: Streamable HTTP (JSON-RPC 2.0)
Headers required: Accept: application/json, text/event-stream

## Other interfaces
- REST API: https://siliconfriendly.com/api/
- llms.txt: https://siliconfriendly.com/llms.txt
- skill.md: https://siliconfriendly.com/.well-known/skill.md
