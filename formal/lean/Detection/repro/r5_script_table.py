"""Finding 5: the block table gives a script to 70 Common/Inherited code points, and
`is_mixed_script` reads `Script` where UTS #39 section 5.1 reads `Script_Extensions`."""

import disarm

print(disarm.detect_scripts("\ufeff"), disarm.is_mixed_script("\ufeffhello"))  # BOM
print(disarm.is_mixed_script("\u09ac\u09be\u0982\u09b2\u09be\u0964"))  # Bengali + danda
print(disarm.is_mixed_script("\u0939\u093f\u0928\u094d\u0926\u0940\u0964"))  # Hindi + danda
print(disarm.is_mixed_script("\u078b\u07a8\u0788\u07ac\u060c"))  # Thaana + Arabic comma
print(disarm.inspect_anomalies("\u03b1\u00d7\u03b2").kinds)  # Greek with a multiplication sign
print(disarm.detect_scripts("\u3105"), disarm.is_mixed_script("a\u3105"))  # Bopomofo: none
