# Web Interface Guide

The SpiderFoot web interface provides an intuitive and powerful way to manage scans, explore results, and generate reports. This guide covers both traditional scanning and the advanced workspace functionality.

## Getting Started

### Accessing the Web Interface

1. **Start SpiderFoot**: `python sf.py -l 127.0.0.1:5001`
2. **Open Browser**: Navigate to `http://127.0.0.1:5001`
3. **Login** (if authentication is enabled)

### Interface Overview

The web interface consists of several main sections:

#### Navigation Bar
- **Home**: Dashboard and scan overview
- **New Scan**: Start individual scans
- **Workspaces**: Manage multi-target projects (if workflow enabled)
- **Settings**: Configure modules and global settings
- **Documentation**: Access help and guides

## Traditional Scanning

### Starting a New Scan

1. **Click "New Scan"** in the navigation
2. **Configure Scan Parameters**:
   - **Scan Name**: Descriptive name for the scan
   - **Target**: Enter your target (domain, IP, email, etc.)
   - **Target Type**: Select appropriate type from dropdown
   - **Modules**: Choose which modules to run

3. **Module Selection Options**:
   - **Use Case Templates**: Pre-configured module sets for common scenarios
   - **By Category**: Choose from organized module categories
   - **All Modules**: Run comprehensive scan with all available modules
   - **Custom Selection**: Manual module selection with filters

4. **Advanced Options**:
   - **Scan Timeout**: Maximum scan duration
   - **Thread Count**: Number of concurrent modules
   - **Recursion Depth**: How deep to follow discovered entities
   - **Module-Specific Settings**: Individual module configuration

5. **Start Scan**: Click "Run Scan Now"

### Monitoring Scan Progress

#### Real-time Updates
- **Progress Bar**: Shows overall completion percentage
- **Module Status**: Individual module progress and status indicators
- **Event Counter**: Number of events discovered in real-time
- **Time Elapsed**: Current scan duration
- **Active Modules**: Which modules are currently running

#### Scan Controls
- **Pause/Resume**: Temporarily stop and restart scans
- **Stop Scan**: Terminate scan early
- **Refresh**: Manual update of scan status
- **Export Progress**: Download partial results

### Viewing Scan Results

#### Results Overview
- **Summary Statistics**: Total events, unique entities, risk levels
- **Event Timeline**: Chronological discovery of events
- **Target Tree**: Hierarchical view of discovered entities
- **Risk Assessment**: Categorized findings by severity

#### Result Exploration
- **Event Browser**: Paginated view of all discovered events
- **Search and Filter**: Find specific events or entity types
- **Entity Graph**: Visual representation of relationships
- **Correlation View**: Related events and patterns

#### Data Export
- **Multiple Formats**: CSV, JSON, GEXF, XML
- **Filtered Export**: Export specific event types or entities
- **Report Generation**: Formatted reports for stakeholders
- **API Export**: Programmatic access to scan data

## Workspace Management

*Note: Workspace functionality is available when workflow features are enabled.*

### Creating Workspaces

1. **Navigate to Workspaces**: Click "Workspaces" in navigation
2. **Create New Workspace**:
   - **Workspace Name**: Descriptive name for the project
   - **Description**: Optional detailed description
   - **Metadata**: Additional project information

### Managing Targets

#### Adding Targets
- **Single Target**: Add individual targets with type selection
- **Bulk Import**: Upload CSV/JSON files with multiple targets
- **Target Metadata**: Associate additional information with targets

#### Target Organization
- **Target List**: View all targets in workspace
- **Target Types**: Group targets by type (domains, IPs, emails, etc.)
- **Target Status**: Track scanning progress per target
- **Priority Levels**: Assign importance rankings

### Multi-Target Scanning

#### Scan Configuration
- **Target Selection**: Choose which targets to scan
- **Module Selection**: Apply same modules across targets
- **Concurrent Scanning**: Configure parallel scan execution
- **Progress Monitoring**: Track multiple scans simultaneously

#### Workflow Management
- **Scan Queuing**: Automatic scheduling of target scans
- **Resource Management**: CPU and memory usage monitoring
- **Error Handling**: Automatic retry and failure tracking
- **Completion Notifications**: Alerts when scans finish

### Cross-Correlation Analysis

#### Correlation Rules
- **Shared Infrastructure**: Find common hosting, DNS, certificates
- **Similar Technologies**: Identify technology stack patterns
- **Threat Indicators**: Cross-reference threat intelligence
- **Custom Rules**: Define organization-specific correlation logic

#### Correlation Results
- **Relationship Mapping**: Visual display of cross-target connections
- **Risk Scoring**: Weighted correlation confidence levels
- **Pattern Detection**: Automated identification of commonalities
- **Export Options**: Share correlation findings

### CTI Report Generation

*Note: Requires MCP (Model Context Protocol) integration*

#### Report Types
- **Threat Assessment**: Comprehensive security analysis
- **Executive Summary**: High-level findings for management
- **Technical Report**: Detailed technical findings
- **Custom Reports**: User-defined report templates

#### Report Features
- **Automated Analysis**: AI-powered threat analysis
- **Multiple Formats**: JSON, HTML, PDF, DOCX
- **Template Customization**: Organization-specific formatting
- **Export and Sharing**: Easy distribution of reports

## Settings and Configuration

### Global Settings

#### Database Settings
- **Database Path**: Location of SpiderFoot database
- **Backup Configuration**: Automatic backup settings
- **Performance Tuning**: Database optimization options

#### Web Interface Settings
- **Port Configuration**: Change web server port
- **Authentication**: Enable/disable login requirements
- **Session Management**: Timeout and security settings
- **Theme Options**: Interface appearance customization

### Module Configuration

#### API Keys Management
- **Service Integration**: Configure external API services
- **Key Validation**: Test API key functionality
- **Usage Monitoring**: Track API quota consumption
- **Security Storage**: Encrypted storage of sensitive keys

#### Module Settings
- **Enable/Disable Modules**: Control which modules are available
- **Module-Specific Options**: Individual module configuration
- **Timeout Settings**: Per-module execution limits
- **Output Filtering**: Control what data modules collect

### Performance Settings

#### Scan Optimization
- **Thread Management**: Configure concurrent execution
- **Memory Limits**: Set resource usage boundaries
- **Timeout Configuration**: Global and per-module timeouts
- **Queue Management**: Control scan scheduling

#### Database Optimization
- **Query Performance**: Optimize database queries
- **Storage Management**: Control data retention
- **Index Configuration**: Improve search performance
- **Cleanup Policies**: Automatic data maintenance

## Troubleshooting

### Common Issues

#### Connection Problems
- **Port Conflicts**: Change default port if 5001 is in use
- **Firewall Issues**: Ensure port is accessible
- **Browser Compatibility**: Modern browser requirements

#### Performance Issues
- **Memory Usage**: Monitor and adjust memory limits
- **Slow Scans**: Optimize module selection and threading
- **Database Performance**: Regular maintenance and cleanup

#### Module Errors
- **API Failures**: Check API key configuration
- **Network Issues**: Verify internet connectivity
- **Rate Limiting**: Configure appropriate delays

### Getting Help

#### Documentation
- **In-App Help**: Contextual help within the interface
- **Module Documentation**: Detailed module information
- **API Reference**: REST API documentation
- **Video Tutorials**: Step-by-step guidance

#### Community Support
- **GitHub Issues**: Report bugs and feature requests
- **Discord Community**: Real-time support and discussion
- **Forums**: Community-driven help and tips

## Advanced Features

### REST API Integration

#### API Access
- **Programmatic Control**: Automate scans via API
- **Data Export**: Bulk data extraction
- **Integration**: Connect with other security tools
- **Monitoring**: Automated scan management

### Workflow Automation

#### Batch Operations
- **Scheduled Scans**: Automated recurring scans
- **Bulk Processing**: Handle large target lists
- **Result Processing**: Automated analysis pipelines
- **Reporting Automation**: Scheduled report generation

### Custom Development

#### Module Development
- **Custom Modules**: Create organization-specific modules
- **Integration Modules**: Connect with internal systems
- **Testing Framework**: Validate custom modules
- **Deployment**: Deploy custom modules safely

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

## Workspace Management

### Creating Workspaces

1. **Navigate to Workspaces**: Click "Workspaces" in navigation
2. **Create New Workspace**:
   - **Name**: Descriptive workspace name
   - **Description**: Optional detailed description
   - **Settings**: Configure workspace-specific options

### Managing Targets

#### Target List View
- **Target Information**: Type, value, metadata
- **Status Indicators**: Scan status for each target
- **Actions**: Edit, delete, or scan individual targets
- **Bulk Operations**: Select multiple targets for operations

### Multi-Target Scanning

#### Scan Configuration
1. **Select Targets**: Choose which targets to include
2. **Module Selection**: Pick appropriate modules for all targets
3. **Scan Options**: Configure concurrent scans and resource limits

#### Progress Monitoring
- **Scan Grid**: Matrix view of target vs. scan status
- **Overall Progress**: Workspace-level completion tracking
- **Individual Status**: Per-target progress indicators

## Settings and Configuration

### Global Settings

#### System Configuration
- **Web Interface**: Port, authentication settings
- **Database**: Location and optimization options
- **Logging**: Log levels and file locations
- **Performance**: Thread limits and timeout settings

### Module Configuration

#### API Keys
Configure API keys for external services:
- **VirusTotal**: Malware and threat intelligence
- **Shodan**: Internet-connected device search
- **Hunter.io**: Email discovery and verification

For detailed configuration options, see the [Configuration Guide](configuration.md).

## Best Practices

### Security
1. **Change default credentials** for web interface
2. **Use HTTPS** in production environments
3. **Restrict access** to trusted networks
4. **Regular updates** for latest security fixes

### Performance
1. **Monitor resources** during large scans
2. **Optimize module selection** for your needs
3. **Regular database maintenance** for performance
4. **Configure appropriate timeouts** for modules

Ready to explore more? Check out [CLI Usage](user_guide/cli_usage.md) or [Workspace Integration](WORKSPACE_INTEGRATION_COMPLETE.md).
