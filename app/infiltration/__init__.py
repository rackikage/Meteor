"""Infiltration pipeline — authorized recon on machines you own.

NOT a botnet. This package is a **single-operator** pipeline with three layers
a junior dev can follow:

  FootprintLayer  — passive/local recon (scope, graph baseline, arsenal inventory)
  Grinder         — active mapping (existing ``grinder.*`` caps — scoped separately)
  InterceptLayer  — capture discovery events from the asset bus into structured intel

Think "map the battlefield on your lab network", not "command compromised hosts".

```
  [Footprint] ──► (optional Grinder via grinder.*) ──► [Intercept] ──► graph.query
       │                      │                              │
   network.scope         event bus                   drain discoveries
   graph.counts          publishes hosts/services
   arsenal.detect
```
"""

from app.infiltration.footprint import FootprintLayer
from app.infiltration.intercept import InterceptLayer
from app.infiltration.pipeline import InfiltrationPipeline

__all__ = ["FootprintLayer", "InterceptLayer", "InfiltrationPipeline"]
