package cmd

import (
	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// metricsCmd uses the real API endpoints:
// GET /metrics            — Prometheus text format (health router, unversioned)
// GET /api/scan-metrics   — JSON dashboard metrics
// POST /api/scan-metrics/reset — Reset counters
var metricsCmd = &cobra.Command{
	Use:   "metrics",
	Short: "Show platform metrics",
}

var metricsPrometheusCmd = &cobra.Command{
	Use:   "prometheus",
	Short: "Show Prometheus-format metrics",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		data, _, err := c.GetRaw("/metrics")
		if err != nil {
			return err
		}
		cmd.Print(string(data))
		return nil
	},
}

var metricsDashboardCmd = &cobra.Command{
	Use:   "dashboard",
	Short: "Show scan metrics dashboard (JSON)",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp interface{}
		if err := c.Get("/api/scan-metrics", &resp); err != nil {
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

var metricsResetCmd = &cobra.Command{
	Use:   "reset",
	Short: "Reset scan metric counters",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		if err := c.Post("/api/scan-metrics/reset", nil, nil); err != nil {
			return err
		}
		output.Success("Scan metrics counters reset")
		return nil
	},
}

func init() {
	metricsCmd.AddCommand(metricsPrometheusCmd)
	metricsCmd.AddCommand(metricsDashboardCmd)
	metricsCmd.AddCommand(metricsResetCmd)
	rootCmd.AddCommand(metricsCmd)
}
