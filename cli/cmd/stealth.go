package cmd

import (
	"fmt"
	"net/url"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// stealthCmd uses the real API endpoints:
// GET /api/scans/{scan_id}/stealth-stats — per-scan stealth statistics
// GET /stealth-stats                     — global stealth statistics (scan router)
// GET /api/ai-config/stealth-levels      — available stealth levels
// GET /api/ai-config/modules             — stealth-aware module listing
var stealthCmd = &cobra.Command{
	Use:   "stealth",
	Short: "Stealth scanning configuration and statistics",
}

var stealthStatsCmd = &cobra.Command{
	Use:   "stats [scan-id]",
	Short: "Show stealth statistics for a scan",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "scan ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/scans/%s/stealth-stats", args[0]), &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			printGenericResponse(resp)
		}
		return nil
	},
}

var stealthGlobalCmd = &cobra.Command{
	Use:   "global",
	Short: "Show global stealth statistics",
	RunE:  simpleGet("/stealth-stats"),
}

var stealthLevelsCmd = &cobra.Command{
	Use:   "levels",
	Short: "List available stealth levels",
	RunE:  simpleGet("/api/ai-config/stealth-levels"),
}

var stealthModulesCmd = &cobra.Command{
	Use:   "modules",
	Short: "Show modules filtered by stealth capabilities",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		passiveOnly, _ := cmd.Flags().GetBool("passive-only")
		category, _ := cmd.Flags().GetString("category")
		targetType, _ := cmd.Flags().GetString("target-type")

		params := url.Values{}
		if passiveOnly {
			params.Set("passive_only", "true")
		}
		if category != "" {
			params.Set("category", category)
		}
		if targetType != "" {
			params.Set("target_type", targetType)
		}
		path := "/api/ai-config/modules"
		if q := params.Encode(); q != "" {
			path += "?" + q
		}

		var resp interface{}
		if err := c.Get(path, &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			printGenericResponse(resp)
		}
		return nil
	},
}

func init() {
	stealthModulesCmd.Flags().Bool("passive-only", false, "Show only passive modules")
	stealthModulesCmd.Flags().String("category", "", "Filter by module category")
	stealthModulesCmd.Flags().String("target-type", "", "Filter by target type")

	stealthCmd.AddCommand(stealthStatsCmd)
	stealthCmd.AddCommand(stealthGlobalCmd)
	stealthCmd.AddCommand(stealthLevelsCmd)
	stealthCmd.AddCommand(stealthModulesCmd)
	rootCmd.AddCommand(stealthCmd)
}
