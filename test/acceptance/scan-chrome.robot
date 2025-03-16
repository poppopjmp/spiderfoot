***Settings***
Library           SeleniumLibrary
Library           OperatingSystem
Test Teardown     Run Keyword If Test Failed  Capture Failure Screenshot
Resource          variables.robot  # Externalize variables

***Variables***
${CHROMEDRIVER_PATH}    /usr/local/bin/chromedriver
${WAIT_TIMEOUT}         120s  # Increased timeout for better reliability
${SCROLL_PADDING}       200   # Padding to ensure elements aren't hidden behind headers/footers

***Keywords***
Capture Failure Screenshot
    Capture Page Screenshot  failure-${TEST NAME}.png

Create Chrome Headless Options
    ${options}=    Evaluate    selenium.webdriver.ChromeOptions()    modules=selenium.webdriver
    Call Method    ${options}    add_argument    --headless
    Call Method    ${options}    add_argument    --no-sandbox
    Call Method    ${options}    add_argument    --disable-dev-shm-usage
    Call Method    ${options}    add_argument    --window-size=1920,1080  # Set a larger window size
    ${service}=    Evaluate    selenium.webdriver.chrome.service.Service(executable_path='${CHROMEDRIVER_PATH}')    modules=selenium.webdriver.chrome.service
    RETURN    ${options}    ${service}

Create a module scan
    [Arguments]  ${scan_name}  ${scan_target}  ${module_name}
    ${chrome_options}    ${service}=    Create Chrome Headless Options
    Open browser              http://127.0.0.1:5001/newscan    browser=chrome    options=${chrome_options}    service=${service}    timeout=${WAIT_TIMEOUT}
    Wait Until Element Is Visible    name:scanname    timeout=${WAIT_TIMEOUT}
    Press Keys                name:scanname            ${scan_name}
    Press Keys                name:scantarget          ${scan_target}
    Click Element             id:moduletab
    Wait Until Element Is Visible    id:btn-deselect-all    timeout=${WAIT_TIMEOUT}
    Click Element             id:btn-deselect-all
    Safe Scroll To Element    id:module_${module_name}
    Wait Until Element Is Visible    id:module_${module_name}    timeout=${WAIT_TIMEOUT}
    Execute Javascript        document.getElementById('module_${module_name}').click();
    Safe Scroll To Element    id:btn-run-scan
    Wait Until Element Is Clickable    id:btn-run-scan    timeout=${WAIT_TIMEOUT}
    Click Element             id:btn-run-scan
    Wait Until Element Is Visible    id:btn-browse    timeout=${WAIT_TIMEOUT}
    Element Should Be Visible    id:scanstatusbadge
    ${scan_status}=    Get Text    id:scanstatusbadge
    Should Not Be Equal As Strings    ${scan_status}    ERROR    msg=Scan creation failed.

Create a use case scan
    [Arguments]  ${scan_name}  ${scan_target}  ${use_case}
    ${chrome_options}    ${service}=    Create Chrome Headless Options
    Open browser              http://localhost:5001/newscan    browser=chrome    options=${chrome_options}    service=${service}    timeout=${WAIT_TIMEOUT}
    Wait Until Element Is Visible    name:scanname    timeout=${WAIT_TIMEOUT}
    Press Keys                name:scanname            ${scan_name}
    Press Keys                name:scantarget          ${scan_target}
    # Check if element exists by different ID format
    ${passive_exists}=    Run Keyword And Return Status    Element Should Be Visible    id:usecase_${use_case}
    Run Keyword If    ${passive_exists}    Safe Click Element    id:usecase_${use_case}
    ...    ELSE IF    '${use_case}' == 'Passive'    Safe Click Element    xpath://input[@id='usecase_passive']
    ...    ELSE    Safe Click Element    xpath://input[@value='${use_case}']
    Safe Scroll To Element    id:btn-run-scan
    Wait Until Element Is Clickable    id:btn-run-scan    timeout=${WAIT_TIMEOUT}
    Click Element             id:btn-run-scan
    Wait Until Element Is Visible    id:scanstatusbadge    timeout=${WAIT_TIMEOUT}

Scan info page should render tabs
    Element Should Be Visible     id:btn-status
    Element Should Be Visible     id:btn-browse
    Element Should Be Visible     id:btn-correlations
    Element Should Be Visible     id:btn-graph
    Element Should Be Visible     id:btn-info
    Element Should Be Visible     id:btn-log

Scan info Summary tab should render
    Scan info page should render tabs
    Wait Until Element Is Visible     xpath=//*[contains(@class, 'summary-chart')]    timeout=${WAIT_TIMEOUT}

Scan info Browse tab should render
    Scan info page should render tabs
    Element Should Be Visible     id:btn-refresh
    Element Should Be Visible     id:btn-export
    Element Should Be Visible     id:searchvalue
    Element Should Be Visible     id:searchbutton

Scan info Correlations tab should render
    Scan info page should render tabs
    Wait Until Element Is Visible     xpath=//*[contains(@id, 'scansummary') or contains(@class, 'scansummary')]    timeout=${WAIT_TIMEOUT}

Scan info Graph tab should render
    Scan info page should render tabs
    Wait Until Element Is Visible     id:graph-container    timeout=${WAIT_TIMEOUT}

Scan info Settings tab should render
    Scan info page should render tabs
    Wait Until Page Contains     Meta Information    timeout=${WAIT_TIMEOUT}
    Wait Until Page Contains     Global Settings    timeout=${WAIT_TIMEOUT}

Scan info Log tab should render
    Scan info page should render tabs
    Element Should Be Visible     id:btn-refresh
    Element Should Be Visible     id:btn-download-logs

Scan list page should render
    Wait Until Element Is Visible     xpath=//div[@id='scanlist' or contains(@class, 'scanlist')]    timeout=${WAIT_TIMEOUT}
    Element Should Be Visible     id:btn-rerun
    Element Should Be Visible     id:btn-stop
    Element Should Be Visible     id:btn-refresh
    Element Should Be Visible     id:btn-export
    Element Should Be Visible     id:btn-delete

Settings page should render
    Element Should Be Visible     id:savesettingsform
    Element Should Be Visible     id:btn-save-changes
    Element Should Be Visible     id:btn-import-config
    Element Should Be Visible     id:btn-opt-export
    Element Should Be Visible     id:btn-reset-settings

New scan page should render
    Element Should Be Visible     id:scanname
    Element Should Be Visible     id:scantarget
    Element Should Be Visible     id:usetab
    Element Should Be Visible     id:typetab
    Element Should Be Visible     id:moduletab

Scroll To Element
    [Arguments]  ${locator}
    ${x}=         Get Horizontal Position  ${locator}
    ${y}=         Get Vertical Position    ${locator}
    Execute Javascript    window.scrollTo(${x} - 100, ${y} - 100)
    Wait Until Element is visible  ${locator}  timeout=30s

Safe Scroll To Element
    [Arguments]  ${locator}
    Wait Until Element Is Visible    ${locator}    timeout=${WAIT_TIMEOUT}
    ${y}=    Execute Javascript    return document.querySelector('${locator}'.replace('id:', '#')).getBoundingClientRect().top + window.pageYOffset - ${SCROLL_PADDING};
    Execute Javascript    window.scrollTo(0, arguments[0])    ${y}
    Sleep    1s    # Give time for any animations to complete
    
Safe Click Element
    [Arguments]  ${locator}
    Safe Scroll To Element    ${locator}
    Wait Until Element Is Clickable    ${locator}    timeout=${WAIT_TIMEOUT}
    Execute Javascript    document.querySelector('${locator}'.replace('id:', '#')).click();

Wait Until Element Is Clickable
    [Arguments]  ${locator}  ${timeout}=${WAIT_TIMEOUT}
    Wait Until Element Is Visible    ${locator}    timeout=${timeout}
    # Ensure element is not covered by something else
    ${is_clickable}=    Execute Javascript
    ...    return (function(element) {
    ...        const rect = element.getBoundingClientRect();
    ...        const elementAtPoint = document.elementFromPoint(rect.left + rect.width/2, rect.top + rect.height/2);
    ...        return element.contains(elementAtPoint) || elementAtPoint.contains(element);
    ...    })(document.querySelector('${locator}'.replace('id:', '#')));
    Should Be True    ${is_clickable}    Element ${locator} is not clickable

Wait For Scan To Finish
    [Arguments]  ${scan_name}
    Wait Until Element Is Visible    id:btn-browse    timeout=${WAIT_TIMEOUT}
    Wait Until Element Contains     scanstatusbadge   FINISHED     timeout=${WAIT_TIMEOUT}
    Sleep    2s    # Give a moment for page to stabilize after scan finishes

***Test Cases***
Main navigation pages should render correctly
    ${chrome_options}    ${service}=    Create Chrome Headless Options
    Open browser              http://localhost:5001    browser=chrome    options=${chrome_options}    service=${service}    timeout=${WAIT_TIMEOUT}
    Wait Until Element Is Visible    id:nav-link-newscan    timeout=${WAIT_TIMEOUT}
    Click Element                 id:nav-link-newscan
    Wait Until Element Is Visible    id:scanname    timeout=${WAIT_TIMEOUT}
    New scan page should render
    Click Element                 id:nav-link-scans
    Wait Until Element Is Visible    xpath=//div[@id='scanlist' or contains(@class, 'scanlist')]    timeout=${WAIT_TIMEOUT}
    Scan list page should render
    Click Element                 id:nav-link-settings
    Wait Until Element Is Visible    id:savesettingsform    timeout=${WAIT_TIMEOUT}
    Settings page should render
    Close All Browsers

Scan info page should render correctly
    Create a module scan           test_scan_info    van1shland.io    sfp_countryname
    Wait For Scan To Finish        test_scan_info
    Safe Click Element            id:btn-status
    Scan info Summary tab should render
    Safe Click Element            id:btn-browse
    Scan info Browse tab should render
    Safe Click Element            id:btn-graph
    Scan info Graph tab should render
    Safe Click Element            id:btn-info
    Scan info Settings tab should render
    Safe Click Element            id:btn-log
    Scan info Log tab should render
    Close All Browsers

Scan list page should list scans
    Create a module scan           test_scan_list    van1shland.io    sfp_countryname
    Safe Click Element            id:nav-link-scans
    Wait Until Element Is Visible   xpath=//table[contains(@class, 'table')]//td[contains(text(), 'test_scan_list')]   timeout=${WAIT_TIMEOUT}
    Close All Browsers

A sfp_dnsresolve scan should resolve INTERNET_NAME to IP_ADDRESS
    Create a module scan           dns_resolve     van1shland.io    sfp_dnsresolve
    Wait For Scan To Finish       dns_resolve
    Safe Click Element            id:btn-browse
    Scan info Browse tab should render
    Wait Until Element Is Visible   xpath=//table[contains(@class, 'table')]    timeout=${WAIT_TIMEOUT}
    Page Should Contain    Domain Name
    Page Should Contain    Internet Name
    Page Should Contain    IP Address
    Close All Browsers

A sfp_dnsresolve scan should reverse resolve IP_ADDRESS to INTERNET_NAME
    Create a module scan           reverse_resolve   1.1.1.1           sfp_dnsresolve
    Wait For Scan To Finish      reverse_resolve
    Safe Click Element            id:btn-browse
    Scan info Browse tab should render
    Wait Until Element Is Visible   xpath=//table[contains(@class, 'table')]    timeout=${WAIT_TIMEOUT}
    Page Should Contain    Domain Name
    Page Should Contain    Internet Name
    Page Should Contain    IP Address
    Close All Browsers

A passive scan with unresolvable target internet name should fail
    Create a use case scan         shouldnotresolve    shouldnotresolve.doesnotexist.local    Passive
    Wait Until Element Is Visible    id:btn-browse    timeout=${WAIT_TIMEOUT}
    Wait Until Element Contains     scanstatusbadge   ERROR     timeout=${WAIT_TIMEOUT}
    Safe Click Element              id:btn-log
    Wait Until Page Contains     Could not resolve    timeout=${WAIT_TIMEOUT}
    Close All Browsers
