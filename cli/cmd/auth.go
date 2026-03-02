package cmd

import (
	"bytes"
	"encoding/json"
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

// authCmd uses the real API endpoints at /api/auth/*.
var authCmd = &cobra.Command{
	Use:   "auth",
	Short: "Authentication and user management",
}

var authLoginCmd = &cobra.Command{
	Use:   "login",
	Short: "Log in and obtain a JWT token",
	RunE: func(cmd *cobra.Command, args []string) error {
		username, _ := cmd.Flags().GetString("username")
		password, _ := cmd.Flags().GetString("password")
		if username == "" || password == "" {
			return fmt.Errorf("--username and --password are required")
		}
		body := map[string]string{"username": username, "password": password}
		payload, _ := json.Marshal(body)

		c := client.New()
		var resp map[string]interface{}
		if err := c.Post("/api/auth/login", bytes.NewReader(payload), &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			if token, ok := resp["access_token"].(string); ok {
				output.Success("Login successful")
				fmt.Printf("Token: %s\n", token)
				fmt.Println("Set via: sf config set token <token>")
			} else {
				printGenericResponse(resp)
			}
		}
		return nil
	},
}

var authStatusCmd = &cobra.Command{
	Use:   "status",
	Short: "Check authentication status",
	RunE:  simpleGet("/api/auth/status"),
}

var authMeCmd = &cobra.Command{
	Use:   "me",
	Short: "Show current user info",
	RunE:  simpleGet("/api/auth/me"),
}

var authUsersCmd = &cobra.Command{
	Use:   "users",
	Short: "List users",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		limit, _ := cmd.Flags().GetInt("limit")
		path := fmt.Sprintf("/api/auth/users?limit=%d", limit)

		var resp interface{}
		if err := c.Get(path, &resp); err != nil {
			return err
		}
		switch output.Current() {
		case output.JSON:
			output.PrintJSON(resp)
		default:
			if items, ok := resp.([]interface{}); ok {
				header := []string{"ID", "Username", "Role", "Status"}
				rows := make([][]string, 0, len(items))
				for _, item := range items {
					if m, ok := item.(map[string]interface{}); ok {
						rows = append(rows, []string{
							fmt.Sprintf("%v", m["id"]),
							fmt.Sprintf("%v", m["username"]),
							fmt.Sprintf("%v", m["role"]),
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

var authLogoutCmd = &cobra.Command{
	Use:   "logout",
	Short: "Log out and invalidate current session",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		if err := c.Post("/api/auth/logout", nil, nil); err != nil {
			return err
		}
		output.Success("Logged out")
		return nil
	},
}

func init() {
	authLoginCmd.Flags().StringP("username", "u", "", "Username (required)")
	authLoginCmd.Flags().StringP("password", "p", "", "Password (required)")
	authUsersCmd.Flags().Int("limit", 50, "Maximum users to return")

	authCmd.AddCommand(authLoginCmd)
	authCmd.AddCommand(authStatusCmd)
	authCmd.AddCommand(authMeCmd)
	authCmd.AddCommand(authUsersCmd)
	authCmd.AddCommand(authLogoutCmd)
	rootCmd.AddCommand(authCmd)
}
