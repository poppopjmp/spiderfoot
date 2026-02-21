package cmd

import (
	"fmt"

	"github.com/fatih/color"
	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

type healthResp struct {
	Status  string `json:"status"`
	Version string `json:"version"`
	Uptime  int64  `json:"uptime_seconds"`
}

var healthCmd = &cobra.Command{
	Use:   "health",
	Short: "Check the SpiderFoot API server health",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp healthResp
		if err := c.Get("/api/health", &resp); err != nil {
			output.Error("Server unreachable: %v", err)
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			statusColor := color.GreenString(resp.Status)
			if resp.Status != "ok" && resp.Status != "healthy" {
				statusColor = color.RedString(resp.Status)
			}
			fmt.Printf("Status:   %s\n", statusColor)
			fmt.Printf("Version:  %s\n", resp.Version)
			if resp.Uptime > 0 {
				fmt.Printf("Uptime:   %ds\n", resp.Uptime)
			}
		}
		return nil
	},
}

func init() {
	rootCmd.AddCommand(healthCmd)
}
