# Ruby parity driver (local only). Reads a JSON job, calls each op on each
# input through the Ruby binding, prints a JSON results map.
# Usage: ruby ruby_driver.rb <jobfile.json> <repoRoot>
# job: { "inputs": [str, ...], "ops": [[opId, rubyName], ...] }
# out: { opId: [ {"v": value} | {"e": "message"} , ... ] }
require "json"

jobfile = ARGV[0]
root = ARGV[1] || File.join(__dir__, "..", "..")
$LOAD_PATH.unshift(File.join(root, "bindings", "ruby", "lib"))
require "disarm"

job = JSON.parse(File.read(jobfile))
out = {}
job["ops"].each do |op_id, ruby_name|
  out[op_id] = job["inputs"].map do |s|
    begin
      { "v" => Disarm.public_send(ruby_name, s) }
    rescue StandardError, ArgumentError => e
      { "e" => e.message.to_s[0, 100] }
    end
  end
end
STDOUT.write(JSON.generate(out))
