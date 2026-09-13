{#-
  disarm's changelog template.

  A fragment is written exactly as it should appear in CHANGELOG.md — leading
  bullet, bold lead-in, indented continuation lines and all. This template
  reproduces it verbatim, so `towncrier build` is an append rather than a
  reformat, and the fragment reviewed in a pull request is the text that ships.

  The stock markdown template cannot do that. It prefixes every entry with
  "- " whatever `all_bullets` says, which doubles the bullet our entries
  already carry; it appends its own "(#123)" suffix, which our entries also
  already carry, in the place the prose wants it; and it derives the heading
  depth from `header_prefix`, landing these at "####" where every release
  below them uses "###".

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
