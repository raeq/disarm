# frozen_string_literal: true

# rb-sys builds the Cargo cdylib in `ext/disarm/` into the loadable extension.
require "mkmf"
require "rb_sys/mkmf"

create_rust_makefile("disarm/disarm")
