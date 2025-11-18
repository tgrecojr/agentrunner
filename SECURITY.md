# Security Policy

## Reporting Security Issues

If you discover a security vulnerability in the Multi-Agent Orchestration Platform, please report it by emailing [security contact - to be added]. Please do not create public GitHub issues for security vulnerabilities.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Security Best Practices

### 1. Credentials Management

#### Never Commit Secrets

**CRITICAL**: Never commit the following to version control:
- `.env` files (only `.env.example` should be committed)
- API keys (OpenAI, Anthropic, AWS, Slack)
- Database passwords
- Private keys or certificates

#### Environment Variables

All sensitive credentials MUST be set via environment variables:

```bash
# BAD - Hardcoded in code
POSTGRES_PASSWORD = "mypassword123"

# GOOD - From environment
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
```

#### Generate Secure Passwords

Use strong, randomly generated passwords:

```bash
# Generate 32-character base64 password
openssl rand -base64 32

# Generate 64-character hex password
openssl rand -hex 64
```

**Minimum Requirements**:
- PostgreSQL password: 16+ characters
- RabbitMQ password: 16+ characters
- API keys: Use provider-generated keys
- Slack secrets: Use Slack-provided values

### 2. Docker Compose Security

#### Required Changes Before Production

The `docker-compose.yml` file requires these environment variables to be set:

```bash
# MUST be set in .env file - docker-compose will fail if missing
POSTGRES_PASSWORD=<secure-password>
RABBITMQ_USER=<username>
RABBITMQ_PASSWORD=<secure-password>
```

To verify your environment is configured correctly:

```bash
# Test that required variables are set
docker-compose config

# If any variable is missing, you'll see an error like:
# "POSTGRES_PASSWORD is not set"
```

#### Network Security

```yaml
# Production: Use custom networks with encryption
networks:
  agent-network:
    driver: overlay
    driver_opts:
      encrypted: "true"
```

#### Volume Permissions

```bash
# Ensure proper ownership of volumes
sudo chown -R 999:999 ./data/postgres  # PostgreSQL UID
sudo chown -R 999:999 ./data/redis     # Redis UID
```

### 3. API Security

#### Enable Authentication

For production, enable API authentication:

```bash
# .env file
API_AUTH_ENABLED=true
API_KEY_HEADER=X-API-Key
API_KEY=$(openssl rand -base64 32)
```

#### Use TLS/SSL

Enable TLS for all services in production:

```bash
# .env file
TLS_ENABLED=true
TLS_CERT_PATH=/app/certs/server.crt
TLS_KEY_PATH=/app/certs/server.key
TLS_CA_PATH=/app/certs/ca.crt
```

Generate self-signed certificates for testing:

```bash
# Generate private key
openssl genrsa -out server.key 2048

# Generate certificate signing request
openssl req -new -key server.key -out server.csr

# Generate self-signed certificate (valid 365 days)
openssl x509 -req -days 365 -in server.csr \
  -signkey server.key -out server.crt
```

For production, use certificates from a trusted CA (Let's Encrypt, etc.).

#### Rate Limiting

Configure rate limiting to prevent abuse:

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

### 4. Database Security

#### PostgreSQL Hardening

```bash
# Use SSL connections
POSTGRES_SSL_MODE=require

# Set statement timeout to prevent long-running queries
POSTGRES_STATEMENT_TIMEOUT=30000  # 30 seconds

# Limit connections per user
POSTGRES_MAX_CONNECTIONS=100
```

#### Redis Security

```bash
# Enable Redis password authentication
REDIS_PASSWORD=<secure-password>

# Disable dangerous commands
REDIS_RENAME_COMMAND_CONFIG=yes
```

#### Regular Backups

```bash
# Backup PostgreSQL daily
0 2 * * * /usr/local/bin/backup-postgres.sh

# Backup retention: 30 days
find /backups/postgres -mtime +30 -delete
```

See `docs/OPERATIONS_GUIDE.md` for detailed backup procedures.

### 5. LLM API Key Security

#### Separate Keys per Environment

Use different API keys for each environment:

```bash
# Development
OPENAI_API_KEY=sk-dev-...

# Staging
OPENAI_API_KEY=sk-staging-...

# Production
OPENAI_API_KEY=sk-prod-...
```

#### Key Rotation

Rotate API keys quarterly:

1. Generate new API key in provider dashboard
2. Update key in secrets manager
3. Update `.env` file or environment variables
4. Restart services: `docker-compose restart`
5. Revoke old API key after verification

#### Monitor API Usage

Enable usage monitoring to detect anomalies:

```bash
# Track API costs and usage
# Set up alerts for unusual activity
```

### 6. Slack Integration Security

#### Signature Verification

The platform verifies all Slack webhook signatures using HMAC-SHA256. Never disable this in production:

```bash
# REQUIRED in production
SLACK_VERIFY_SIGNATURE=true
SLACK_SIGNING_SECRET=<from-slack-app-settings>
```

#### OAuth Scopes

Grant minimum required OAuth scopes:

**Required Scopes**:
- `chat:write` - Send messages
- `commands` - Respond to slash commands
- `app_mentions:read` - Receive mentions

**Avoid**:
- `*:read` wildcards
- Admin scopes unless required
- File access scopes unless needed

### 7. Container Security

#### Use Non-Root Users

All Dockerfiles should run as non-root:

```dockerfile
# Create non-root user
RUN addgroup -g 1000 appuser && \
    adduser -D -u 1000 -G appuser appuser

# Switch to non-root user
USER appuser
```

#### Minimal Base Images

Use Alpine Linux for smaller attack surface:

```dockerfile
FROM python:3.11-alpine
```

#### Regular Updates

Update base images and dependencies regularly:

```bash
# Update base images
docker-compose pull

# Rebuild with latest dependencies
docker-compose build --no-cache

# Update Python dependencies
pip install --upgrade -r requirements.txt
```

#### Scan for Vulnerabilities

```bash
# Scan images with Trivy
trivy image agentrunner-state-manager:latest

# Scan with Docker Scout
docker scout cves agentrunner-state-manager:latest
```

### 8. Secrets Management (Production)

For production deployments, use a secrets management service:

#### AWS Secrets Manager

```python
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name, region_name="us-east-1"):
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        raise e

# Use in code
POSTGRES_PASSWORD = get_secret('prod/postgres/password')
```

#### HashiCorp Vault

```python
import hvac

client = hvac.Client(url='https://vault.example.com:8200')
client.auth.approle.login(
    role_id=os.environ['VAULT_ROLE_ID'],
    secret_id=os.environ['VAULT_SECRET_ID']
)

secret = client.secrets.kv.v2.read_secret_version(path='prod/postgres')
POSTGRES_PASSWORD = secret['data']['data']['password']
```

#### Docker Secrets

```yaml
# docker-compose.yml
services:
  state-manager:
    secrets:
      - postgres_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password

secrets:
  postgres_password:
    external: true
```

```bash
# Create secret
echo "secure-password" | docker secret create postgres_password -

# Deploy with secrets
docker stack deploy -c docker-compose.yml agentrunner
```

### 9. Network Security

#### Firewall Rules

Only expose necessary ports:

```bash
# Allow only required ports
ufw allow 22/tcp      # SSH
ufw allow 443/tcp     # HTTPS
ufw deny 5432/tcp     # Block external PostgreSQL access
ufw deny 6379/tcp     # Block external Redis access
ufw deny 5672/tcp     # Block external RabbitMQ access
ufw deny 15672/tcp    # Block RabbitMQ management UI
ufw enable
```

#### Internal-Only Services

Keep infrastructure services internal:

```yaml
# docker-compose.yml
services:
  postgres:
    # Don't expose ports to host
    # ports:
    #   - "5432:5432"  # REMOVE THIS
    networks:
      - agent-network  # Internal network only
```

#### Reverse Proxy

Use nginx or Traefik for TLS termination:

```nginx
# nginx.conf
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location / {
        proxy_pass http://agent-orchestrator:8003;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 10. Logging and Monitoring

#### Secure Logging

Don't log sensitive data:

```python
# BAD - Logs password
logger.info(f"Connecting with password: {password}")

# GOOD - Redacts sensitive data
logger.info("Connecting to database")
```

#### Audit Logging

Enable audit logging for security events:

```python
# Log authentication attempts
logger.info(f"API authentication attempt: {user_id}, success={success}")

# Log agent actions
logger.info(f"Agent {agent_name} executed task {task_id}")
```

#### Log Retention

```bash
# Retain logs for compliance
LOG_RETENTION_DAYS=90

# Rotate logs
/var/log/agentrunner/*.log {
    daily
    rotate 90
    compress
    delaycompress
    notifempty
    create 0640 appuser appuser
}
```

### 11. Compliance

#### GDPR/Privacy

If processing personal data:

1. Document data flows in `docs/DATA_FLOW.md`
2. Implement data deletion endpoints
3. Enable encryption at rest
4. Log data access for audit trails

#### SOC 2

For SOC 2 compliance:

1. Enable comprehensive audit logging
2. Implement role-based access control (RBAC)
3. Regular security assessments
4. Incident response procedures
5. Encryption in transit and at rest

## Security Checklist for Production

Before deploying to production, verify:

- [ ] All passwords changed from defaults
- [ ] API keys stored in secrets manager
- [ ] TLS enabled for all services
- [ ] API authentication enabled
- [ ] Rate limiting configured
- [ ] Firewall rules applied
- [ ] Container images scanned for vulnerabilities
- [ ] Non-root users in containers
- [ ] Database backups automated
- [ ] Monitoring and alerting configured
- [ ] Audit logging enabled
- [ ] `.env` file not committed to git
- [ ] Security headers configured (HSTS, CSP, etc.)
- [ ] Regular dependency updates scheduled
- [ ] Incident response plan documented

## Security Updates

Check for security updates regularly:

```bash
# Check for Python package vulnerabilities
pip-audit

# Update dependencies
pip install --upgrade -r requirements.txt

# Update Docker images
docker-compose pull && docker-compose up -d --build
```

## Incident Response

If a security incident occurs:

1. **Contain**: Immediately revoke compromised credentials
2. **Assess**: Determine scope of breach
3. **Eradicate**: Remove attacker access
4. **Recover**: Restore from clean backups
5. **Document**: Record timeline and actions taken
6. **Review**: Update security measures to prevent recurrence

## Contact

For security concerns, contact: [security@example.com]

---

**Last Updated**: 2025-11-18
**Version**: 1.0
