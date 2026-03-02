package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

var exportCmd = &cobra.Command{
	Use:   "export",
	Short: "Export scan data in various formats",
}

var exportJSONCmd = &cobra.Command{
	Use:   "json [scan-id]",
	Short: "Export scan results as JSON",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return doExport(args[0], "json", "json")
	},
}

var exportCSVCmd = &cobra.Command{
	Use:   "csv [scan-id]",
	Short: "Export scan results as CSV",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return doExport(args[0], "csv", "csv")
	},
}

var exportSTIXCmd = &cobra.Command{
	Use:   "stix [scan-id]",
	Short: "Export scan results as STIX 2.1 bundle",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return doExport(args[0], "stix", "json")
	},
}

var exportSARIFCmd = &cobra.Command{
	Use:   "sarif [scan-id]",
	Short: "Export scan results as SARIF",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return doExport(args[0], "sarif", "sarif.json")
	},
}

// doExport fetches scan data in the specified format using the real API endpoint:
// GET /api/scans/{scan_id}/export?format=json|csv|stix|sarif
func doExport(scanID, format, ext string) error {
	if err := validateSafeID(scanID, "scan ID"); err != nil {
		return err
	}
	c := client.New()
	includeRaw, _ := exportCmd.PersistentFlags().GetBool("include-raw")
	maxEvents, _ := exportCmd.PersistentFlags().GetInt("max-events")

	path := fmt.Sprintf("/api/scans/%s/export?format=%s", scanID, format)
	if includeRaw {
		path += "&include_raw=true"
	}
	if maxEvents > 0 {
		path += fmt.Sprintf("&max_events=%d", maxEvents)
	}

	data, _, err := c.GetRaw(path)
	if err != nil {
		return err
	}

	outFile, _ := exportCmd.PersistentFlags().GetString("file")
	if outFile == "" {
		outFile = fmt.Sprintf("spiderfoot_%s.%s", scanID[:min(12, len(scanID))], ext)
	}

	if err := os.WriteFile(outFile, data, 0600); err != nil {
		return fmt.Errorf("writing file: %w", err)
	}
	output.Success("Exported to %s (%d bytes)", outFile, len(data))
	return nil
}

func init() {
	exportCmd.PersistentFlags().StringP("file", "f", "", "Output filename (auto-generated if omitted)")
	exportCmd.PersistentFlags().Bool("include-raw", false, "Include raw event data")
	exportCmd.PersistentFlags().Int("max-events", 0, "Maximum events to export (0 = all)")

	exportCmd.AddCommand(exportJSONCmd)
	exportCmd.AddCommand(exportCSVCmd)
	exportCmd.AddCommand(exportSTIXCmd)
	exportCmd.AddCommand(exportSARIFCmd)
	rootCmd.AddCommand(exportCmd)
}
