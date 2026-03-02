package cmd

import (
	"fmt"
	"net/url"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// asmCmd uses the real API endpoints at /api/asm/*.
var asmCmd = &cobra.Command{
	Use:   "asm",
	Short: "Attack Surface Management",
}

var asmAssetsCmd = &cobra.Command{
	Use:   "assets",
	Short: "List discovered assets",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		assetType, _ := cmd.Flags().GetString("type")
		risk, _ := cmd.Flags().GetString("risk")
		status, _ := cmd.Flags().GetString("status")
		search, _ := cmd.Flags().GetString("search")
		limit, _ := cmd.Flags().GetInt("limit")

		params := url.Values{}
		if assetType != "" {
			params.Set("asset_type", assetType)
		}
		if risk != "" {
			params.Set("risk", risk)
		}
		if status != "" {
			params.Set("status", status)
		}
		if search != "" {
			params.Set("search", search)
		}
		if limit > 0 {
			params.Set("limit", fmt.Sprintf("%d", limit))
		}

		path := "/api/asm/assets"
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
				header := []string{"ID", "Type", "Value", "Risk", "Status"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["asset_id"]),
							fmt.Sprintf("%v", m["asset_type"]),
							fmt.Sprintf("%v", m["value"]),
							fmt.Sprintf("%v", m["risk"]),
							fmt.Sprintf("%v", m["status"]),
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

var asmAssetGetCmd = &cobra.Command{
	Use:   "get [asset-id]",
	Short: "Get asset details",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "asset ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/asm/assets/%s", args[0]), &resp); err != nil {
			return err
		}
		printGenericResponse(resp)
		return nil
	},
}

var asmSummaryCmd = &cobra.Command{
	Use:   "summary",
	Short: "Show ASM summary dashboard",
	RunE:  simpleGet("/api/asm/summary"),
}

var asmTypesCmd = &cobra.Command{
	Use:   "types",
	Short: "List asset types",
	RunE:  simpleGet("/api/asm/types"),
}

var asmRisksCmd = &cobra.Command{
	Use:   "risks",
	Short: "List risk levels",
	RunE:  simpleGet("/api/asm/risks"),
}

func init() {
	asmAssetsCmd.Flags().String("type", "", "Filter by asset type")
	asmAssetsCmd.Flags().String("risk", "", "Filter by risk level")
	asmAssetsCmd.Flags().String("status", "", "Filter by status")
	asmAssetsCmd.Flags().String("search", "", "Search term")
	asmAssetsCmd.Flags().Int("limit", 50, "Maximum assets to return")

	asmCmd.AddCommand(asmAssetsCmd)
	asmCmd.AddCommand(asmAssetGetCmd)
	asmCmd.AddCommand(asmSummaryCmd)
	asmCmd.AddCommand(asmTypesCmd)
	asmCmd.AddCommand(asmRisksCmd)
	rootCmd.AddCommand(asmCmd)
}
