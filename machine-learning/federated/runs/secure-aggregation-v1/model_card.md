# BEHAVE X25519/HKDF secure-aggregation protocol test

Seven real BEHAVE participant partitions trained in seven independent Windows processes for 60 local epochs. Each process generated an ephemeral X25519 key pair and derived pairwise cancelling masks with HKDF-SHA256. The coordinator received public keys and masked updates, not client private keys or plaintext updates.

The secure aggregate matched the independent plaintext audit to a maximum absolute error of `4.996e-15`, and both aggregates produced identical predictions. The frozen sequence-disjoint evaluation reached Accuracy `0.8069` and Macro-F1 `0.6934`.

This is a **single-machine multiprocess protocol validation**, not a real multi-device deployment. It does not implement dropout recovery, malicious-client protection, or transport TLS. Secure aggregation is not differential privacy: the final aggregate can still reveal information.

The aggregate metrics contain no participant identifiers, raw updates, private keys, or derived participant features. No model weight is released from this run.
