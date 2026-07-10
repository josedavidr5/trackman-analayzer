"""
trajectory — módulo independiente de análisis de trayectorias de pitcheo TrackMan.

No depende del resto del sistema: recibe filas/DataFrames con columnas TrackMan
y devuelve estructuras Python puras (dicts/listas), listas para JSON o gráficas.
"""
from .engine import (compute_pitch_path, pitch_metrics, initial_conditions,
                     PLATE_Y, RELEASE_DIST_TOTAL)
from .validation import validate_schema, validate_physical, REQUIRED_FIELDS, PHYSICAL_RANGES
from .analytics import (pitch_trajectory_payload, list_pitches, movement_profile,
                        release_consistency, velocity_spin_trends, ensure_pitch_ids)

__all__=["compute_pitch_path","pitch_metrics","initial_conditions",
         "validate_schema","validate_physical","REQUIRED_FIELDS","PHYSICAL_RANGES",
         "pitch_trajectory_payload","list_pitches","movement_profile",
         "release_consistency","velocity_spin_trends","ensure_pitch_ids",
         "PLATE_Y","RELEASE_DIST_TOTAL"]
