"""Experiment runners for CouncilAgent benchmark evaluation.

MLflow and Hydra live only in this package (Constitution §8).
core/ and council/ are never imported from this package at module load time —
only inside function bodies, so the core pipeline stays framework-free.
"""
