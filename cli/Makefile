# SpiderFoot CLI — Cross-platform build targets
# Requires Go 1.22+

APP_NAME  := sf
VERSION   := $(shell cat ../VERSION 2>/dev/null || echo 6.0.0)
BUILD_DIR := build
GOFLAGS   := -trimpath
LDFLAGS   := -s -w -X github.com/spiderfoot/spiderfoot-cli/cmd.version=$(VERSION)

.PHONY: all clean build linux darwin windows test fmt

all: linux darwin windows

build:
	go build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(BUILD_DIR)/$(APP_NAME) .

# Linux targets
linux: linux-amd64 linux-arm64

linux-amd64:
	GOOS=linux GOARCH=amd64 go build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(BUILD_DIR)/$(APP_NAME)-linux-amd64 .

linux-arm64:
	GOOS=linux GOARCH=arm64 go build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(BUILD_DIR)/$(APP_NAME)-linux-arm64 .

# macOS targets
darwin: darwin-amd64 darwin-arm64

darwin-amd64:
	GOOS=darwin GOARCH=amd64 go build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(BUILD_DIR)/$(APP_NAME)-darwin-amd64 .

darwin-arm64:
	GOOS=darwin GOARCH=arm64 go build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(BUILD_DIR)/$(APP_NAME)-darwin-arm64 .

# Windows targets
windows: windows-amd64 windows-arm64

windows-amd64:
	GOOS=windows GOARCH=amd64 go build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(BUILD_DIR)/$(APP_NAME)-windows-amd64.exe .

windows-arm64:
	GOOS=windows GOARCH=arm64 go build $(GOFLAGS) -ldflags "$(LDFLAGS)" -o $(BUILD_DIR)/$(APP_NAME)-windows-arm64.exe .

# Test
test:
	go test ./...

# Format
fmt:
	gofmt -w .

# Clean
clean:
	rm -rf $(BUILD_DIR)
