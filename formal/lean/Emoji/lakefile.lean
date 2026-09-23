import Lake
open Lake DSL

package emoji where
  -- Compile the model to native code so `native_decide` checks run at native speed.
  precompileModules := true

@[default_target]
lean_lib Emoji where
  roots := #[`Emoji]

lean_exe emojimodel where
  root := `Main

lean_exe cex where
  root := `Cex
