#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW_FILE="${ROOT_DIR}/.github/workflows/release.yml"
LOG_FILE="${ROOT_DIR}/release-workflow-check.log"

: > "${LOG_FILE}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI not found. Run this script where Docker is available." |
    tee -a "${LOG_FILE}" >&2
  exit 127
fi

if [[ ! -f "${WORKFLOW_FILE}" ]]; then
  echo "Release workflow not found: ${WORKFLOW_FILE}" |
    tee -a "${LOG_FILE}" >&2
  exit 1
fi

RUBY_CHECK="$(cat <<'RUBY'
require "yaml"

def mapping_value(mapping, key)
  return unless mapping.is_a?(Psych::Nodes::Mapping)

  mapping.children.each_slice(2) do |key_node, value_node|
    return value_node if key_node.is_a?(Psych::Nodes::Scalar) && key_node.value == key
  end
  nil
end

def scalar_value(node)
  node.value if node.is_a?(Psych::Nodes::Scalar)
end

workflow = YAML.parse_file(ARGV.fetch(0)).root
release = mapping_value(mapping_value(workflow, "on"), "release")
types = mapping_value(release, "types")
jobs = mapping_value(workflow, "jobs")
package_job = mapping_value(jobs, "package")
steps = mapping_value(package_job, "steps")
raise "Expected release trigger for published releases" unless
  types.is_a?(Psych::Nodes::Sequence) &&
  types.children.any? { |node| scalar_value(node) == "published" }
raise "Expected package job steps" unless steps.is_a?(Psych::Nodes::Sequence)

step_values = steps.children.map do |step|
  {
    "uses" => scalar_value(mapping_value(step, "uses")),
    "run" => scalar_value(mapping_value(step, "run")),
    "files" => scalar_value(mapping_value(mapping_value(step, "with"), "files"))
  }
end
checkout = step_values.any? { |step| step["uses"]&.start_with?("actions/checkout@") }
packaging = step_values.any? do |step|
  step["run"]&.include?("test -f NexusArchiveStateTool/__init__.py") &&
    step["run"]&.include?("zip -r NexusArchiveStateTool.zip NexusArchiveStateTool")
end
upload = step_values.any? do |step|
  step["uses"]&.start_with?("softprops/action-gh-release@") &&
    step["files"] == "NexusArchiveStateTool.zip"
end
raise "Missing checkout step" unless checkout
raise "Missing plugin ZIP packaging step" unless packaging
raise "Missing GitHub Release ZIP upload step" unless upload

puts "PASS: workflow parses and packages/uploads NexusArchiveStateTool.zip on published releases"
RUBY
)"

if docker run --rm -i \
  --mount "type=bind,src=${WORKFLOW_FILE},dst=/workspace/release.yml,readonly" \
  -w /workspace \
  ruby:3.3-alpine ruby -e "${RUBY_CHECK}" /workspace/release.yml 2>&1 |
  tee "${LOG_FILE}"
then
  printf 'Validation passed. Log: %s\n' "${LOG_FILE}" | tee -a "${LOG_FILE}"
else
  status=$?
  printf 'Validation failed with exit code %s. Log: %s\n' "${status}" "${LOG_FILE}" |
    tee -a "${LOG_FILE}" >&2
  exit "${status}"
fi
