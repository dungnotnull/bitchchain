import os
path = r'D:\bitchchain-agent\config\agent_config.yaml'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('chain_db: "chain.db"', 'chain_db: "data/chain.db"')
content = content.replace('agent_db: "agent_memory.db"', 'agent_db: "data/agent_memory.db"')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated config to use data/ directory')
