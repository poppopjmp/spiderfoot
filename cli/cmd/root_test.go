package cmd

import (
	"testing"
)

// TestRootCommandHasSubcommands verifies the command tree includes all expected subcommands.
func TestRootCommandHasSubcommands(t *testing.T) {
	expected := []string{
		"health",
		"scan",
		"modules",
		"export",
		"schedule",
		"config",
		"version",
		"correlate",
		"metrics",
		"iac",
		"stealth",
		"audit",
		"keys",
		"workspace",
		"report",
		"auth",
		"asm",
		"tasks",
		"webhooks",
		"monitor",
		"tags",
	}

	cmds := rootCmd.Commands()
	cmdNames := make(map[string]bool, len(cmds))
	for _, c := range cmds {
		cmdNames[c.Name()] = true
	}

	for _, name := range expected {
		if !cmdNames[name] {
			t.Errorf("root command missing subcommand %q", name)
		}
	}
}

// TestScanSubcommands verifies scan has all expected subcommands.
func TestScanSubcommands(t *testing.T) {
	expected := []string{
		"list", "get", "start", "stop", "delete", "events", "correlations",
		"search", "summary", "logs", "profiles", "rerun", "clone",
		"retry", "archive", "unarchive", "compare", "history",
	}

	cmds := scanCmd.Commands()
	cmdNames := make(map[string]bool, len(cmds))
	for _, c := range cmds {
		cmdNames[c.Name()] = true
	}

	for _, name := range expected {
		if !cmdNames[name] {
			t.Errorf("scan command missing subcommand %q", name)
		}
	}
}

// TestScheduleSubcommands verifies schedule has the expected subcommands.
func TestScheduleSubcommands(t *testing.T) {
	expected := []string{"list", "create", "update", "delete", "trigger"}

	cmds := scheduleCmd.Commands()
	cmdNames := make(map[string]bool, len(cmds))
	for _, c := range cmds {
		cmdNames[c.Name()] = true
	}

	for _, name := range expected {
		if !cmdNames[name] {
			t.Errorf("schedule command missing subcommand %q", name)
		}
	}
}

// TestIaCSubcommands verifies iac has generate/validate/providers.
func TestIaCSubcommands(t *testing.T) {
	expected := []string{"generate", "validate", "providers"}

	cmds := iacCmd.Commands()
	cmdNames := make(map[string]bool, len(cmds))
	for _, c := range cmds {
		cmdNames[c.Name()] = true
	}

	for _, name := range expected {
		if !cmdNames[name] {
			t.Errorf("iac command missing subcommand %q", name)
		}
	}
}

// TestStealthSubcommands verifies stealth command tree.
func TestStealthSubcommands(t *testing.T) {
	expected := []string{"stats", "global", "levels", "modules"}

	cmds := stealthCmd.Commands()
	cmdNames := make(map[string]bool, len(cmds))
	for _, c := range cmds {
		cmdNames[c.Name()] = true
	}

	for _, name := range expected {
		if !cmdNames[name] {
			t.Errorf("stealth command missing subcommand %q", name)
		}
	}
}

// TestModulesSubcommands verifies modules command tree.
func TestModulesSubcommands(t *testing.T) {
	expected := []string{"list", "get", "stats", "categories", "types", "enable", "disable"}

	cmds := modulesCmd.Commands()
	cmdNames := make(map[string]bool, len(cmds))
	for _, c := range cmds {
		cmdNames[c.Name()] = true
	}

	for _, name := range expected {
		if !cmdNames[name] {
			t.Errorf("modules command missing subcommand %q", name)
		}
	}
}

// TestAuditSubcommands verifies audit command tree.
func TestAuditSubcommands(t *testing.T) {
	expected := []string{"list", "actions", "stats"}

	cmds := auditCmd.Commands()
	cmdNames := make(map[string]bool, len(cmds))
	for _, c := range cmds {
		cmdNames[c.Name()] = true
	}

	for _, name := range expected {
		if !cmdNames[name] {
			t.Errorf("audit command missing subcommand %q", name)
		}
	}
}

// TestKeysSubcommands verifies keys command tree.
func TestKeysSubcommands(t *testing.T) {
	expected := []string{"list", "create", "get", "delete", "revoke"}

	cmds := keysCmd.Commands()
	cmdNames := make(map[string]bool, len(cmds))
	for _, c := range cmds {
		cmdNames[c.Name()] = true
	}

	for _, name := range expected {
		if !cmdNames[name] {
			t.Errorf("keys command missing subcommand %q", name)
		}
	}
}

// TestWorkspaceSubcommands verifies workspace command tree.
func TestWorkspaceSubcommands(t *testing.T) {
	expected := []string{"list", "get", "create", "delete", "set-active", "targets", "scans"}

	cmds := workspaceCmd.Commands()
	cmdNames := make(map[string]bool, len(cmds))
	for _, c := range cmds {
		cmdNames[c.Name()] = true
	}

	for _, name := range expected {
		if !cmdNames[name] {
			t.Errorf("workspace command missing subcommand %q", name)
		}
	}
}

// TestValidateSafeID verifies the scan-ID validator.
func TestValidateSafeID(t *testing.T) {
	tests := []struct {
		id    string
		valid bool
	}{
		{"abc-123", true},
		{"scan_001", true},
		{"ABC", true},
		{"", false},
		{"a b c", false},
		{"../etc/passwd", false},
		{"x; rm -rf /", false},
	}

	for _, tt := range tests {
		err := validateSafeID(tt.id, "test")
		if tt.valid && err != nil {
			t.Errorf("validateSafeID(%q) should pass but got error: %v", tt.id, err)
		}
		if !tt.valid && err == nil {
			t.Errorf("validateSafeID(%q) should fail but passed", tt.id)
		}
	}
}

// TestFormatEpoch verifies epoch formatting edge cases.
func TestFormatEpoch(t *testing.T) {
	if result := formatEpoch(0); result != "—" {
		t.Errorf("formatEpoch(0) = %q, want \"—\"", result)
	}
	if result := formatEpoch(-1); result != "—" {
		t.Errorf("formatEpoch(-1) = %q, want \"—\"", result)
	}
	if result := formatEpoch(1700000000); result == "—" {
		t.Error("formatEpoch(1700000000) should not return \"—\"")
	}
}

// TestTruncID verifies ID truncation.
func TestTruncID(t *testing.T) {
	if result := truncID("short"); result != "short" {
		t.Errorf("truncID(\"short\") = %q, want \"short\"", result)
	}
	long := "abcdefghijklmnopqrstuvwxyz"
	if result := truncID(long); len(result) != 12 {
		t.Errorf("truncID(%q) length = %d, want 12", long, len(result))
	}
}
