package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
	"github.com/spiderfoot/spiderfoot-cli/internal/client"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

var configCmd = &cobra.Command{
	Use:   "config",
	Short: "View or modify CLI and server configuration",
}

// --- Local CLI config subcommands ---

var configShowCmd = &cobra.Command{
	Use:   "show",
	Short: "Show current CLI configuration",
	Run: func(cmd *cobra.Command, args []string) {
		keys := []string{"server", "api_key", "token", "output", "no_color", "insecure"}
		switch output.Current() {
		case output.JSON:
			m := make(map[string]interface{})
			for _, k := range keys {
				m[k] = viper.Get(k)
			}
			output.PrintJSON(m)
		default:
			for _, k := range keys {
				val := viper.GetString(k)
				if k == "api_key" || k == "token" {
					if len(val) > 8 {
						val = val[:4] + "****" + val[len(val)-4:]
					}
				}
				fmt.Printf("  %-12s %s\n", k+":", val)
			}
		}
	},
}

var configSetCmd = &cobra.Command{
	Use:   "set [key] [value]",
	Short: "Set a CLI configuration value",
	Args:  cobra.ExactArgs(2),
	RunE: func(cmd *cobra.Command, args []string) error {
		key, value := args[0], args[1]
		viper.Set(key, value)

		configFile := viper.ConfigFileUsed()
		if configFile == "" {
			home, _ := cmd.Root().PersistentFlags().GetString("config")
			if home == "" {
				return fmt.Errorf("no config file found — use --config flag or create ~/.spiderfoot.yaml")
			}
			configFile = home
		}

		if err := viper.WriteConfigAs(configFile); err != nil {
			return fmt.Errorf("writing config: %w", err)
		}
		output.Success("Set %s=%s in %s", key, value, configFile)
		return nil
	},
}

// --- Remote server config subcommands (via /api/config/*) ---

var configRemoteCmd = &cobra.Command{
	Use:   "remote",
	Short: "View and manage remote server configuration",
}

var configRemoteShowCmd = &cobra.Command{
	Use:   "show",
	Short: "Show server configuration",
	RunE:  simpleGet("/api/config"),
}

var configRemoteModulesCmd = &cobra.Command{
	Use:   "modules",
	Short: "Show module configuration",
	RunE:  simpleGet("/api/config/modules"),
}

var configRemoteKeysCmd = &cobra.Command{
	Use:   "api-keys",
	Short: "List configured API keys on the server",
	RunE:  simpleGet("/api/config/api-keys"),
}

var configRemoteCredentialsCmd = &cobra.Command{
	Use:   "credentials",
	Short: "List configured credentials on the server",
	RunE:  simpleGet("/api/config/credentials"),
}

var configRemoteRateLimitsCmd = &cobra.Command{
	Use:   "rate-limits",
	Short: "Show rate limit configuration",
	RunE:  simpleGet("/api/config/rate-limits"),
}

var configRemoteReloadCmd = &cobra.Command{
	Use:   "reload",
	Short: "Reload server configuration from disk",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.New()
		if err := c.Post("/api/config/reload", nil, nil); err != nil {
			return err
		}
		output.Success("Server configuration reloaded")
		return nil
	},
}

var configRemoteValidateCmd = &cobra.Command{
	Use:   "validate",
	Short: "Validate current server configuration",
	RunE:  simpleGet("/api/config/validate"),
}

var configRemoteHistoryCmd = &cobra.Command{
	Use:   "history",
	Short: "Show configuration change history",
	RunE:  simpleGet("/api/config/history"),
}

var configRemoteSourcesCmd = &cobra.Command{
	Use:   "sources",
	Short: "List configured data sources",
	RunE:  simpleGet("/api/config/sources"),
}

var configRemoteEnvironmentCmd = &cobra.Command{
	Use:   "environment",
	Short: "Show server environment information",
	RunE:  simpleGet("/api/config/environment"),
}

func init() {
	configRemoteCmd.AddCommand(configRemoteShowCmd)
	configRemoteCmd.AddCommand(configRemoteModulesCmd)
	configRemoteCmd.AddCommand(configRemoteKeysCmd)
	configRemoteCmd.AddCommand(configRemoteCredentialsCmd)
	configRemoteCmd.AddCommand(configRemoteRateLimitsCmd)
	configRemoteCmd.AddCommand(configRemoteReloadCmd)
	configRemoteCmd.AddCommand(configRemoteValidateCmd)
	configRemoteCmd.AddCommand(configRemoteHistoryCmd)
	configRemoteCmd.AddCommand(configRemoteSourcesCmd)
	configRemoteCmd.AddCommand(configRemoteEnvironmentCmd)

	configCmd.AddCommand(configShowCmd)
	configCmd.AddCommand(configSetCmd)
	configCmd.AddCommand(configRemoteCmd)
	rootCmd.AddCommand(configCmd)
}
