# SpiderFoot Code Coverage Improvement Plan

## Current State Analysis
- **Overall Coverage**: 42% (56,978 total statements, 33,108 missed)
- **Critical Infrastructure**: Mixed coverage (24% - 92%)
- **Module Coverage**: Highly variable (0% - 100%)
- **Test Infrastructure**: Good foundation but needs expansion

## Priority Framework

### Tier 1: Critical Infrastructure (Immediate Priority)
**Target: 80%+ coverage within 2 weeks**

#### Core Components
1. **spiderfoot/db.py** - 24% → 80%
   - **Current**: 764 statements, 584 missed
   - **Priority**: CRITICAL - Database operations are core to application
   - **Strategy**: 
     - Mock database connections and operations
     - Test CRUD operations, error handling, connection pooling
     - Focus on data integrity and transaction handling
   
2. **spiderfoot/workspace.py** - 11% → 75%
   - **Current**: 323 statements, 288 missed  
   - **Priority**: HIGH - Workspace management is essential
   - **Strategy**:
     - Test workspace creation, deletion, validation
     - Mock file system operations
     - Test permission and configuration handling

3. **spiderfoot/helpers.py** - 68% → 85%
   - **Current**: 665 statements, 212 missed
   - **Priority**: HIGH - Utility functions used throughout
   - **Strategy**:
     - Focus on uncovered utility functions
     - Test edge cases and error conditions
     - Improve input validation testing

#### API Layer
4. **sfapi.py** - 5% → 70%
   - **Current**: 577 statements, 549 missed
   - **Priority**: CRITICAL - Main API interface
   - **Strategy**:
     - Mock HTTP requests/responses
     - Test all API endpoints systematically
     - Focus on authentication, validation, error handling

5. **sfwebui.py** - 55% → 75%
   - **Current**: 1,431 statements, 647 missed
   - **Priority**: HIGH - Web interface
   - **Strategy**:
     - Test route handlers and form processing
     - Mock template rendering
     - Focus on security and input validation

### Tier 2: Core Application Logic (2-4 weeks)
**Target: 70%+ coverage**

#### Scanning Engine
6. **sfscan.py** - 35% → 70%
   - **Current**: 368 statements, 238 missed
   - **Strategy**: Mock scanning operations, test scan lifecycle

7. **sflib.py** - 36% → 70%
   - **Current**: 851 statements, 541 missed
   - **Strategy**: Test core library functions, configuration management

8. **sfcli.py** - 41% → 70%
   - **Current**: 888 statements, 526 missed
   - **Strategy**: Test CLI argument parsing, command execution

#### Data Processing
9. **spiderfoot/correlation.py** - 59% → 80%
   - **Current**: 540 statements, 221 missed
   - **Strategy**: Test correlation algorithms and pattern matching

10. **spiderfoot/logger.py** - 18% → 75%
    - **Current**: 135 statements, 111 missed
    - **Strategy**: Test logging configuration and output formatting

### Tier 3: Storage Modules (Parallel with Tier 2)
**Target: 85%+ coverage**

#### Current State
- **sfp__stor_db_advanced.py**: 84% (maintain)
- **sfp__stor_db.py**: 61% → 85%
- **sfp__stor_stdout.py**: 28% → 80%
- **sfp__stor_elasticsearch.py**: 16% → 70%

#### Strategy
- Focus on error handling and edge cases
- Test different storage backends
- Validate data persistence and retrieval

### Tier 4: High-Value Data Modules (4-6 weeks)
**Target: 50%+ coverage for critical modules**

#### Selection Criteria (focusing on modules with >40% current coverage)
1. **sfp_webanalytics.py** - 48% → 70%
2. **sfp_criminalip.py** - 77% → 85%
3. **sfp_cloudfront.py** - 77% → 85%
4. **sfp_phone.py** - 77% → 85%
5. **sfp_countryname.py** - 63% → 75%
6. **sfp_bitcoinabuse.py** - 58% → 70%
7. **sfp_bingsearch.py** - 55% → 70%
8. **sfp_googlesearch.py** - 55% → 70%

### Tier 5: Low-Priority Modules (Ongoing)
**Target: 30%+ coverage**
- Focus on modules with <20% coverage
- Implement basic functionality tests
- Prioritize based on actual usage patterns

## Implementation Strategy

### Phase 1: Infrastructure Setup (Week 1)
1. **Enhanced Test Fixtures**
   ```python
   # test/fixtures/
   ├── database_fixtures.py      # DB connection mocks, sample data
   ├── network_fixtures.py       # HTTP response mocks, API fixtures
   ├── filesystem_fixtures.py    # File system mocks, temp directories
   └── event_fixtures.py         # SpiderFootEvent test data
   ```

2. **Mock Infrastructure**
   ```python
   # test/mocks/
   ├── mock_database.py          # Database operation mocks
   ├── mock_network.py           # HTTP request/response mocks
   ├── mock_filesystem.py        # File system operation mocks
   └── mock_modules.py           # Module execution mocks
   ```

3. **Test Utilities**
   ```python
   # test/utils/
   ├── test_helpers.py           # Common test utilities
   ├── coverage_helpers.py       # Coverage measurement tools
   └── assertion_helpers.py      # Custom assertions
   ```

### Phase 2: Core Infrastructure Tests (Week 1-2)

#### Database Testing (db.py)
```python
class TestSpiderFootDb:
    def test_connection_management(self):
        # Test connection creation, pooling, cleanup
    
    def test_crud_operations(self):
        # Test create, read, update, delete operations
    
    def test_transaction_handling(self):
        # Test transaction rollback, commit
    
    def test_error_conditions(self):
        # Test database errors, connection failures
    
    def test_migration_operations(self):
        # Test schema updates, data migration
```

#### API Testing (sfapi.py)
```python
class TestSpiderFootApi:
    def test_authentication(self):
        # Test auth mechanisms, token validation
    
    def test_endpoint_validation(self):
        # Test input validation, parameter checking
    
    def test_response_formatting(self):
        # Test JSON responses, error messages
    
    def test_rate_limiting(self):
        # Test API rate limiting, throttling
```

### Phase 3: Application Logic Tests (Week 2-3)

#### Scanning Engine
```python
class TestSpiderFootScanner:
    def test_scan_lifecycle(self):
        # Test scan initialization, execution, completion
    
    def test_module_loading(self):
        # Test dynamic module loading and validation
    
    def test_event_processing(self):
        # Test event generation and processing pipeline
    
    def test_error_recovery(self):
        # Test error handling and recovery mechanisms
```

### Phase 4: Storage Module Enhancement (Week 3-4)

#### Database Storage Advanced Testing
```python
class TestAdvancedDbStorage:
    def test_connection_pooling(self):
        # Test connection pool management under load
    
    def test_data_integrity(self):
        # Test data consistency and integrity checks
    
    def test_performance_optimization(self):
        # Test query optimization and caching
```

### Phase 5: Data Module Testing (Week 4-6)

#### High-Value Module Template
```python
class TestDataModule:
    def test_module_initialization(self):
        # Test module setup and configuration
    
    def test_data_processing(self):
        # Test data extraction and processing
    
    def test_api_interaction(self):
        # Test external API calls and response handling
    
    def test_error_handling(self):
        # Test various error conditions and recovery
```

## Testing Patterns and Best Practices

### 1. Mock Strategy
```python
# Network mocking
@patch('requests.get')
def test_api_call(self, mock_get):
    mock_get.return_value.json.return_value = {"data": "test"}
    # Test implementation

# Database mocking
@patch('sqlite3.connect')
def test_db_operation(self, mock_connect):
    mock_connect.return_value = Mock()
    # Test implementation
```

### 2. Parameterized Testing
```python
@pytest.mark.parametrize("input_data,expected", [
    ("valid_input", "expected_output"),
    ("edge_case", "edge_result"),
    ("invalid_input", None),
])
def test_data_processing(self, input_data, expected):
    result = process_data(input_data)
    assert result == expected
```

### 3. Integration Test Strategy
```python
class TestIntegration:
    def test_end_to_end_scan(self):
        # Test complete scan workflow
    
    def test_storage_integration(self):
        # Test data flow between components
```

## Coverage Monitoring and Automation

### 1. Coverage Tracking
```bash
# Daily coverage reports
pytest --cov=spiderfoot --cov-report=html --cov-report=term

# Coverage diff tracking
coverage-diff --compare-branch=main --fail-under=80
```

### 2. CI/CD Integration
```yaml
# .github/workflows/coverage.yml
- name: Generate Coverage Report
  run: |
    pytest --cov=spiderfoot --cov-report=xml
    codecov --file=coverage.xml

- name: Coverage Gate
  run: |
    coverage report --fail-under=75
```

### 3. Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
  - id: coverage-check
    name: Coverage Check
    entry: pytest --cov=spiderfoot --cov-fail-under=70
    language: system
```

## Quality Gates

### Coverage Targets by Component
- **Core Infrastructure**: 80% minimum
- **API Layer**: 75% minimum  
- **Storage Modules**: 85% minimum
- **High-Value Data Modules**: 60% minimum
- **Standard Data Modules**: 40% minimum

### Regression Prevention
- No decrease in coverage for existing tested code
- New code requires 80% coverage minimum
- Critical paths require 90% coverage

## Resource Allocation

### Development Time Estimate
- **Week 1**: Infrastructure setup, core db.py testing
- **Week 2**: API layer, workspace.py, helpers.py improvements
- **Week 3**: Scanning engine, correlation testing
- **Week 4**: Storage module enhancement
- **Week 5-6**: High-value data module testing
- **Ongoing**: Low-priority module testing, maintenance

### Success Metrics
- **Week 2**: Overall coverage 50%+
- **Week 4**: Overall coverage 60%+
- **Week 6**: Overall coverage 65%+
- **Month 3**: Overall coverage 70%+

## Risk Mitigation

### Testing Challenges
1. **External API Dependencies**: Use comprehensive mocking
2. **Database Operations**: Use in-memory databases for testing
3. **File System Operations**: Use temporary directories
4. **Network Operations**: Mock all HTTP requests

### Maintenance Strategy
1. **Automated Coverage Monitoring**: Daily reports
2. **Coverage Regression Testing**: Block PRs that decrease coverage
3. **Documentation**: Maintain testing guidelines and examples
4. **Regular Review**: Monthly coverage analysis and strategy updates

## Conclusion

This plan prioritizes critical infrastructure components while establishing a sustainable testing framework. The phased approach ensures immediate impact on code reliability while building long-term testing capabilities. Focus on Tier 1 components will provide the highest ROI, improving overall application stability and maintainability.
