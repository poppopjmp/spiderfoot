package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// reportCmd uses the real API endpoints:
// POST /api/reports/generate — generate a report (202 Accepted)
// GET  /api/reports          — list reports
// GET  /api/reports/{id}     — get report
// GET  /api/reports/{id}/status — check generation status
// GET  /api/reports/{id}/export?format= — download report
// DELETE /api/reports/{id}   — delete report
var reportCmd = &cobra.Command{
	Use:     "report",
	Aliases: []string{"reports"},
	Short:   "Manage scan reports",
}

var reportListCmd = &cobra.Command{
	Use:   "list",
	Short: "List reports",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		scanID, _ := cmd.Flags().GetString("scan-id")
		limit, _ := cmd.Flags().GetInt("limit")

		path := fmt.Sprintf("/api/reports?limit=%d", limit)
		if scanID != "" {
			path += "&scan_id=" + scanID
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
				header := []string{"ID", "Scan", "Status", "Format", "Created"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["report_id"]),
							fmt.Sprintf("%v", m["scan_id"]),
							fmt.Sprintf("%v", m["status"]),
							fmt.Sprintf("%v", m["format"]),
							fmt.Sprintf("%v", m["created_at"]),
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

var reportGenerateCmd = &cobra.Command{
	Use:   "generate",
	Short: "Generate a new scan report",
	RunE: func(cmd *cobra.Command, args []string) error {
		scanID, _ := cmd.Flags().GetString("scan-id")
		format, _ := cmd.Flags().GetString("format")
		template, _ := cmd.Flags().GetString("template")

		if scanID == "" {
			return fmt.Errorf("--scan-id is required")
		}
		body := map[string]string{"scan_id": scanID, "format": format}
		if template != "" {
			body["template"] = template
		}
		payload, _ := json.Marshal(body)

		c := client.New()
		var resp map[string]interface{}
		if err := c.Post("/api/reports/generate", bytes.NewReader(payload), &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			output.Success("Report generation started: %v", resp["report_id"])
			fmt.Println("Use 'sf report status <id>' to check progress")
		}
		return nil
	},
}

var reportStatusCmd = &cobra.Command{
	Use:   "status [report-id]",
	Short: "Check report generation status",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "report ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/reports/%s/status", args[0]), &resp); err != nil {
			return err
		}
		printGenericResponse(resp)
		return nil
	},
}

var reportDownloadCmd = &cobra.Command{
	Use:   "download [report-id]",
	Short: "Download a generated report",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "report ID"); err != nil {
			return err
		}
		format, _ := cmd.Flags().GetString("format")
		outFile, _ := cmd.Flags().GetString("file")

		c := client.New()
		path := fmt.Sprintf("/api/reports/%s/export?format=%s", args[0], format)
		data, _, err := c.GetRaw(path)
		if err != nil {
			return err
		}

		if outFile == "" {
			outFile = fmt.Sprintf("report_%s.%s", args[0][:min(12, len(args[0]))], format)
		}
		if err := os.WriteFile(outFile, data, 0600); err != nil {
			return fmt.Errorf("writing file: %w", err)
		}
		output.Success("Report saved to %s (%d bytes)", outFile, len(data))
		return nil
	},
}

var reportDeleteCmd = &cobra.Command{
	Use:   "delete [report-id]",
	Short: "Delete a report",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "report ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Delete(fmt.Sprintf("/api/reports/%s", args[0]), nil); err != nil {
			return err
		}
		output.Success("Report %s deleted", args[0])
		return nil
	},
}

func init() {
	reportListCmd.Flags().String("scan-id", "", "Filter by scan ID")
	reportListCmd.Flags().Int("limit", 20, "Max reports to return")

	reportGenerateCmd.Flags().String("scan-id", "", "Scan ID to generate report for (required)")
	reportGenerateCmd.Flags().String("format", "html", "Report format: markdown, html, json, plain_text, csv")
	reportGenerateCmd.Flags().String("template", "", "Report template to use")

	reportDownloadCmd.Flags().String("format", "html", "Export format: markdown, html, json, plain_text, csv")
	reportDownloadCmd.Flags().StringP("file", "f", "", "Output filename")

	reportCmd.AddCommand(reportListCmd)
	reportCmd.AddCommand(reportGenerateCmd)
	reportCmd.AddCommand(reportStatusCmd)
	reportCmd.AddCommand(reportDownloadCmd)
	reportCmd.AddCommand(reportDeleteCmd)
	rootCmd.AddCommand(reportCmd)
}
