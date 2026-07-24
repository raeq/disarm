package com.disarm;

import java.util.List;

/**
 * Structured anomaly report. Returned by {@link Disarm#inspectAnomalies}.
 *
 * @param anomalous whether any token tripped (the same value {@code hasAnomalies} returns)
 * @param kinds     the anomaly kinds that fired, in first-appearance order
 * @param findings  every finding, with span and detail
 * @param reason    the first finding's reason, or {@code null}
 */
public record AnomalyReport(
        boolean anomalous, List<String> kinds, List<Finding> findings, String reason) {}
