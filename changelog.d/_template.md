{#-
  disarm's changelog template.

  A fragment is written exactly as it should appear in CHANGELOG.md — leading
  bullet, bold lead-in, indented continuation lines and all. This template
  reproduces it verbatim, so `towncrier build` is an append rather than a
  reformat, and the fragment reviewed in a pull request is the text that ships.

  The stock markdown template cannot do that. It prefixes every entry with
  "- " whatever `all_bullets` says, which doubles the bullet our entries
  already carry, and it leaves an extra blank line before the previous
  release. It would also append a "(#123)" suffix after the numbers our
  entries already carry; `issue_format = ""` in pyproject.toml empties that,
  and this template never renders issue references at all. Re-wrapping at 79
  columns is a separate switch, `wrap`, which is false by default and stated
  as false in pyproject.toml. (The stock headings are not the problem: they
  follow `title_format`, and land at "###" as these do.)
  tests/test_changelog_fragments.py compares the assembled file whole, so
  removing the `template =` line, or setting `wrap = true`, fails it.

  disarm files no fragment under a towncrier *section*, so the section loop
  runs exactly once, over the unnamed section, and only the category heading
  is written.
-#}
{%- set newline = "\n" -%}
{%- for section, _ in sections.items() %}
    {%- for category, val in definitions.items() if category in sections[section] %}
        {{- newline }}
        {{- "### " ~ definitions[category]['name'] ~ newline }}
        {%- for text, values in sections[section][category].items() %}
            {{- newline }}
            {{- text ~ newline }}
        {%- endfor %}
    {%- endfor %}
{%- endfor %}
{{- newline -}}
