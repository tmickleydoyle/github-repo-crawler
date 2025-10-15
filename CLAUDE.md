# Software Engineering Standards & Best Practices

This document establishes the highest standards for software development in this project. All code must adhere to these principles to ensure maintainability, reliability, and scalability.

---

## Table of Contents

1. [Project Structure & Organization](#project-structure--organization)
2. [Code Quality & Standards](#code-quality--standards)
3. [Type Safety & Static Analysis](#type-safety--static-analysis)
4. [Testing Strategy](#testing-strategy)
5. [Architecture & Design](#architecture--design)
6. [Security & Performance](#security--performance)
7. [Error Handling & Resilience](#error-handling--resilience)
8. [Observability & Monitoring](#observability--monitoring)
9. [Development Workflow](#development-workflow)
10. [Documentation & Deployment](#documentation--deployment)
11. [Python-Specific Guidelines](#python-specific-guidelines)
12. [Code Review Standards](#code-review-standards)
13. [Critical Rules](#critical-rules)

---

## Project Structure & Organization

### Standard Layout
```
project/
├── src/ or package_name/      # Main application code
│   ├── __init__.py
│   ├── domain/                # Domain models and business logic
│   ├── infrastructure/        # External services, DB, API clients
│   ├── api/                   # API endpoints and routes
│   └── config.py              # Configuration management
├── tests/                     # Test suite
│   ├── unit/                  # Fast, isolated tests
│   ├── integration/           # Service integration tests
│   └── e2e/                   # End-to-end scenarios
├── docs/                      # Documentation
├── scripts/                   # Utility scripts
├── migrations/                # Database migrations
├── .github/workflows/         # CI/CD pipelines
├── pyproject.toml            # Modern Python packaging
├── requirements.txt          # Production dependencies
├── requirements-dev.txt      # Development dependencies
└── README.md                 # Project overview
```

### Package Management
- **Use `pyproject.toml`** for modern Python projects (PEP 517/518)
- **Pin exact versions** in production (`==` not `>=`)
- **Use dependency groups**: production, development, testing
- **Virtual environments are mandatory** - never install globally
- **Document all dependencies** with purpose and version rationale

### Module Organization
- **One class per file** for complex classes (>200 lines)
- **Group related functionality** into cohesive modules
- **Clear separation of concerns**: domain, infrastructure, presentation
- **Avoid circular dependencies** - use dependency injection
- **Keep modules focused** - single responsibility principle

---

## Code Quality & Standards

### Formatting & Linting
**Required Tools:**
- **Ruff** for linting and formatting (replaces Black, isort, flake8)
- **MyPy** for static type checking with `--strict` mode
- **Pre-commit hooks** for automated checks

**Configuration:**
```toml
[tool.ruff]
line-length = 88
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP", "B", "A", "C4", "PT"]

[tool.mypy]
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

### Code Style
- **PEP 8 compliance is mandatory**
- **Line length: 88 characters** (Black standard)
- **Docstrings for all public APIs** (Google or NumPy style)
- **Type hints on all functions** (parameters and return values)
- **Meaningful variable names** - no single letters except loop indices
- **Constants in UPPER_CASE** with clear naming

### Naming Conventions
```python
# Classes: PascalCase
class UserRepository:
    pass

# Functions/methods: snake_case
def calculate_total_cost(items: list[Item]) -> Decimal:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRY_ATTEMPTS = 3
DEFAULT_TIMEOUT_SECONDS = 30

# Private: leading underscore
def _internal_helper() -> None:
    pass

# Type variables: PascalCase with T prefix
T = TypeVar('T')
```

---

## Type Safety & Static Analysis

### Type Hints Are Mandatory
```python
# ✅ GOOD: Full type annotations
def process_user(
    user_id: int,
    email: str | None = None,
    metadata: dict[str, Any] | None = None
) -> User:
    ...

# ❌ BAD: No type hints
def process_user(user_id, email=None, metadata=None):
    ...
```

### Use Modern Type Syntax (Python 3.10+)
```python
# ✅ GOOD: Modern union syntax
def get_value() -> int | None:
    ...

# ❌ BAD: Old Optional syntax
from typing import Optional
def get_value() -> Optional[int]:
    ...
```

### Protocol and Abstract Base Classes
```python
from typing import Protocol

class Storable(Protocol):
    """Any object that can be stored."""
    def save(self) -> None: ...
    def delete(self) -> None: ...
```

### Type Guards and Narrowing
```python
from typing import TypeGuard

def is_valid_user(obj: object) -> TypeGuard[User]:
    return isinstance(obj, User) and obj.id > 0
```

---

## Testing Strategy

### Test Coverage Requirements
- **Minimum 80% code coverage** for production code
- **100% coverage** for critical paths (auth, payments, data integrity)
- **No untested public APIs**

### Test Pyramid
```
      /\
     /  \  E2E Tests (5-10%)
    /----\  
   /      \ Integration Tests (20-30%)
  /--------\
 /          \ Unit Tests (60-75%)
```

### Testing Best Practices
```python
# ✅ GOOD: Clear, focused test
def test_user_creation_with_valid_data():
    # Arrange
    email = "user@example.com"
    
    # Act
    user = create_user(email=email)
    
    # Assert
    assert user.email == email
    assert user.id is not None
    assert user.created_at is not None

# ❌ BAD: Multiple concerns in one test
def test_user():
    user = create_user("test@test.com")
    assert user.email
    user.update_email("new@test.com")
    assert user.email == "new@test.com"
    user.delete()
    assert not user.exists()
```

### Test Fixtures & Factories
```python
import pytest
from factory import Factory, Faker

class UserFactory(Factory):
    class Meta:
        model = User
    
    email = Faker('email')
    username = Faker('user_name')

@pytest.fixture
def db_session():
    """Provide a transactional database session."""
    session = create_test_session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
```

### Test Naming
- **Test file naming**: `test_<module_name>.py`
- **Test function naming**: `test_<what>_<condition>_<expected_result>`
- **Examples**:
  - `test_user_creation_with_valid_email_succeeds`
  - `test_order_processing_with_insufficient_funds_raises_error`

---

## Architecture & Design

### SOLID Principles
**Single Responsibility:** Each class has one reason to change
```python
# ✅ GOOD: Single responsibility
class UserRepository:
    def save(self, user: User) -> None: ...
    def find_by_id(self, user_id: int) -> User | None: ...

class UserValidator:
    def validate_email(self, email: str) -> bool: ...
    def validate_password(self, password: str) -> bool: ...
```

**Open/Closed:** Open for extension, closed for modification
```python
# ✅ GOOD: Use Strategy pattern
class PaymentProcessor:
    def __init__(self, strategy: PaymentStrategy):
        self.strategy = strategy
    
    def process(self, amount: Decimal) -> PaymentResult:
        return self.strategy.execute(amount)
```

**Dependency Inversion:** Depend on abstractions, not concretions
```python
# ✅ GOOD: Depend on interface
class OrderService:
    def __init__(self, repo: OrderRepository):  # Interface
        self.repo = repo
```

### Design Patterns to Use

**Repository Pattern** - Data access abstraction
```python
class Repository(Protocol[T]):
    def get(self, id: int) -> T | None: ...
    def save(self, entity: T) -> None: ...
    def delete(self, id: int) -> None: ...
```

**Factory Pattern** - Complex object creation
```python
class UserFactory:
    @staticmethod
    def create_admin(email: str) -> User:
        return User(email=email, role=Role.ADMIN, permissions=ADMIN_PERMS)
```

**Strategy Pattern** - Algorithm selection at runtime
```python
class SearchStrategy(Protocol):
    def generate_queries(self) -> list[Query]: ...
```

### Configuration Management
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    api_key: SecretStr
    max_retries: int = 3
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="forbid"  # Fail on unknown env vars
    )
```

---

## Security & Performance

### Input Validation
```python
from pydantic import BaseModel, EmailStr, constr

class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=100)
    age: int = Field(ge=0, le=120)
```

### Secrets Management
```python
# ✅ GOOD: Use SecretStr
from pydantic import SecretStr

class Config:
    api_key: SecretStr
    
    def get_api_key(self) -> str:
        return self.api_key.get_secret_value()

# ❌ BAD: Plain string secrets
class Config:
    api_key: str = "hardcoded_secret"  # NEVER DO THIS
```

### SQL Injection Prevention
```python
# ✅ GOOD: Use parameterized queries
cursor.execute("SELECT * FROM users WHERE email = ?", (email,))

# ❌ BAD: String formatting
cursor.execute(f"SELECT * FROM users WHERE email = '{email}'")
```

### Performance Optimization
- **Use connection pooling** for databases
- **Implement caching** for expensive operations (Redis, in-memory)
- **Async/await** for I/O-bound operations
- **Batch operations** instead of loops
- **Profile before optimizing** - use `cProfile`, `py-spy`
- **Use appropriate data structures** - sets for membership, dicts for lookups

```python
# ✅ GOOD: Batch database operations
async def save_many(users: list[User]) -> None:
    await db.execute_many(
        "INSERT INTO users VALUES (?)", 
        [(u.id, u.email) for u in users]
    )

# ❌ BAD: Loop with individual saves
for user in users:
    await db.execute("INSERT INTO users VALUES (?)", (user.id, user.email))
```

---

## Error Handling & Resilience

### Exception Hierarchy
```python
class ApplicationError(Exception):
    """Base exception for application errors."""
    pass

class ValidationError(ApplicationError):
    """Input validation failed."""
    pass

class NotFoundError(ApplicationError):
    """Resource not found."""
    pass

class ExternalServiceError(ApplicationError):
    """External service unavailable."""
    pass
```

### Retry Logic
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(ExternalServiceError)
)
async def call_external_api() -> dict:
    ...
```

### Graceful Degradation
```python
async def get_user_recommendations(user_id: int) -> list[Product]:
    try:
        return await recommendation_service.get(user_id)
    except ExternalServiceError:
        logger.warning("Recommendation service unavailable, using fallback")
        return await get_popular_products()
```

---

## Observability & Monitoring

### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# ✅ GOOD: Structured logging
logger.info(
    "user_created",
    user_id=user.id,
    email=user.email,
    duration_ms=duration
)

# ❌ BAD: String formatting
logger.info(f"User {user.id} created with email {user.email}")
```

### Logging Levels
- **DEBUG:** Detailed diagnostic information
- **INFO:** General informational messages
- **WARNING:** Warning messages for recoverable issues
- **ERROR:** Error messages for failures
- **CRITICAL:** Critical failures requiring immediate attention

### Metrics Collection
```python
from prometheus_client import Counter, Histogram

api_requests = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

request_duration = Histogram(
    'request_duration_seconds',
    'Request duration in seconds',
    ['endpoint']
)
```

### Tracing
- **Use correlation IDs** for request tracing
- **Log entry and exit** of critical functions
- **Measure performance** of slow operations
- **Integrate with APM tools** (DataDog, New Relic, Sentry)

---

## Development Workflow

### Git Workflow
**Commit Messages:**
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`

Example:
```
feat(auth): add JWT token refresh mechanism

Implement automatic token refresh when tokens expire.
Tokens are refreshed 5 minutes before expiration.

Closes #123
```

### Branch Strategy
- **main/master:** Production-ready code
- **develop:** Integration branch
- **feature/*:** New features
- **bugfix/*:** Bug fixes
- **hotfix/*:** Emergency production fixes

### Pre-commit Hooks
```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        args: [--strict]
```

### CI/CD Pipeline Requirements
**Every PR must pass:**
1. ✅ Linting (ruff)
2. ✅ Type checking (mypy --strict)
3. ✅ Unit tests (80%+ coverage)
4. ✅ Integration tests
5. ✅ Security scan (bandit, safety)
6. ✅ Dependency vulnerability check

---

## Documentation & Deployment

### Code Documentation
```python
def calculate_discount(
    price: Decimal,
    discount_rate: float,
    max_discount: Decimal | None = None
) -> Decimal:
    """Calculate the discounted price.
    
    Args:
        price: Original price before discount
        discount_rate: Discount percentage (0.0 to 1.0)
        max_discount: Maximum discount amount allowed
    
    Returns:
        Final price after applying discount
    
    Raises:
        ValueError: If discount_rate is outside valid range
    
    Examples:
        >>> calculate_discount(Decimal("100"), 0.1)
        Decimal("90.00")
        >>> calculate_discount(Decimal("100"), 0.2, max_discount=Decimal("15"))
        Decimal("85.00")
    """
    if not 0 <= discount_rate <= 1:
        raise ValueError("Discount rate must be between 0 and 1")
    
    discount = price * Decimal(str(discount_rate))
    if max_discount and discount > max_discount:
        discount = max_discount
    
    return price - discount
```

### README Requirements
Every project must have:
- **Project description** and purpose
- **Quick start guide** (< 5 minutes to run)
- **Installation instructions** (step-by-step)
- **Configuration** (all environment variables documented)
- **Usage examples** with code snippets
- **API documentation** link
- **Contributing guidelines**
- **License information**

### Docker Best Practices
```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder

WORKDIR /app
COPY pyproject.toml requirements.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app
COPY --from=builder /root/.local /home/appuser/.local
COPY . .

USER appuser
ENV PATH=/home/appuser/.local/bin:$PATH

CMD ["python", "-m", "app.main"]
```

---

## Python-Specific Guidelines

### Async/Await Best Practices
```python
# ✅ GOOD: Gather concurrent tasks
results = await asyncio.gather(
    fetch_user(1),
    fetch_user(2),
    fetch_user(3),
    return_exceptions=True
)

# ❌ BAD: Sequential awaits
result1 = await fetch_user(1)
result2 = await fetch_user(2)
result3 = await fetch_user(3)
```

### Context Managers
```python
# ✅ GOOD: Always use context managers for resources
async with GitHubClient() as client:
    data = await client.fetch()

# ❌ BAD: Manual resource management
client = GitHubClient()
try:
    data = await client.fetch()
finally:
    await client.close()
```

### Dataclasses and Pydantic
```python
from dataclasses import dataclass
from pydantic import BaseModel

# Use dataclasses for internal models
@dataclass(frozen=True)
class User:
    id: int
    email: str

# Use Pydantic for API validation
class UserCreate(BaseModel):
    email: EmailStr
    password: str
```

### Avoid Common Pitfalls
```python
# ❌ BAD: Mutable default arguments
def add_item(item, items=[]):  # Bug: shared list
    items.append(item)
    return items

# ✅ GOOD: Use None as default
def add_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

---

## Code Review Standards

### Reviewer Checklist
- [ ] Code follows PEP 8 and project standards
- [ ] All functions have type hints
- [ ] Tests cover new functionality (80%+ coverage)
- [ ] No hardcoded secrets or credentials
- [ ] Error handling is appropriate
- [ ] Logging is meaningful and structured
- [ ] Documentation is updated
- [ ] No dead code or unused imports
- [ ] Performance implications considered
- [ ] Security implications reviewed

### Review Comments
```python
# ✅ GOOD: Constructive feedback
"""
Consider using a set instead of a list for `seen_ids` to improve 
lookup performance from O(n) to O(1). With large datasets, this 
could significantly reduce processing time.

Suggested change:
- seen_ids: list[int] = []
+ seen_ids: set[int] = set()
"""

# ❌ BAD: Unconstructive
"""
This is slow.
"""
```

### PR Size Guidelines
- **Small PRs:** < 200 lines (preferred)
- **Medium PRs:** 200-400 lines (acceptable)
- **Large PRs:** > 400 lines (break into smaller PRs)

---

## Critical Rules

### Absolute Requirements

1. **NO DEAD CODE** - Remove unused functions, imports, and commented code
2. **NO UNUSED IMPORTS** - Every import must be used
3. **NO HARDCODED SECRETS** - Use environment variables or secret management
4. **TYPE HINTS EVERYWHERE** - All functions must have complete type annotations
5. **TESTS ARE MANDATORY** - No production code without tests (80%+ coverage)
6. **CODE QUALITY CHECKS MUST PASS** - Ruff, MyPy, and tests before merge
7. **MEANINGFUL NAMES** - No single-letter variables except loop indices
8. **CENTRALIZE LOGIC** - DRY principle - don't repeat yourself
9. **HANDLE ERRORS PROPERLY** - No bare `except:` clauses
10. **LOG MEANINGFULLY** - Use structured logging with context

### Code Smells to Avoid

❌ **God Objects** - Classes with too many responsibilities
❌ **Long Functions** - Functions > 50 lines (consider breaking up)
❌ **Deep Nesting** - More than 3 levels of indentation
❌ **Magic Numbers** - Use named constants
❌ **Global State** - Avoid global variables
❌ **Tight Coupling** - Use dependency injection
❌ **Premature Optimization** - Profile first, optimize later

### Maintenance Philosophy

> **"Code is read 10x more than it's written. Optimize for readability."**

- Write code that junior engineers can understand and maintain
- Prefer explicit over clever
- Centralize common logic
- Document complex algorithms
- Keep functions small and focused
- Use meaningful variable names
- Add comments for "why" not "what"

---

## Conclusion

These standards ensure code quality, maintainability, and scalability. **All code merged to main must meet these standards without exception.**

For questions or clarifications, refer to:
- Python Style Guide: [PEP 8](https://peps.python.org/pep-0008/)
- Type Hints: [PEP 484](https://peps.python.org/pep-0484/)
- Clean Code: Robert C. Martin
- Design Patterns: Gang of Four

**Remember:** Good code is not just working code - it's maintainable, testable, and understandable code.
