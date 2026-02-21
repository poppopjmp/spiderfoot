// Package cmd provides the root Cobra command and persistent flags for the SpiderFoot CLI.
package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var version = "6.0.0"

const defaultAddr = "http://127.0.0.1:8001"

var cfgFile string

// rootCmd is the top-level command.
var rootCmd = &cobra.Command{
	Use:   "sf",
	Short: "SpiderFoot CLI — OSINT automation platform",
	Long: `SpiderFoot CLI is a cross-platform command-line client for the SpiderFoot
REST API. It provides scan management, module listing, data export, schedule
management, and health checks.

Configure connection parameters via flags, environment variables, or a
~/.spiderfoot.yaml config file.`,
}

func Execute() {
	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func init() {
	cobra.OnInitialize(initConfig)

	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default $HOME/.spiderfoot.yaml)")
	rootCmd.PersistentFlags().String("server", defaultAddr, "SpiderFoot API server URL")
	rootCmd.PersistentFlags().String("api-key", "", "API key for authentication")
	rootCmd.PersistentFlags().String("token", "", "JWT bearer token")
	rootCmd.PersistentFlags().StringP("output", "o", "table", "Output format: table, json, csv")
	rootCmd.PersistentFlags().Bool("no-color", false, "Disable colored output")
	rootCmd.PersistentFlags().Bool("insecure", false, "Skip TLS certificate verification")

	// Bind flags to viper keys
	viper.BindPFlag("server", rootCmd.PersistentFlags().Lookup("server"))
	viper.BindPFlag("api_key", rootCmd.PersistentFlags().Lookup("api-key"))
	viper.BindPFlag("token", rootCmd.PersistentFlags().Lookup("token"))
	viper.BindPFlag("output", rootCmd.PersistentFlags().Lookup("output"))
	viper.BindPFlag("no_color", rootCmd.PersistentFlags().Lookup("no-color"))
	viper.BindPFlag("insecure", rootCmd.PersistentFlags().Lookup("insecure"))

	// Environment variable bindings
	viper.SetEnvPrefix("SF")
	viper.AutomaticEnv()
}

func initConfig() {
	if cfgFile != "" {
		viper.SetConfigFile(cfgFile)
	} else {
		home, err := os.UserHomeDir()
		if err != nil {
			return
		}
		viper.AddConfigPath(home)
		viper.SetConfigType("yaml")
		viper.SetConfigName(".spiderfoot")
	}

	// Silently read config if it exists
	_ = viper.ReadInConfig()
}
