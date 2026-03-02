package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/url"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// tagsCmd uses the real API endpoints at /api/tags/* and /api/groups/*.
var tagsCmd = &cobra.Command{
	Use:   "tags",
	Short: "Manage tags and groups",
}

var tagsListCmd = &cobra.Command{
	Use:   "list",
	Short: "List tags",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		parent, _ := cmd.Flags().GetString("parent")
		params := url.Values{}
		if parent != "" {
			params.Set("parent", parent)
		}
		path := "/api/tags"
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
				header := []string{"ID", "Name", "Color", "Parent"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["tag_id"]),
							fmt.Sprintf("%v", m["name"]),
							fmt.Sprintf("%v", m["color"]),
							fmt.Sprintf("%v", m["parent"]),
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

var tagsTreeCmd = &cobra.Command{
	Use:   "tree",
	Short: "Show tag hierarchy tree",
	RunE:  simpleGet("/api/tags/tree"),
}

var tagsCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "Create a new tag",
	RunE: func(cmd *cobra.Command, args []string) error {
		name, _ := cmd.Flags().GetString("name")
		color, _ := cmd.Flags().GetString("color")
		if name == "" {
			return fmt.Errorf("--name is required")
		}
		body := map[string]string{"name": name}
		if color != "" {
			body["color"] = color
		}
		payload, _ := json.Marshal(body)

		c := client.New()
		var resp map[string]interface{}
		if err := c.Post("/api/tags", bytes.NewReader(payload), &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			output.Success("Tag created: %v", resp["tag_id"])
		}
		return nil
	},
}

var tagsDeleteCmd = &cobra.Command{
	Use:   "delete [tag-id]",
	Short: "Delete a tag",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "tag ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Delete(fmt.Sprintf("/api/tags/%s", args[0]), nil); err != nil {
			return err
		}
		output.Success("Tag %s deleted", args[0])
		return nil
	},
}

var tagsStatsCmd = &cobra.Command{
	Use:   "stats",
	Short: "Show tag usage statistics",
	RunE:  simpleGet("/api/tags/stats"),
}

var tagsColorsCmd = &cobra.Command{
	Use:   "colors",
	Short: "List available tag colors",
	RunE:  simpleGet("/api/tags/colors"),
}

func init() {
	tagsListCmd.Flags().String("parent", "", "Filter by parent tag ID")
	tagsCreateCmd.Flags().StringP("name", "n", "", "Tag name (required)")
	tagsCreateCmd.Flags().String("color", "", "Tag color")

	tagsCmd.AddCommand(tagsListCmd)
	tagsCmd.AddCommand(tagsTreeCmd)
	tagsCmd.AddCommand(tagsCreateCmd)
	tagsCmd.AddCommand(tagsDeleteCmd)
	tagsCmd.AddCommand(tagsStatsCmd)
	tagsCmd.AddCommand(tagsColorsCmd)
	rootCmd.AddCommand(tagsCmd)
}
