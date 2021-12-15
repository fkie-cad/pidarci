#!/usr/bin/env bash

PYTHONPATH=. python scripts/extract_assembly_from_response.py
PYTHONPATH=. python scripts/anonymize_assembly.py
PYTHONPATH=. python scripts/cluster_anonymized_assembly_snippets.py
PYTHONPATH=. python scripts/combine_clusters_to_single_file.py