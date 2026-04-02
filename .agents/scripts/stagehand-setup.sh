#!/usr/bin/env bash
set -euo pipefail

# Stagehand Setup Script for AI DevOps Framework
# Comprehensive setup and configuration for Stagehand AI browser automation

# Source shared constants
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit
source "${SCRIPT_DIR}/../../.agents/scripts/shared-constants.sh"

# Print functions
# Stagehand configuration
readonly STAGEHAND_CONFIG_DIR="${HOME}/.aidevops/stagehand"
readonly STAGEHAND_EXAMPLES_DIR="${STAGEHAND_CONFIG_DIR}/examples"
readonly STAGEHAND_TEMPLATES_DIR="${STAGEHAND_CONFIG_DIR}/templates"

# Create advanced example scripts
create_advanced_examples() {
	print_info "Creating advanced Stagehand example scripts..."

	mkdir -p "$STAGEHAND_EXAMPLES_DIR"
	mkdir -p "$STAGEHAND_TEMPLATES_DIR"

	# E-commerce automation example
	cat "$SCRIPT_DIR/stagehand-ecommerce-automation.js.template" >"${STAGEHAND_EXAMPLES_DIR}/ecommerce-automation.js"

	# Social media automation example
	cat "$SCRIPT_DIR/stagehand-social-media-automation.js.template" >"${STAGEHAND_EXAMPLES_DIR}/social-media-automation.js"

	# Web scraping template
	cat "$SCRIPT_DIR/stagehand-web-scraping-template.js.template" >"${STAGEHAND_TEMPLATES_DIR}/web-scraping-template.js"

	print_success "Created advanced Stagehand examples"
	return 0
}

# Create package.json template
create_package_template() {
    local package_file="${STAGEHAND_TEMPLATES_DIR}/package.json"
    cat "$SCRIPT_DIR/stagehand-package.json.template" > "$package_file"
    print_success "Created package.json template"
    return 0
}

# Setup MCP integration for Stagehand
setup_mcp_integration() {
    print_info "Setting up Stagehand MCP integration..."
    
    # Create MCP configuration for Stagehand
    local mcp_config="${HOME}/.aidevops/mcp/stagehand-config.json"
    mkdir -p "$(dirname "$mcp_config")"
    cat "$SCRIPT_DIR/stagehand-mcp-config.json.template" > "$mcp_config"
    print_success "Created Stagehand MCP configuration"
    return 0
}

EOF

	print_success "Created package.json template"
	return 0
}

# Setup MCP integration for Stagehand
setup_mcp_integration() {
	print_info "Setting up Stagehand MCP integration..."

	# Create MCP configuration for Stagehand
	local mcp_config="${HOME}/.aidevops/mcp/stagehand-config.json"
	mkdir -p "$(dirname "$mcp_config")"

	cat >"$mcp_config" <<'EOF'
{
  "mcpServers": {
    "stagehand": {
      "command": "node",
      "args": [
        "-e",
        "const { Stagehand } = require('@browserbasehq/stagehand'); console.log('Stagehand MCP Server Ready');"
      ],
      "env": {
        "STAGEHAND_ENV": "LOCAL",
        "STAGEHAND_VERBOSE": "1"
      }
    }
  }
    return 0
}
EOF

	print_success "Created Stagehand MCP configuration"
	return 0
}

# Main setup function
main() {
	local command="${1:-setup}"

	case "$command" in
	"setup")
		print_info "Setting up Stagehand advanced configuration..."
		create_advanced_examples
		create_package_template
		setup_mcp_integration
		print_success "Stagehand advanced setup completed!"
		print_info "Next steps:"
		print_info "1. Run: bash .agents/scripts/stagehand-helper.sh install"
		print_info "2. Configure API keys in ~/.aidevops/stagehand/.env"
		print_info "3. Try examples: cd ~/.aidevops/stagehand && npm run search-products" || exit
		;;
	"examples")
		create_advanced_examples
		;;
	"mcp")
		setup_mcp_integration
		;;
	"help")
		cat <<EOF
Stagehand Setup Script

USAGE:
    $0 [COMMAND]

COMMANDS:
    setup       Complete advanced setup (default)
    examples    Create example scripts only
    mcp         Setup MCP integration only
    help        Show this help

EOF
		;;
	*)
		print_error "$ERROR_UNKNOWN_COMMAND $command"
		return 1
		;;
	esac

	return 0
}

# Execute main function
main "$@"
