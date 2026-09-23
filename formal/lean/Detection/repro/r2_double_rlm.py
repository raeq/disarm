"""Finding 2: the #741 number-run rule reads only the first RTL mark in a token, so a second
mark in front of the first hides the construction. The rendering is unchanged."""

import disarm

RLM, ALM = "\u200f", "\u061c"
for s in [
    f"Transfer {RLM}100 200 300 to Bob",
    f"Transfer {RLM}{RLM}100 200 300 to Bob",
    f"acct {ALM}4321-9876",
    f"acct {ALM}{ALM}4321-9876",
    f"acct a{RLM},{RLM}4321-9876",
]:
    print(ascii(s), disarm.inspect_anomalies(s).kinds)
