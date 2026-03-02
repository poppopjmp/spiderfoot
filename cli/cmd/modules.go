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
	Short: "List and inspect available modules",
}

var modulesListCmd = &cobra.Command{
	Use:   "list",
	Short: "List available modules",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		filter, _ := cmd.Flags().GetString("filter")

		path := "/api/data/modules"
		params := url.Values{}
		if filter != "" {
			params.Set("type", filter)
		}
		if q := params.Encode(); q != "" {
			path += "?" + q
		}

		var modules []moduleInfo
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

var modulesGetCmd = &cobra.Command{
	Use:   "get [module-name]",
	Short: "Get details for a specific module",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/data/modules/%s", url.PathEscape(args[0])), &resp); err != nil {
			return err
		}
		printGenericResponse(resp)
		return nil
	},
}

var modulesStatsCmd = &cobra.Command{
	Use:   "stats",
	Short: "Show module statistics",
	RunE:  simpleGet("/api/data/modules/stats"),
}

var modulesCategoriesCmd = &cobra.Command{
	Use:   "categories",
	Short: "List module categories",
	RunE:  simpleGet("/api/data/categories"),
}

var modulesTypesCmd = &cobra.Command{
	Use:   "types",
	Short: "List event types produced by modules",
	RunE:  simpleGet("/api/data/types"),
}

var modulesEnableCmd = &cobra.Command{
	Use:   "enable [module-name]",
	Short: "Enable a module",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		if err := c.Post(fmt.Sprintf("/api/data/modules/%s/enable", url.PathEscape(args[0])), nil, nil); err != nil {
			return err
		}
		output.Success("Module %s enabled", args[0])
		return nil
	},
}

var modulesDisableCmd = &cobra.Command{
	Use:   "disable [module-name]",
	Short: "Disable a module",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		if err := c.Post(fmt.Sprintf("/api/data/modules/%s/disable", url.PathEscape(args[0])), nil, nil); err != nil {
			return err
		}
		output.Success("Module %s disabled", args[0])
		return nil
	},
}

func init() {
	modulesListCmd.Flags().StringP("filter", "f", "", "Filter by module type")

	modulesCmd.AddCommand(modulesListCmd)
	modulesCmd.AddCommand(modulesGetCmd)
	modulesCmd.AddCommand(modulesStatsCmd)
	modulesCmd.AddCommand(modulesCategoriesCmd)
	modulesCmd.AddCommand(modulesTypesCmd)
	modulesCmd.AddCommand(modulesEnableCmd)
	modulesCmd.AddCommand(modulesDisableCmd)
	rootCmd.AddCommand(modulesCmd)
}
