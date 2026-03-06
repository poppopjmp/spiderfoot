package cmd

import (
	"fmt"
	"net/url"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// auditCmd uses the real API endpoints:
// GET  /api/audit           — list audit events (with filters)
// GET  /api/audit/actions   — list audit action types
// GET  /api/audit/stats     — audit statistics
var auditCmd = &cobra.Command{
	Use:   "audit",
	Short: "View audit logs and statistics",
}

var auditListCmd = &cobra.Command{
	Use:   "list",
	Short: "List audit events",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		action, _ := cmd.Flags().GetString("action")
		actor, _ := cmd.Flags().GetString("actor")
		resourceType, _ := cmd.Flags().GetString("resource-type")
		severity, _ := cmd.Flags().GetString("severity")
		sinceHours, _ := cmd.Flags().GetInt("since-hours")
		limit, _ := cmd.Flags().GetInt("limit")

		params := url.Values{}
		if action != "" {
			params.Set("action", action)
		}
		if actor != "" {
			params.Set("actor", actor)
		}
		if resourceType != "" {
			params.Set("resource_type", resourceType)
		}
		if severity != "" {
			params.Set("severity", severity)
		}
		if sinceHours > 0 {
			params.Set("since_hours", fmt.Sprintf("%d", sinceHours))
		}
		if limit > 0 {
			params.Set("limit", fmt.Sprintf("%d", limit))
		}

		path := "/api/audit"
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
			if items, ok := resp.([]interface{}); ok {
				header := []string{"Time", "Action", "Actor", "Resource", "Severity"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["timestamp"]),
							fmt.Sprintf("%v", m["action"]),
							fmt.Sprintf("%v", m["actor"]),
							fmt.Sprintf("%v", m["resource_type"]),
							fmt.Sprintf("%v", m["severity"]),
						})
					}
				}
				output.PrintTable(header, rows)
			} else {
				printGenericResponse(resp)
			}
		}
		return nil
	},
}

var auditActionsCmd = &cobra.Command{
	Use:   "actions",
	Short: "List available audit action types",
	RunE:  simpleGet("/api/audit/actions"),
}

var auditStatsCmd = &cobra.Command{
	Use:   "stats",
	Short: "Show audit statistics",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		sinceHours, _ := cmd.Flags().GetInt("since-hours")
		path := "/api/audit/stats"
		if sinceHours > 0 {
			path += fmt.Sprintf("?since_hours=%d", sinceHours)
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
	auditListCmd.Flags().String("action", "", "Filter by action type")
	auditListCmd.Flags().String("actor", "", "Filter by actor")
	auditListCmd.Flags().String("resource-type", "", "Filter by resource type")
	auditListCmd.Flags().String("severity", "", "Filter by severity")
	auditListCmd.Flags().Int("since-hours", 24, "Hours to look back")
	auditListCmd.Flags().Int("limit", 50, "Maximum entries to return")

	auditStatsCmd.Flags().Int("since-hours", 24, "Hours to look back")

	auditCmd.AddCommand(auditListCmd)
	auditCmd.AddCommand(auditActionsCmd)
	auditCmd.AddCommand(auditStatsCmd)
	rootCmd.AddCommand(auditCmd)
}
