FROM n8nio/n8n:latest
USER root
RUN npm install -g @modelcontextprotocol/server-filesystem
RUN mkdir /data && chown node:node /data
USER node
CMD n8n start & mcp-server-filesystem --root /data