package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
	"github.com/spiderfoot/spiderfoot-cli/internal/output"
)

var configCmd = &cobra.Command{
	Use:   "config",
	Short: "View or modify CLI configuration",
}

var configShowCmd = &cobra.Command{
	Use:   "show",
	Short: "Show current configuration",
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
	Short: "Set a configuration value",
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

func init() {
	configCmd.AddCommand(configShowCmd)
	configCmd.AddCommand(configSetCmd)
	rootCmd.AddCommand(configCmd)
}
