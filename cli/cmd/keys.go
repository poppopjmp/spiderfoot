package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// keysCmd uses the real API endpoints:
// GET    /api/keys           — list API keys
// POST   /api/keys           — create a key
// GET    /api/keys/{key_id}  — get key details
// PUT    /api/keys/{key_id}  — update key
// DELETE /api/keys/{key_id}  — delete key
// POST   /api/keys/{key_id}/revoke — revoke key
var keysCmd = &cobra.Command{
	Use:     "keys",
	Aliases: []string{"apikeys"},
	Short:   "Manage API keys",
}

var keysListCmd = &cobra.Command{
	Use:   "list",
	Short: "List API keys",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		var resp interface{}
		if err := c.Get("/api/keys", &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			if items, ok := resp.([]interface{}); ok {
				header := []string{"ID", "Name", "Created", "Status"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["id"]),
							fmt.Sprintf("%v", m["name"]),
							fmt.Sprintf("%v", m["created_at"]),
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

var keysCreateCmd = &cobra.Command{
	Use:   "create",
	Short: "Create a new API key",
	RunE: func(cmd *cobra.Command, args []string) error {
		name, _ := cmd.Flags().GetString("name")
		if name == "" {
			return fmt.Errorf("--name is required")
		}
		body := map[string]string{"name": name}
		payload, _ := json.Marshal(body)
		c := client.New()
		var resp interface{}
		if err := c.Post("/api/keys", bytes.NewReader(payload), &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			if m, ok := resp.(map[string]interface{}); ok {
				output.Success("API key created: %v", m["id"])
				if key, ok := m["key"].(string); ok {
					fmt.Printf("Key: %s\n", key)
					fmt.Println("⚠  Save this key — it won't be shown again.")
				}
			} else {
				printGenericResponse(resp)
			}
		}
		return nil
	},
}

var keysGetCmd = &cobra.Command{
	Use:   "get [key-id]",
	Short: "Get API key details",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "key ID"); err != nil {
			return err
		}
		c := client.New()
		var resp interface{}
		if err := c.Get(fmt.Sprintf("/api/keys/%s", args[0]), &resp); err != nil {
			return err
		}
		printGenericResponse(resp)
		return nil
	},
}

var keysDeleteCmd = &cobra.Command{
	Use:   "delete [key-id]",
	Short: "Delete an API key",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "key ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Delete(fmt.Sprintf("/api/keys/%s", args[0]), nil); err != nil {
			return err
		}
		output.Success("API key %s deleted", args[0])
		return nil
	},
}

var keysRevokeCmd = &cobra.Command{
	Use:   "revoke [key-id]",
	Short: "Revoke an API key",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := validateSafeID(args[0], "key ID"); err != nil {
			return err
		}
		c := client.New()
		if err := c.Post(fmt.Sprintf("/api/keys/%s/revoke", args[0]), nil, nil); err != nil {
			return err
		}
		output.Success("API key %s revoked", args[0])
		return nil
	},
}

func init() {
	keysCreateCmd.Flags().StringP("name", "n", "", "Key name (required)")

	keysCmd.AddCommand(keysListCmd)
	keysCmd.AddCommand(keysCreateCmd)
	keysCmd.AddCommand(keysGetCmd)
	keysCmd.AddCommand(keysDeleteCmd)
	keysCmd.AddCommand(keysRevokeCmd)
	rootCmd.AddCommand(keysCmd)
}
