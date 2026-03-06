package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// monitorCmd uses the real API endpoints at /api/monitor/*.
var monitorCmd = &cobra.Command{
	Use:   "monitor",
	Short: "Domain monitoring and change detection",
}

var monitorListCmd = &cobra.Command{
	Use:   "list",
	Short: "List monitored domains",
	RunE:  simpleGet("/api/monitor/domains"),
}

var monitorGetCmd = &cobra.Command{
	Use:   "get [domain]",
	Short: "Get monitoring details for a domain",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/monitor/domains/%s", args[0]), &resp); err != nil {
			return err
		}
		printGenericResponse(resp)
		return nil
	},
}

var monitorChangesCmd = &cobra.Command{
	Use:   "changes [domain]",
	Short: "Show recent changes for a monitored domain",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		limit, _ := cmd.Flags().GetInt("limit")
		path := fmt.Sprintf("/api/monitor/domains/%s/changes?limit=%d", args[0], limit)

		var resp interface{}
		if err := c.Get(path, &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			if items, ok := resp.([]interface{}); ok {
				header := []string{"Time", "Type", "Details"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["timestamp"]),
							fmt.Sprintf("%v", m["change_type"]),
							fmt.Sprintf("%v", m["details"]),
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

var monitorCheckCmd = &cobra.Command{
	Use:   "check [domain]",
	Short: "Trigger an immediate check for a monitored domain",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		if err := c.Post(fmt.Sprintf("/api/monitor/domains/%s/check", args[0]), nil, nil); err != nil {
			return err
		}
		output.Success("Check triggered for %s", args[0])
		return nil
	},
}

func init() {
	monitorChangesCmd.Flags().Int("limit", 20, "Maximum changes to return")

	monitorCmd.AddCommand(monitorListCmd)
	monitorCmd.AddCommand(monitorGetCmd)
	monitorCmd.AddCommand(monitorChangesCmd)
	monitorCmd.AddCommand(monitorCheckCmd)
	rootCmd.AddCommand(monitorCmd)
}
