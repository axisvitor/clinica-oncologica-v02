**Documentation Index**

This guide provides quick access to all documentation resources for the Hormonia Backend.

---

## 📚 Essential Documentation (Read First!)

### 1. Database Migrations

**START HERE:** `docs/database/DATA_MIGRATION_STRATEGY.md`
- Complete migration guide (1500+ LOC)
- Zero-downtime patterns
- Production deployment procedures
- Rollback strategies

**TEMPLATE:** `alembic/MIGRATION_TEMPLATE.py`
- Use this template for all new migrations
- Comprehensive documentation structure
- Pre/post deployment checklists

**TESTING:** `scripts/test_migration_prod_dump.sh`
```bash
# Test migration on production data dump
./scripts/test_migration_prod_dump.sh 018b_backfill_email_verified
```

### 2. API Documentation

**EXAMPLES:** `docs/api/EXAMPLES.md`
- 30+ API request/response examples
- Authentication flows
- Error handling
- Pagination patterns

**INTERACTIVE DOCS:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

### 3. Environment Configuration

**DEVELOPMENT:** `.env.example`
- Copy to `.env` and update values
- 50+ variables documented
- Inline comments for each variable

**PRODUCTION:** `.env.production.example`
- Production-specific template
- Security checklists
- SSL/TLS requirements

**VALIDATION:** `scripts/validate_env.py`
```bash
# Validate environment variables
python scripts/validate_env.py

# Strict validation for production
python scripts/validate_env.py --strict --environment=production
```

### 4. API Testing (Postman)

**COLLECTION:** `postman/Backend_Hormonia_API.postman_collection.json`
- 50+ API requests organized by functionality
- Automated test scripts
- Variable extraction

**GENERATE COLLECTION:**
```bash
# Regenerate Postman collection from OpenAPI
cd backend-hormonia
python scripts/generate_postman_collection.py
```

**IMPORT TO POSTMAN:**
1. Open Postman
2. Import `Backend_Hormonia_API.postman_collection.json`
3. Import `Development.postman_environment.json`
4. Run Authentication > Login
5. JWT token auto-saved to environment

---

## 🎯 Quick Tasks

### Create a New Migration

```bash
# 1. Create migration file
cd backend-hormonia
alembic revision -m "add_new_feature"

# 2. Copy template structure from alembic/MIGRATION_TEMPLATE.py

# 3. Fill in documentation sections:
#    - WHY: Business justification
#    - WHAT: Technical changes
#    - IMPACT: Performance metrics
#    - BENCHMARK: Test results
#    - ROLLBACK: Safety assessment
#    - RELATED: Links to issues/PRs

# 4. Test on production data dump
./scripts/test_migration_prod_dump.sh

# 5. Deploy to staging
alembic upgrade head
```

### Test API Endpoints

```bash
# 1. Generate/Update Postman collection
cd backend-hormonia
python scripts/generate_postman_collection.py

# 2. Import to Postman
# - Open Postman
# - Import postman/Backend_Hormonia_API.postman_collection.json
# - Import postman/Development.postman_environment.json

# 3. Run tests
# - Select Development environment
# - Run Authentication > Login
# - Start testing endpoints
```

### Validate Environment

```bash
# Development validation
python scripts/validate_env.py

# Production validation (strict mode)
python scripts/validate_env.py --strict --environment=production

# Fix any critical errors before deployment
```

### Run CI/CD API Tests

```bash
# Tests run automatically on:
# - Push to main/develop/staging
# - Pull requests
# - Daily at 2 AM UTC

# Manual run:
# - Go to Actions tab in GitHub
# - Select "Postman API Tests" workflow
# - Click "Run workflow"
```

---

## 📂 Documentation Structure

```
backend-hormonia/
├── docs/
│
├── .env.example                            # Development template
├── .env.production.example                 # Production template
└── .env.test.example                       # Testing template
```

---

## 🔗 Quick Links

| Resource | Path | Description |
|----------|------|-------------|
| **Migration Guide** | `docs/database/DATA_MIGRATION_STRATEGY.md` | Complete migration strategy |
| **Migration Template** | `alembic/MIGRATION_TEMPLATE.py` | Template for new migrations |
| **API Examples** | `docs/api/EXAMPLES.md` | Request/response examples |
| **Environment Guide** | `docs/deployment/README.md` | Deployment & Env Guide |
| **Postman Collection** | `postman/Backend_Hormonia_API.postman_collection.json` | API test collection |
| **Swagger UI** | http://localhost:8000/docs | Interactive API docs |

---

## 💡 Best Practices

### Migrations

✅ **DO:**
- Use `alembic/MIGRATION_TEMPLATE.py` for all new migrations
- Test on production data dumps before deployment
- Document WHY, WHAT, IMPACT, BENCHMARK, ROLLBACK
- Use CONCURRENTLY for indexes on large tables
- Batch large data transformations (1000 rows/batch)

❌ **DON'T:**
- Skip migration documentation
- Deploy untested migrations to production
- Use table locks on large tables
- Add NOT NULL without backfilling data

### API Development

✅ **DO:**
- Add request/response examples to all endpoints
- Use Pydantic schema examples
- Test with Postman collection
- Document error responses
- Follow pagination patterns

❌ **DON'T:**
- Skip API documentation
- Break backward compatibility
- Return inconsistent error formats
- Forget to update Postman collection

### Environment Configuration

✅ **DO:**
- Use appropriate .env template (dev/prod/test)
- Validate environment before deployment
- Use SSL/TLS in production
- Rotate secrets regularly
- Document all variables

❌ **DON'T:**
- Commit .env files to git
- Use development secrets in production
- Skip environment validation
- Use wildcard CORS in production

---

## 🆘 Troubleshooting

### Migration Failed

```bash
# Check current migration state
alembic current

# Check migration history
alembic history

# Downgrade one step
alembic downgrade -1

# Test migration on prod dump
./scripts/test_migration_prod_dump.sh
```

### Environment Validation Failed

```bash
# Run validation with detailed output
python scripts/validate_env.py --environment=development

# Check specific variable
echo $DATABASE_URL

# Verify .env file exists
ls -la .env
```

### Postman Collection Out of Date

```bash
# Regenerate collection from OpenAPI
cd backend-hormonia
python scripts/generate_postman_collection.py

# Reimport to Postman
# - Delete old collection
# - Import new collection
# - Select environment
```

### API Tests Failing in CI/CD

```bash
# Check GitHub Actions logs
# - Go to Actions tab
# - Select failed workflow
# - Review Newman test output

# Run tests locally
cd backend-hormonia/postman
newman run Backend_Hormonia_API.postman_collection.json \
  -e Development.postman_environment.json \
  --env-var "base_url=http://localhost:8000"
```

---

## 📞 Get Help

1. **Documentation Issues:** Check `docs/` directory
2. **Migration Issues:** See `docs/database/DATA_MIGRATION_STRATEGY.md`
3. **API Issues:** See `docs/api/EXAMPLES.md`
4. **Environment Issues:** Run `python scripts/validate_env.py`
5. **Postman Issues:** See `postman/README.md`

---

**Happy coding! 🚀**
