package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// workspaceCmd uses the real API endpoints at /api/workspaces/*.
var workspaceCmd = &cobra.Command{
	Use:     "workspace",
	Aliases: []string{"workspaces", "ws"},
	Short:   "Manage workspaces",
}

var workspaceListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all workspaces",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp interface{}
		if err := c.Get("/api/workspaces", &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			if items, ok := resp.([]interface{}); ok {
				header := []string{"ID", "Name", "Targets", "Scans", "Created"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["id"]),
							fmt.Sprintf("%v", m["name"]),
							fmt.Sprintf("%v", m["target_count"]),
							fmt.Sprintf("%v", m["scan_count"]),
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

var workspaceGetCmd = &cobra.Command{
	Use:   "get [workspace-id]",
	Short: "Get workspace details",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "workspace ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/workspaces/%s", args[0]), &resp); err != nil {
			return err
		}
		printGenericResponse(resp)
		return nil
	},
}

var workspaceCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "Create a new workspace",
	RunE: func(cmd *cobra.Command, args []string) error {
		name, _ := cmd.Flags().GetString("name")
		description, _ := cmd.Flags().GetString("description")
		if name == "" {
			return fmt.Errorf("--name is required")
		}
		body := map[string]string{"name": name}
		if description != "" {
			body["description"] = description
		}
		payload, _ := json.Marshal(body)
		c := client.New()
		var resp map[string]interface{}
		if err := c.Post("/api/workspaces", bytes.NewReader(payload), &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			output.Success("Workspace created: %v", resp["id"])
		}
		return nil
	},
}

var workspaceDeleteCmd = &cobra.Command{
	Use:   "delete [workspace-id]",
	Short: "Delete a workspace",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "workspace ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Delete(fmt.Sprintf("/api/workspaces/%s", args[0]), nil); err != nil {
			return err
		}
		output.Success("Workspace %s deleted", args[0])
		return nil
	},
}

var workspaceSetActiveCmd = &cobra.Command{
	Use:   "set-active [workspace-id]",
	Short: "Set the active workspace",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "workspace ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Post(fmt.Sprintf("/api/workspaces/%s/set-active", args[0]), nil, nil); err != nil {
			return err
		}
		output.Success("Active workspace set to %s", args[0])
		return nil
	},
}

var workspaceTargetsCmd = &cobra.Command{
	Use:   "targets [workspace-id]",
	Short: "List targets in a workspace",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "workspace ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/workspaces/%s/targets", args[0]), &resp); err != nil {
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

var workspaceScansCmd = &cobra.Command{
	Use:   "scans [workspace-id]",
	Short: "List scans in a workspace",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "workspace ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/workspaces/%s/scans", args[0]), &resp); err != nil {
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

func init() {
	workspaceCreateCmd.Flags().StringP("name", "n", "", "Workspace name (required)")
	workspaceCreateCmd.Flags().StringP("description", "d", "", "Workspace description")

	workspaceCmd.AddCommand(workspaceListCmd)
	workspaceCmd.AddCommand(workspaceGetCmd)
	workspaceCmd.AddCommand(workspaceCreateCmd)
	workspaceCmd.AddCommand(workspaceDeleteCmd)
	workspaceCmd.AddCommand(workspaceSetActiveCmd)
	workspaceCmd.AddCommand(workspaceTargetsCmd)
	workspaceCmd.AddCommand(workspaceScansCmd)
	rootCmd.AddCommand(workspaceCmd)
}
