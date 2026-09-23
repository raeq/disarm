import Lake
open Lake DSL

package confusables where
  -- Compile the model to native code so `native_decide` checks run at native speed.
  precompileModules := true

@[default_target]
lean_lib Confusables where
  roots := #[`Confusables]

lean_exe confmodel where
  root := `Main

lean_exe cex where
  root := `Cex
