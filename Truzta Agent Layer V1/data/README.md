# Data ownership

- `catalog/`: versioned shared GRC knowledge and approved relationships.
- `client-memory/`: one readable YAML document per client during local development.
- `schemas/`: machine-enforced contracts for catalog records.
- `assessments/`: reserved for assessment instances; assessment results do not belong in client memory.

The SCF JSON remains in `Small SCF JSON Master` as source data. Do not silently modify source mappings. Derived or manually approved relationships must record their provenance.
