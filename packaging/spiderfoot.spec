%global debug_package %{nil}

Name:           spiderfoot
Version:        %{version}
Release:        1%{?dist}
Summary:        Open source OSINT automation tool for threat intelligence and reconnaissance
License:        GPLv3+
URL:            https://github.com/smicallef/spiderfoot
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  python3-devel, python3-setuptools
Requires:       python3, python3-setuptools

%description
SpiderFoot automates open source intelligence (OSINT) for threat intelligence,
red teaming, and digital footprinting. It helps security professionals and
researchers gather, correlate, and analyze data from hundreds of sources to
discover information about IPs, domains, emails, and more.

%prep
%setup -q

%build
%py3_build

%install
rm -rf %{buildroot}
%py3_install
mkdir -p %{buildroot}%{python3_sitelib}/modules
cp -r modules/* %{buildroot}%{python3_sitelib}/modules/
mkdir -p %{buildroot}%{python3_sitelib}/correlations
cp -r correlations/* %{buildroot}%{python3_sitelib}/correlations/
mkdir -p %{buildroot}%{python3_sitelib}/spiderfoot
cp -r spiderfoot/* %{buildroot}%{python3_sitelib}/spiderfoot/
# Add all sf* and sflib* files from root
cp sf.py %{buildroot}%{python3_sitelib}/
cp sfcli.py %{buildroot}%{python3_sitelib}/
cp sfapi.py %{buildroot}%{python3_sitelib}/
cp sflib.py %{buildroot}%{python3_sitelib}/
cp sfscan.py %{buildroot}%{python3_sitelib}/
cp sfwebui.py %{buildroot}%{python3_sitelib}/
cp sfworkflow.py %{buildroot}%{python3_sitelib}/
cp test_version.py %{buildroot}%{python3_sitelib}/
cp update_version.py %{buildroot}%{python3_sitelib}/
cp version_check_hook.py %{buildroot}%{python3_sitelib}/

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/spiderfoot*
%{python3_sitelib}/modules*
%{python3_sitelib}/correlations*
# Add all sf* and sflib* files from root
%{python3_sitelib}/sf.py
%{python3_sitelib}/sfcli.py
%{python3_sitelib}/sfapi.py
%{python3_sitelib}/sflib.py
%{python3_sitelib}/sfscan.py
%{python3_sitelib}/sfwebui.py
%{python3_sitelib}/sfworkflow.py
%{python3_sitelib}/test_version.py
%{python3_sitelib}/update_version.py
%{python3_sitelib}/version_check_hook.py

%changelog
* Tue Jun 24 2025 SpiderFoot Team <info@spiderfoot.net> - %{version}-1
- Initial RPM release
