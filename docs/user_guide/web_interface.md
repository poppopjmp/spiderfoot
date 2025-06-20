# Web Interface Guide

The SpiderFoot web interface provides an intuitive and powerful way to manage scans, explore results, and generate reports. This guide covers all aspects of using the web interface effectively.

## Getting Started

### Accessing the Web Interface

1. **Start SpiderFoot**:
   ```bash
   python sf.py -l 127.0.0.1:5001
   ```

2. **Open Browser**: Navigate to `http://127.0.0.1:5001`

3. **Login** (if authentication is enabled):
   - Default username: `admin`
   - Default password: `spiderfoot`

### Interface Overview

The web interface consists of several main sections:

#### Navigation Bar
- **Home**: Dashboard and scan overview
- **New Scan**: Start individual scans
- **Workspaces**: Manage multi-target projects (new feature)
- **Settings**: Configure modules and global settings
- **Documentation**: Access help and guides

#### Dashboard
- Recent scan activity
- System status and performance metrics
- Quick access to common functions
- Workspace summary (if workspaces are enabled)

## Traditional Scanning

### Starting a New Scan

1. **Click "New Scan"** in the navigation
2. **Configure Scan Parameters**:
   - **Scan Name**: Descriptive name for the scan
   - **Target**: Enter your target (domain, IP, email, etc.)
   - **Target Type**: Select appropriate type from dropdown
   - **Modules**: Choose which modules to run

3. **Module Selection**:
   - **Use Case**: Select pre-configured module sets
   - **By Category**: Choose from organized module categories
   - **Custom**: Manual module selection

4. **Advanced Options** (optional):
   - **Thread Count**: Number of concurrent threads
   - **Timeout**: Module execution timeout
   - **Custom Options**: Module-specific settings

5. **Start Scan**: Click "Run Scan Now"

### Monitoring Scan Progress

#### Real-time Updates
- **Progress Bar**: Shows overall completion percentage
- **Module Status**: Individual module progress and status
- **Event Counter**: Number of events discovered
- **Time Elapsed**: Current scan duration

#### Status Indicators
- **STARTING**: Scan initialization in progress
- **RUNNING**: Active data collection
- **FINISHED**: Scan completed successfully
- **ABORTED**: Scan stopped by user
- **ERROR-FAILED**: Scan failed due to error

### Viewing Scan Results

#### Browse Tab
- **Event Types**: Filter by event categories
- **Event Data**: Detailed information for each finding
- **Risk Assessment**: Color-coded risk levels
- **Source Module**: Which module discovered the event

#### Graph Tab
- **Visual Relationships**: Interactive graph of discovered entities
- **Entity Types**: Different node types for various data
- **Filtering**: Show/hide specific event types
- **Export**: Save graph visualizations

#### Export Tab
- **Format Selection**: CSV, JSON, GEXF options
- **Data Filtering**: Choose specific event types
- **Custom Exports**: Configure export parameters

## Workspace Management

### Creating Workspaces

1. **Navigate to Workspaces**: Click "Workspaces" in navigation
2. **Create New Workspace**:
   - **Name**: Descriptive workspace name
   - **Description**: Optional detailed description
   - **Settings**: Configure workspace-specific options

3. **Add Targets**:
   - **Single Target**: Add individual targets manually
   - **Bulk Import**: Upload CSV file with multiple targets
   - **Target Types**: Mix different target types in same workspace

### Managing Targets

#### Target List View
- **Target Information**: Type, value, metadata
- **Status Indicators**: Scan status for each target
- **Actions**: Edit, delete, or scan individual targets
- **Bulk Operations**: Select multiple targets for operations

#### Target Metadata
- **Priority**: High, medium, low priority levels
- **Environment**: Production, staging, development tags
- **Owner**: Responsible team or individual
- **Custom Tags**: User-defined labels and categories

### Multi-Target Scanning

#### Scan Configuration
1. **Select Targets**: Choose which targets to include
2. **Module Selection**: Pick appropriate modules for all targets
3. **Scan Options**:
   - **Concurrent Scans**: Number of parallel scans
   - **Resource Limits**: Memory and CPU constraints
   - **Scheduling**: Immediate or scheduled execution

#### Progress Monitoring
- **Scan Grid**: Matrix view of target vs. scan status
- **Overall Progress**: Workspace-level completion tracking
- **Individual Status**: Per-target progress indicators
- **Resource Usage**: System performance metrics

### Correlation Analysis

#### Running Correlations
1. **Complete Scans**: Ensure all target scans are finished
2. **Start Correlation**: Click "Run Correlation Analysis"
3. **Rule Selection**: Choose specific correlation rules or run all
4. **Progress Tracking**: Monitor correlation processing

#### Viewing Correlation Results
- **Pattern Summary**: Overview of discovered patterns
- **Detailed Findings**: Specific correlation instances
- **Risk Assessment**: Impact and confidence ratings
- **Affected Targets**: Which targets are involved

### CTI Report Generation

#### Report Configuration
1. **Select Report Type**:
   - **Threat Assessment**: Comprehensive threat analysis
   - **Infrastructure Analysis**: Security posture evaluation
   - **Attack Surface**: External exposure mapping

2. **Customization Options**:
   - **Custom Prompts**: Specific analysis focus
   - **Data Filtering**: Include/exclude specific findings
   - **Format Selection**: JSON, HTML, PDF options

#### Report Management
- **Report List**: All generated reports for workspace
- **Status Tracking**: Generation progress and completion
- **Export Options**: Download in various formats
- **Sharing**: Generate shareable report links

## Settings and Configuration

### Global Settings

#### System Configuration
- **Web Interface**: Port, authentication settings
- **Database**: Location and optimization options
- **Logging**: Log levels and file locations
- **Performance**: Thread limits and timeout settings

#### Network Configuration
- **Proxy Settings**: HTTP/HTTPS proxy configuration
- **DNS Settings**: Custom DNS servers
- **User Agents**: Browser identification strings
- **Rate Limiting**: Request throttling options

### Module Configuration

#### API Keys
Configure API keys for external services:
- **VirusTotal**: Malware and threat intelligence
- **Shodan**: Internet-connected device search
- **Hunter.io**: Email discovery and verification
- **SecurityTrails**: DNS and domain intelligence

#### Module Settings
- **Timeouts**: Per-module timeout values
- **Delays**: Rate limiting between requests
- **Verification**: Enable/disable hostname verification
- **Custom Options**: Module-specific parameters

### User Management

#### Authentication
- **Enable/Disable**: Toggle web authentication
- **Credentials**: Set username and password
- **Session Timeout**: Automatic logout timing
- **Security Options**: HTTPS, secure cookies

#### Access Control
- **IP Restrictions**: Limit access by IP address
- **Role-Based Access**: Different permission levels
- **Audit Logging**: Track user actions
- **Session Management**: Active session monitoring

## Data Management

### Database Operations

#### Maintenance
- **Database Size**: Monitor storage usage
- **Optimization**: Periodic database cleanup
- **Backup**: Export database for backup
- **Restoration**: Import previous database state

#### Data Retention
- **Scan Retention**: How long to keep scan data
- **Automatic Cleanup**: Scheduled data removal
- **Archive Options**: Long-term storage solutions
- **Compliance**: Data retention for regulatory requirements

### Import/Export

#### Scan Data
- **Export Scans**: Download scan results
- **Import Previous**: Load historical scan data
- **Format Options**: Multiple export formats
- **Selective Export**: Choose specific data types

#### Configuration
- **Settings Export**: Backup configuration
- **Settings Import**: Restore configuration
- **API Key Management**: Secure key storage
- **Module Configuration**: Backup module settings

## Visualization and Analysis

### Graph Visualization

#### Interactive Features
- **Pan and Zoom**: Navigate large graphs
- **Node Filtering**: Show/hide specific types
- **Layout Options**: Different graph arrangements
- **Search**: Find specific nodes or connections

#### Customization
- **Color Coding**: Risk-based node coloring
- **Size Scaling**: Importance-based node sizing
- **Label Options**: Show/hide node labels
- **Export**: Save graphs as images

### Data Tables

#### Sorting and Filtering
- **Column Sorting**: Sort by any column
- **Search Filter**: Text-based filtering
- **Date Ranges**: Time-based filtering
- **Risk Levels**: Filter by risk assessment

#### Export Options
- **CSV Export**: Spreadsheet-compatible format
- **JSON Export**: Structured data format
- **Filtered Exports**: Export only visible data
- **Custom Columns**: Select specific data fields

## Performance and Troubleshooting

### Performance Monitoring

#### System Metrics
- **CPU Usage**: Processor utilization
- **Memory Usage**: RAM consumption
- **Disk Space**: Storage availability
- **Network Activity**: Bandwidth utilization

#### Scan Performance
- **Execution Time**: How long scans take
- **Event Rate**: Events discovered per minute
- **Module Performance**: Individual module speed
- **Resource Bottlenecks**: Identify performance issues

### Common Issues

#### Slow Performance
1. **Reduce Thread Count**: Lower concurrent operations
2. **Increase Timeouts**: Allow more time for operations
3. **Optimize Database**: Run database maintenance
4. **Check Resources**: Monitor system resources

#### Module Failures
1. **Check API Keys**: Verify external service credentials
2. **Network Connectivity**: Test internet connection
3. **Module Logs**: Review error messages
4. **Update Modules**: Ensure latest versions

#### Interface Issues
1. **Browser Compatibility**: Use supported browsers
2. **Clear Cache**: Clear browser cache and cookies
3. **Check JavaScript**: Ensure JavaScript is enabled
4. **Network Issues**: Verify connectivity to SpiderFoot

### Debugging Tools

#### Log Analysis
- **System Logs**: SpiderFoot application logs
- **Module Logs**: Individual module error logs
- **Access Logs**: Web interface access logs
- **Debug Mode**: Enable verbose logging

#### Diagnostic Tools
- **Module Test**: Test individual modules
- **Connectivity Test**: Verify network connectivity
- **Database Check**: Validate database integrity
- **Configuration Validation**: Check settings

## Mobile and Remote Access

### Mobile Interface

#### Responsive Design
- **Mobile Layout**: Optimized for small screens
- **Touch Navigation**: Touch-friendly interface
- **Key Features**: Core functionality on mobile
- **Performance**: Lightweight mobile experience

#### Feature Limitations
- **Graph Visualization**: Limited on small screens
- **File Operations**: Reduced file handling
- **Complex Configuration**: Use desktop for setup
- **Performance**: Slower on mobile devices

### Remote Access

#### Security Considerations
- **HTTPS**: Use secure connections for remote access
- **VPN**: Connect through secure tunnels
- **Authentication**: Strong passwords and 2FA
- **IP Restrictions**: Limit access by location

#### Configuration
- **Bind Address**: Configure for external access
- **Firewall Rules**: Open necessary ports
- **SSL Certificates**: Set up HTTPS encryption
- **Domain Names**: Use proper domain configuration

## Best Practices

### Security
1. **Change Default Credentials**: Use strong, unique passwords
2. **Enable HTTPS**: Encrypt web traffic
3. **Restrict Access**: Limit access to authorized users
4. **Regular Updates**: Keep SpiderFoot updated
5. **Monitor Logs**: Review access and error logs

### Performance
1. **Monitor Resources**: Watch CPU and memory usage
2. **Optimize Database**: Regular maintenance
3. **Manage Data**: Clean up old scans regularly
4. **Network Tuning**: Optimize network settings
5. **Module Selection**: Use appropriate modules

### Workflow
1. **Organize Workspaces**: Group related assessments
2. **Document Scans**: Use descriptive names and notes
3. **Regular Correlation**: Run correlation analysis frequently
4. **Export Results**: Back up important findings
5. **Review Settings**: Periodically review configuration

Ready to explore advanced features? Check out the [CLI Usage Guide](cli_usage.md) or learn about [Module Development](../developer/module_development.md).
