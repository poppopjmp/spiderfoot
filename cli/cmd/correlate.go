package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

var correlateCmd = &cobra.Command{
	Use:   "correlate [scan-id]",
	Short: "Run correlations for a scan",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "scan ID"); err != nil {
			return err
		}
		c := client.New()
		var resp map[string]interface{}
		if err := c.Post(fmt.Sprintf("/api/scans/%s/correlations/run", args[0]), nil, &resp); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			total, _ := resp["total"].(float64)
			fmt.Printf("Correlations found: %.0f\n", total)
			if corrs, ok := resp["correlations"].([]interface{}); ok {
				for _, c := range corrs {
					if m, ok := c.(map[string]interface{}); ok {
						fmt.Printf("  [%s] %s\n", m["rule_risk"], m["title"])
					}
				}
			}
		}
		return nil
	},
}

func init() {
	rootCmd.AddCommand(correlateCmd)
}
