package com.disarm;

/** Unicode normalization form. Maps to the core's {@code "NFC"|"NFD"|"NFKC"|"NFKD"} tokens. */
public enum NormalizationForm {
    NFC,
    NFD,
    NFKC,
    NFKD;

    String token() {
        return name();
    }
}
