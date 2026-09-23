- **`demojize` named ill-formed sequences whole that `replace_emoji` treats as two
  emoji.** #1011 let a U+FE0F with no table edge continue the trie walk, so that
  fully qualified sequences are named whole. It applied anywhere, so
  `demojize("\U0001f1e7\ufe0f\U0001f1e6")` named a flag that
  `replace_emoji` counts as two emoji, and that the same letters with U+FE0E never
  formed; `\u2764\u200d\ufe0f\U0001f525` became `heart on fire`. The
  selector now continues the walk only straight after a pictograph, where the fully
  qualified form puts it. Found by running the Emoji model's differential test
  (`formal/lean/Emoji`) against #1011: on 219,724 inputs `replace_emoji` agrees with
  the model everywhere, and every remaining `demojize` difference is a deliberate one.
