package cmd

import (
	"fmt"
	"net/url"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

type moduleInfo struct {
	Name        string   `json:"name"`
	Type        string   `json:"type"`
	Description string   `json:"descr"`
	Provides    []string `json:"provides"`
	Consumes    []string `json:"consumes"`
	Categories  []string `json:"categories"`
	APIKeyReq   bool     `json:"apiKeyRequired"`
}

var modulesCmd = &cobra.Command{
	Use:   "modules",
	Short: "List available modules",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		filter, _ := cmd.Flags().GetString("filter")

		var modules []moduleInfo
		path := "/api/modules"
		if filter != "" {
			path += "?type=" + url.QueryEscape(filter)
		}
		if err := c.Get(path, &modules); err != nil {
			return err
		}

		switch output.Current() {
		case output.JSON:
			output.PrintJSON(modules)
		case output.CSV:
			header := []string{"Name", "Type", "Description", "API Key"}
			rows := make([][]string, 0, len(modules))
			for _, m := range modules {
				rows = append(rows, []string{m.Name, m.Type, m.Description, fmt.Sprintf("%v", m.APIKeyReq)})
			}
			output.PrintCSV(header, rows)
		default:
			header := []string{"Name", "Type", "Description", "API Key"}
			rows := make([][]string, 0, len(modules))
			for _, m := range modules {
				desc := m.Description
				if len(desc) > 60 {
					desc = desc[:57] + "..."
				}
				apiKey := "no"
				if m.APIKeyReq {
					apiKey = "yes"
				}
				rows = append(rows, []string{m.Name, m.Type, desc, apiKey})
			}
			output.PrintTable(header, rows)
			fmt.Printf("\nTotal: %d modules\n", len(modules))
		}
		return nil
	},
}

func init() {
	modulesCmd.Flags().StringP("filter", "f", "", "Filter by module type")
	rootCmd.AddCommand(modulesCmd)
}
