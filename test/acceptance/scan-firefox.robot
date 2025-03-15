***Settings***
Library           SeleniumLibrary
Library           OperatingSystem
Library           Collections
Test Teardown     Run Keyword If Test Failed    Capture Failure Screenshot
Resource          variables.robot  # Externalize variables

***Variables***
${GECKODRIVER_PATH}    /usr/local/bin/geckodriver
${FIREFOX_BINARY_PATH}    /usr/bin/firefox  # Add path to Firefox binary

***Keywords***
Capture Failure Screenshot
    Capture Page Screenshot    failure-${TEST NAME}.png

Create Firefox Headless Options
    ${options}=    Evaluate    selenium.webdriver.FirefoxOptions()    modules=selenium.webdriver
    Call Method    ${options}    add_argument    --headless
    # Set the Firefox binary path using the binary property instead of set_binary
    Set To Dictionary    ${options}    binary    ${FIREFOX_BINARY_PATH}
    Set Environment Variable    webdriver.gecko.driver    ${GECKODRIVER_PATH}
    RETURN    ${options}

Create a module scan
    [Arguments]    ${scan_name}    ${scan_target}    ${module_name}
    ${firefox_options}=    Create Firefox Headless Options
    Set Environment Variable    webdriver.gecko.driver    ${GECKODRIVER_PATH}
    Open browser    http://localhost:5001/newscan   firefox    options=${firefox_options}
    Press Keys    name:scanname    van1shland
    Press Keys    name:scantarget    van1shland.io
    Click Element    id:moduletab
    Click Element    id:btn-deselect-all
    Scroll To Element    id:module_${module_name}
    Set Focus To Element    id:module_${module_name}
    Click Element    id:module_${module_name}
    Scroll To Element    id:btn-run-scan
    Click Element    id:btn-run-scan
    Wait Until Element Is Visible    id:btn-browse    timeout=15s #Add wait for the browse button.
    Element Should Be Visible    id:scanstatusbadge #verify that the scan status badge is visible
    ${scan_status}=    Get Text    id:scanstatusbadge
    Should Not Be Equal As Strings    ${scan_status}    ERROR    msg=Scan creation failed.

Create a use case scan
    [Arguments]    ${scan_name}    ${scan_target}    ${use_case}
    ${firefox_options}=    Create Firefox Headless Options
    Set Environment Variable    webdriver.gecko.driver    ${GECKODRIVER_PATH}
    Open browser    http://localhost:5001/newscan    firefox    options=${firefox_options}
    Press Keys    name:scanname    van1shland
    Press Keys    name:scantarget    van1shland.io
    Click Element    id:usecase_${use_case}
    Scroll To Element    id:btn-run-scan
    Click Element    id:btn-run-scan
    Wait Until Element Is Visible    id:btn-browse    timeout=15s #Add wait for the browse button.
    Element Should Be Visible    id:scanstatusbadge #verify that the scan status badge is visible

Scan info page should render tabs
    Element Should Be Visible    id:btn-status
    Element Should Be Visible    id:btn-browse
    Element Should Be Visible    id:btn-correlations
    Element Should Be Visible    id:btn-graph
    Element Should Be Visible    id:btn-info
    Element Should Be Visible    id:btn-log

Scan info Summary tab should render
    Scan info page should render tabs
    Element Should Be Visible    id:vbarsummary

Scan info Browse tab should render
    Scan info page should render tabs
    Element Should Be Visible    id:btn-refresh
    Element Should Be Visible    id:btn-export
    Element Should Be Visible    id:searchvalue
    Element Should Be Visible    id:searchbutton

Scan info Correlations tab should render
    Scan info page should render tabs
    Element Should Be Visible    id:scansummary-content

Scan info Graph tab should render
    Scan info page should render tabs
    Element Should Be Visible    id:graph-container

Scan info Settings tab should render
    Scan info page should render tabs
    Page Should Contain    Meta Information
    Page Should Contain    Global Settings

Scan info Log tab should render
    Scan info page should render tabs
    Element Should Be Visible    id:btn-refresh
    Element Should Be Visible    id:btn-download-logs

Scan list page should render
    Element Should Be Visible    id:scanlist
    Element Should Be Visible    id:btn-rerun
    Element Should Be Visible    id:btn-stop
    Element Should Be Visible    id:btn-refresh
    Element Should Be Visible    id:btn-export
    Element Should Be Visible    id:btn-delete

Settings page should render
    Element Should Be Visible    id:savesettingsform
    Element Should Be Visible    id:btn-save-changes
    Element Should Be Visible    id:btn-import-config
    Element Should Be Visible    id:btn-opt-export
    Element Should Be Visible    id:btn-reset-settings

New scan page should render
    Element Should Be Visible    id:scanname
    Element Should Be Visible    id:scantarget
    Element Should Be Visible    id:usetab
    Element Should Be Visible    id:typetab
    Element Should Be Visible    id:moduletab

Scroll To Element
    [Arguments]    ${locator}
    ${x}=    Get Horizontal Position    ${locator}
    ${y}=    Get Vertical Position    ${locator}
    Execute Javascript    window.scrollTo(${x} - 100, ${y} - 100)
    Wait Until Element is visible    ${locator}    timeout=15s

Wait For Scan To Finish
    [Arguments]    ${scan_name}
    Wait Until Element Is Visible    id:btn-browse    timeout=15s
    Wait Until Element Contains    scanstatusbadge    FINISHED    timeout=60s

***Test Cases***
Main navigation pages should render correctly
    ${firefox_options}=    Create Firefox Headless Options
    Open browser    http://localhost:5001    firefox    options=${firefox_options}
    Click Element    id:nav-link-newscan
    Wait Until Element Is Visible    id:scanname    timeout=15s
    New scan page should render
    Click Element    id:nav-link-scans
    Wait Until Element Is Visible    id:scanlist    timeout=15s
    Scan list page should render
    Click Element    id:nav-link-settings
    Wait Until Element Is Visible    id:savesettingsform    timeout=15s
    Settings page should render
    Close All Browsers

Scan info page should render correctly
    Create a module scan    test scan info    van1shland.io    sfp_countryname
    Wait For Scan To Finish    test scan info
    Click Element    id:btn-status
    Scan info Summary tab should render
    Click Element    id:btn-browse
    Scan info Browse tab should render
    Click Element    id:btn-graph
    Scan info Graph tab should render
    Click Element    id:btn-info
    Scan info Settings tab should render
    Click Element    id:btn-log
    Scan info Log tab should render
    Close All Browsers

Scan list page should list scans
    Create a module scan    test scan list    van1shland.io    sfp_countryname
    Click Element    id:nav-link-scans
    Wait Until Element Is Visible    xpath=//td[contains(text(), 'test scan list')]    timeout=15s
    Close All Browsers

A sfp_dnsresolve scan should resolve INTERNET_NAME to IP_ADDRESS
    Create a module scan    dns resolve    van1shland.io    sfp_dnsresolve
    Wait For Scan To Finish    dns resolve
    Click Element    id:btn-browse
    Scan info Browse tab should render
    Element Should Contain    id:browse-table-content    Domain Name
    Element Should Contain    id:browse-table-content    Internet Name
    Element Should Contain    id:browse-table-content    IP Address
    Close All Browsers

A sfp_dnsresolve scan should reverse resolve IP_ADDRESS to INTERNET_NAME
    Create a module scan    reverse resolve    1.1.1.1    sfp_dnsresolve
    Wait For Scan To Finish    reverse resolve
    Click Element    id:btn-browse
    Scan info Browse tab should render
    Element Should Contain    id:browse-table-content    Domain Name
    Element Should Contain    id:browse-table-content    Internet Name
    Element Should Contain    id:browse-table-content    IP Address
    Close All Browsers

A passive scan with unresolvable target internet name should fail
    Create a use case scan    shouldnotresolve    shouldnotresolve.doesnotexist.local    Passive
    Wait Until Element Is Visible    id:btn-browse    timeout=15s
    Wait Until Element Contains    scanstatusbadge    ERROR    timeout=60s
    Click Element    id:btn-log
    Page Should Contain    Could not resolve
    Close All Browsers
