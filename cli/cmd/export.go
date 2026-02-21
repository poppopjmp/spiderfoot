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
	Short: "Export scan data",
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

var exportExcelCmd = &cobra.Command{
	Use:   "excel [scan-id]",
	Short: "Export scan results as Excel (.xlsx)",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		return doExport(args[0], "xlsx", "xlsx")
	},
}

func doExport(scanID, format, ext string) error {
	c := client.New()
	path := fmt.Sprintf("/api/scans/%s/export/%s", scanID, format)

	data, _, err := c.GetRaw(path)
	if err != nil {
		return err
	}

	outFile, _ := exportCmd.PersistentFlags().GetString("file")
	if outFile == "" {
		outFile = fmt.Sprintf("spiderfoot_%s.%s", scanID[:min(12, len(scanID))], ext)
	}

	if err := os.WriteFile(outFile, data, 0644); err != nil {
		return fmt.Errorf("writing file: %w", err)
	}
	output.Success("Exported to %s (%d bytes)", outFile, len(data))
	return nil
}

func init() {
	exportCmd.PersistentFlags().StringP("file", "f", "", "Output filename (auto-generated if omitted)")

	exportCmd.AddCommand(exportJSONCmd)
	exportCmd.AddCommand(exportCSVCmd)
	exportCmd.AddCommand(exportSTIXCmd)
	exportCmd.AddCommand(exportExcelCmd)
	rootCmd.AddCommand(exportCmd)
}
