import Sanitizers.Filename
import Sanitizers.Slug
import Sanitizers.Unique
import Sanitizers.LogInjection
import Sanitizers.Encoders
import Sanitizers.EditDistance

/-!
# Documented examples, replayed on the models

Every ASCII example with an exact expected value in the docs, docstrings and unit tests
of the functions modelled here, checked by the kernel (`decide`). Sources:
`docs/user-guide/filenames.md`, `docs/user-guide/slugification.md`, `docs/limitations.md`,
the `_api.py` docstrings, and the `src/filename.rs`, `src/log_injection.rs`,
`src/encoders.rs` and `src/utils.rs` tests.
-/

namespace Sanitizers.Vectors

open Filename in
def sf (s : String) (sep := "_") (ml := 255) (p := Platform.universal) (pe := true) : List Char :=
  sanitize s.toList sep.toList ml p pe

example : sf "my<file>:v2.txt" = "my_file_v2.txt".toList := by decide
example : sf "../../../etc/passwd" = "_.etcpasswd".toList := by decide
example : sf "CON.txt" = "_CON.txt".toList := by decide
example : sf "CON.txt" (p := .windows) = "_CON.txt".toList := by decide
example : sf "hello:world" (sep := "-") = "hello-world".toList := by decide
example : sf "my:file?.txt" = "my_file.txt".toList := by decide
example : sf "my:file?.txt" (p := .posix) = "my:file?.txt".toList := by decide
example : sf "long_name.pdf" (ml := 12) = "long_nam.pdf".toList := by decide
example : sf "long_name.pdf" (ml := 12) (pe := false) = "long_name.pd".toList := by decide
example : sf "My Report (final).pdf" = "My_Report_(final).pdf".toList := by decide
example : sf "my<file>.txt" (ml := 100) = "my_file.txt".toList := by decide
example : sf "../etc" = "_etc".toList := by decide
example : sf "..%2Fetc" = "%2Fetc".toList := by decide
example : sf "0*.0" = "0.0".toList := by decide
example : sf "a*.b" = "a.b".toList := by decide
example : sf "a_.b" = "a.b".toList := by decide
example : sf "*.b." = "b".toList := by decide
example : sf "a*.b." = sf "a_.b" := by decide
example : sf "AUX.py" (ml := 7) = "_AUX.py".toList := by decide
example : sf ".bashrc" = "bashrc".toList := by decide
example : sf "." = "_".toList := by decide
example : sf ".." = "_".toList := by decide
example : sf "" = "_".toList := by decide
example : sf "     " = "_".toList := by decide
example : sf "/////" = "_".toList := by decide
example : sf "a:b" (p := .posix) = "a:b".toList := by decide

open Slug in
def sl (s : String) (sep := "-") (ml := 0) (wb := false) (stop : List String := []) : List Char :=
  slugify { sep := sep.toList, lowercase := true, maxLen := ml, wordBoundary := wb,
            saveOrder := false, stopwords := stop.map String.toList } s.toList

example : sl "Hello World!" = "hello-world".toList := by decide
example : sl "My Title" (sep := "_") = "my_title".toList := by decide
example : sl "The Big Fox" (stop := ["the"]) = "big-fox".toList := by decide
example : sl "Very Long Title Here" (ml := 10) (wb := true) = "very-long".toList := by decide
example : sl "Hello World" (sep := "_") = "hello_world".toList := by decide

open Unique in
example :
    run { sep := ['-'], lowercase := true, maxLen := 0, wordBoundary := false, saveOrder := false,
          stopwords := [] } 10000 ["My Post".toList, "My Post".toList, "My Post".toList] =
      [.ok "my-post".toList, .ok "my-post-1".toList, .ok "my-post-2".toList] := by decide

open Log in
example : strip [Char.ofNat 0xFFFD] false ['a', '\r', '\n', 'b', Char.ofNat 0, 'c'] =
    ['a', Char.ofNat 0xFFFD, Char.ofNat 0xFFFD, 'b', Char.ofNat 0xFFFD, 'c'] := by decide
open Log in
example : strip [Char.ofNat 0xFFFD] false (Char.ofNat 0x1B :: "[31mred".toList) =
    Char.ofNat 0xFFFD :: "[31mred".toList := by decide
open Log in
example : strip [Char.ofNat 0xFFFD] true ['a', '\t', 'b'] = ['a', '\t', 'b'] := by decide
open Log in
example : validRep ['\r'] false = false := by decide

open Enc in
example : escapeHtml "<b>a & b</b>".toList = "&lt;b&gt;a &amp; b&lt;/b&gt;".toList := by decide
open Enc in
example : escapeHtml "it's".toList = "it&#x27;s".toList := by decide
open Enc in
example : escapeHtml "&amp;".toList = "&amp;amp;".toList := by decide

open Enc in
def pe (c : Component) (s : String) : List Nat := pctEncode c (s.toList.map Char.toNat)

open Enc in
example : pe .query "a b&c" = "a%20b%26c".toList.map Char.toNat := by decide
open Enc in
example : pe .form "a b&c" = "a+b%26c".toList.map Char.toNat := by decide
open Enc in
example : pe .segment "a/b" = "a%2Fb".toList.map Char.toNat := by decide
open Enc in
example : pe .path "a/b" = "a/b".toList.map Char.toNat := by decide
open Enc in
example : pe .query "a&b=c+d" = "a%26b%3Dc%2Bd".toList.map Char.toNat := by decide
open Enc in
example : pe .form "a b+c" = "a+b%2Bc".toList.map Char.toNat := by decide
open Enc in
example : pctEncode .query [0xC3, 0xA9] = "%C3%A9".toList.map Char.toNat := by decide

open Dist in
example : dp "paypa1".toList "paypal".toList = 1 := by decide
open Dist in
example : dp "stripe".toList "stripe".toList = 0 := by decide
open Dist in
example : dp "xx".toList "paypal".toList = 6 := by decide
open Dist in
example : dp "kitten".toList "sitting".toList = 3 := by decide
open Dist in
example : dp "".toList "abc".toList = 3 := by decide
open Dist in
example : nearest "paypa1".toList (["paypal", "stripe", "admin"].map String.toList) 1 =
    some ("paypal".toList, 1) := by decide
open Dist in
example : nearest "admin".toList (["paypal", "stripe", "admin"].map String.toList) 1 =
    some ("admin".toList, 0) := by decide
open Dist in
set_option maxRecDepth 10000 in
example : nearest "something-else".toList (["paypal", "stripe", "admin"].map String.toList) 1 =
    none := by decide

end Sanitizers.Vectors
